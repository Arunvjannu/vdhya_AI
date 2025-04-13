import os
import google.generativeai as genai
from flask import Flask, render_template, request, session, redirect, url_for, jsonify
from dotenv import load_dotenv
from google.cloud import speech
from google.cloud import texttospeech
import base64
import re

load_dotenv() # Load environment variables from .env file

app = Flask(__name__)
app.secret_key = os.urandom(24) # Needed for session management

# Configure the Gemini API client
try:
    genai.configure(api_key=os.environ["GOOGLE_API_KEY"])
except KeyError:
    print("ERROR: GOOGLE_API_KEY environment variable not set.")
    # Handle the error appropriately in a real application
    # For now, we might let it proceed but Gemini calls will fail.
    pass

# +++ Instantiate Google Cloud clients +++
speech_client = None
tts_client = None
credentials_path = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')

if not credentials_path:
    print("ERROR: GOOGLE_APPLICATION_CREDENTIALS environment variable is not set.")
elif not os.path.exists(credentials_path):
    print(f"ERROR: Credentials file not found at path: {credentials_path}")
    print("Please verify the path set in GOOGLE_APPLICATION_CREDENTIALS.")
elif not os.path.isfile(credentials_path):
     print(f"ERROR: Path exists but is not a file: {credentials_path}")
else:
    print(f"Attempting to use credentials file: {credentials_path}")
    try:
        # Explicitly pass credentials to ensure we're using the intended file
        # Although not strictly necessary if the env var is set, this adds clarity for debugging.
        # from google.oauth2 import service_account
        # credentials = service_account.Credentials.from_service_account_file(credentials_path)
        # speech_client = speech.SpeechClient(credentials=credentials)
        # tts_client = texttospeech.TextToSpeechClient(credentials=credentials)
        
        # Try implicit way first (standard method)
        speech_client = speech.SpeechClient()
        print("SpeechClient initialized successfully.")
        tts_client = texttospeech.TextToSpeechClient()
        print("TextToSpeechClient initialized successfully.")
        
    except Exception as e:
        print("-"*40)
        print(f"ERROR: Failed to initialize Google Cloud clients using credentials path: {credentials_path}")
        print(f"Specific Error Type: {type(e).__name__}")
        print(f"Specific Error Details: {e}")
        print("-"*40)
        print("Troubleshooting tips:")
        print("- Verify the GOOGLE_APPLICATION_CREDENTIALS path is correct.")
        print("- Ensure the JSON key file is valid and not corrupted.")
        print("- Check the service account's IAM permissions in GCP (e.g., Editor, or specific STT/TTS roles).")
        print("- Ensure the STT and TTS APIs are enabled in the correct GCP project.")
        print("- Check network connectivity/firewall settings.")
        # Clients remain None

# Simplified instructions for the LLM
SYSTEM_INSTRUCTIONS = r"""# LLM INSTRUCTIONS FOR VIDHYA AI (VOCABULARY TUTOR - PYTHON INTEGRATION)

# --- PERSONA & CORE DIRECTIVE ---
# You are vdhya AI, a sophisticated, professional, yet warm and encouraging AI assistant functioning as a personal Vocabulary Tutor.
# Your persona is professional, kind, like a caretaker, and focused on helping the user with their education.
# Your primary directive is to guide users through a structured English vocabulary learning process based on defined levels.
# You must execute conversational sequences precisely, evaluate user input accurately, provide clear corrections, and ensure word mastery using the specified logic.
# Maintain your persona consistently. Pronounce your name as 'vdhya AI' (all lowercase and AI in uppercase).
# **CRITICAL EXECUTION NOTE:** You MUST follow the numbered steps in the EXECUTION PROTOCOL strictly in sequence. Complete only ONE numbered step at a time. Where a step includes `*(Await Application providing ...)*`, you MUST stop and wait for the application to provide the next piece of information or user input before proceeding to the subsequent step.

# --- OPERATIONAL CONTEXT & DATA (PROVIDED BY APPLICATION/LLM) ---
# User State Management: Assume the application framework handles persistent storage of user data (name, education, confirmed level, list of mastered words for the current level).
# Vocabulary Level Structure: You MUST operate strictly within the following 10-level vocabulary structure. The application determines the user's level based on this structure. **You use this structure to select appropriate vocabulary.**
    # Level 1: Grades/Class 1-4
    #   - Target Word Count: ~150 - 300 words
    #   - Focus: Foundational vocabulary, sight words, basic nouns/verbs/adjectives, core concepts.
    #   - Example Words (Use for guidance): the, cat, run, happy, book
    # Level 2: Grade/Class 5
    #   - Target Word Count: ~200 - 350 words
    #   - Focus: Vocabulary expansion, common school terms, descriptive words, basic synonyms/antonyms.
    #   - Example Words (Use for guidance): friend, share, learn, brave, quickly
    # Level 3: Grade/Class 6
    #   - Target Word Count: ~250 - 400 words
    #   - Focus: Simple abstract concepts, common affixes, words for clearer explanation.
    #   - Example Words (Use for guidance): discover, curious, important, explain, unhappy
    # Level 4: Grade/Class 7
    #   - Target Word Count: ~300 - 500 words
    #   - Focus: Cross-subject vocabulary, common idioms, transition words, precise descriptors.
    #   - Example Words (Use for guidance): describe, compare, however, suddenly, analyze
    # Level 5: Grade/Class 8
    #   - Target Word Count: ~400 - 600 words
    #   - Focus: Core academic vocabulary, word connotations, sophisticated transitions, middle-grade literature terms.
    #   - Example Words (Use for guidance): frequent, diligent, consequence, perspective, elaborate
    # Level 6: Grade/Class 9
    #   - Target Word Count: ~500 - 700 words
    #   - Focus: General academic vocabulary (AWL components), analysis/argumentation terms, formal high school vocabulary.
    #   - Example Words (Use for guidance): hypothesis, evaluate, significant, influence, furthermore
    # Level 7: Grade/Class 10
    #   - Target Word Count: ~600 - 800 words
    #   - Focus: Academic consolidation, standardized test vocabulary, nuance/tone, critical thinking terms.
    #   - Example Words (Use for guidance): crucial, advocate, synthesize, differentiate, ambiguous
    # Level 8: Grades/Class 11-12 / Intermediate
    #   - Target Word Count: ~700 - 1000+ words
    #   - Focus: Higher academic vocabulary, entrance exam terms, complex analysis/synthesis vocabulary, formal communication.
    #   - Example Words (Use for guidance): meticulous, plausible, ubiquitous, exacerbate, empirical
    # Level 9: Degree, Engineering, or Graduation Students
    #   - Target Word Count: ~1500 - 2500+ words
    #   - Focus: Broad interdisciplinary academic vocabulary, domain-specific terminology introduction (incl. engineering), research/analysis terms, nuanced discourse.
    #   - Example Words (Use for guidance): paradigm, salient, juxtaposition, methodology, corollary
    # Level 10: Masters / PhD Students
    #   - Target Word Count: ~3000 - 5000+ words
    #   - Focus: Highly specialized field-specific vocabulary, sophisticated general academic terms, theoretical/methodological language, nuanced distinctions.
    #   - Example Words (Use for guidance): ephemeral, esoteric, elucidate, perfunctory, ontological
# Vocabulary Generation Responsibility: **You are responsible for selecting the next appropriate vocabulary word for the user's confirmed level, knowing its correct definition, and generating 1-2 accurate example sentences when needed for correction.** Use the Level Structure descriptions above (Focus, Example Words) as your guide for choosing words and gauging difficulty. Start with easier words within the level.
# Intra-Level Difficulty: Aim to present words within a level in an approximate order of increasing difficulty.

# --- EXECUTION PROTOCOL --- (Focus on Goals, Not Exact Phrasing)

# Phase 1: User Onboarding & Level Setting (Execute Only on First Interaction)
# Goal: Greet the user, gather necessary information, set the starting level based on education, and confirm readiness, all while embodying the defined persona.

1.  **Greeting & Introduction:** Initiate the conversation. Greet the user warmly, introduce yourself as vdhya AI, and clearly state your purpose of helping them learn vocabulary effectively and enjoyably.
2.  **Ask Name:** Politely ask the user for their name so you can personalize the interaction.
3.  **Acknowledge Name & Ask Education:** Once the name ([UserName]) is provided, acknowledge it warmly **and thank them for sharing it**. Then, explain that knowing their education level helps tailor the session and ask for their current grade or level of education.
4.  **Set Level & Explain Process:**
    *   Once education details ([UserEducation]) are provided, acknowledge them **and thank the user again for the information.** Inform them that based on their input, you will start at the appropriate level ([Confirmed Vocabulary Level] - provided by the application). **Do not describe the level details.**
    *   Explain the learning process: Clearly describe the upcoming interaction pattern – you will present a word, the user needs to provide its meaning and use it in a sentence. Reassure them that you are there to help if they find anything tricky.
5.  **Confirm Readiness:** Ask the user if they are ready to begin the vocabulary learning session.

# Phase 2: Vocabulary Training Module (Execute for each word in a session)
# Goal: Guide the user to master each presented word using the 'Repeat Until Correct' loop, providing encouragement and clear corrections as needed.

1.  **Select & Store Word:** Choose the next appropriate vocabulary word ('[Word]') for the user's current level ([Confirmed Vocabulary Level]), keeping track of words already mastered in the session/level. Store its correct definition and 1-2 example sentences internally for evaluation and correction.
2.  **Present Word:** Clearly present the target word ('[Word]') to the user. Adapt your phrasing slightly if it's the first word versus subsequent words in the session.
3.  **Request User Input:** Ask the user to provide both the meaning of the word ('[Word]') and an example sentence using it.
4.  **Evaluate Response:** Analyze the user's combined response against the correct definition and your understanding of valid sentence structure/usage you stored in Step 1. Determine if both the meaning and the sentence are correct. Signal this classification ('correct' or 'incorrect') to the application.
5.  **Execute Response Handling Logic:**
    *   **IF 'correct':**
        *   Offer positive reinforcement acknowledging both parts were correct. Use encouraging words fitting your persona.
        *   Signal 'mastery' of `[Word]` to the application.
        *   Indicate readiness for the next word (Return to Step 1 of Phase 2).
    *   **IF 'incorrect':**
        *   **Provide Correction:** Respond supportively, acknowledging their attempt. Clearly state the correct definition **(that you stored/know)** and provide one or two clear example sentences **that you generate** based on the word's meaning, using your defined persona.
        *   **Initiate Mastery Loop (IMPORTANT):** Immediately re-prompt the user to try the *same word* ('[Word]') again, asking for the meaning and a sentence now that they have the correction.
        *   **Re-evaluate:** Go back to Step 4 to evaluate this *new* response for the *same word*.
        *   **Repeat:** Continue this loop (Evaluate -> Correct/Re-prompt) until the user provides a 'correct' response for `[Word]`.
        *   **On final 'correct' response after correction:** Provide positive acknowledgement confirming they've grasped the word. Use encouraging words fitting your persona.
        *   Signal 'mastery' of `[Word]` to the application.
        *   Indicate readiness for the next word (Return to Step 1 of Phase 2).

# --- GENERAL GUIDANCE ---
# - Adhere strictly to the vdhya AI persona: knowledgeable, clear, professional, patient, kind, caretaker-like, and highly encouraging.
# - Utilize placeholders ([UserName], [Word], [CorrectDefinition], etc.) which the application will populate.
# - Ensure smooth conversational transitions.
# - Focus on executing the specified onboarding and training loop logic precisely. The application manages overall session flow, level progression triggers, and persistence.
# - **Handling Missing Information (Onboarding):** During Phase 1 (Onboarding), if you ask for specific information (like Name in step 2, or Education in step 3) and the user's response does not appear to provide that information, politely reiterate your request for that specific piece of information. Do not proceed to the next numbered step until you receive a response that seems to answer the question.
# - **Output Focus (CRITICAL):** ONLY output the direct conversational text intended for the user as specified in the protocol steps. Do NOT verbalize step numbers (e.g., "(Step 1)"), internal confirmations (e.g., "Okay, I will now ask for the name..."), or references to the prompt structure. Stick strictly to the user-facing dialogue.
# - **Output Formatting (CRITICAL): Your spoken response to the user MUST be plain text ONLY. Do NOT include any Markdown formatting (like `**word**`, `*word*`, `_word_`, `[link]`, etc.) in the text you generate for the user.**
# - **Example Sentence Formatting:** When providing example sentences (e.g., during correction), state them as complete, plain sentences. Do NOT use bullet points (like `* Example sentence.` or `- Example sentence.`). For instance, say "For example: It is crucial to pay attention. Another example is: Water is crucial for survival." instead of using list markers.
# - **Pronunciation Note 1 (CRITICAL): DO NOT SAY THE WORD "ASTERISK". EVER.** When you encounter text surrounded by double asterisks, like `**crucial**` or `**important**` (in internal instructions or examples ONLY), you MUST speak ONLY the word(s) *inside* the asterisks (e.g., speak "crucial", speak "important"). The `**` symbols are for internal emphasis ONLY and must be completely ignored in your spoken output. Do not mention them or the word "asterisk".
# - **Pronunciation Note 2 (CRITICAL):** NEVER pronounce the individual letters of abbreviations like 'e.g.'. You MUST interpret 'e.g.' as 'for example' and either say "for example" or naturally integrate the example into your sentence. Do NOT say "e g".
"""

# --- Model Initialization ---
generation_config = genai.GenerationConfig(
    temperature=0.7,
    # top_p=1.0, # Consider adjusting if needed
    # top_k=32,  # Consider adjusting if needed
    max_output_tokens=8192,
    response_mime_type="text/plain",
)
safety_settings = [
    {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
    {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
    {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
    {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
]

# Use the latest available Gemini 2.5 Pro model
model = genai.GenerativeModel(
    model_name="gemini-2.5-pro-preview-03-25", # gemini-1.5-pro-latest   -- Using 1.5 Pro as 2.5 is not yet available via API as of last check
    safety_settings=safety_settings,
    generation_config=generation_config,
    system_instruction=SYSTEM_INSTRUCTIONS,
)


@app.route("/")
def index():
    """Renders the main chat page, displaying history."""
    chat_history = session.get('chat_history', [])
    # Initialize chat with greeting if history is empty
    if not chat_history:
        try:
            # Start a new chat to get the initial greeting based on system prompt
            chat_session = model.start_chat(history=[])
            # Sending an empty message often triggers the initial system-prompt-driven response
            # Adjust this logic if the model doesn't respond as expected to an empty message
            initial_response = chat_session.send_message("Let's start") # Or send something innocuous
            if initial_response.text:
                 chat_history.append({"role": "model", "parts": [initial_response.text]})
                 session['chat_history'] = chat_history
        except Exception as e:
            error_type = type(e).__name__
            print(f"Error initializing chat ({error_type}): {e}")
            # Add an error message to display in the template
            session['error_message'] = f"Failed to initialize chat: {error_type}"
            # Optionally clear history if init fails
            # session['chat_history'] = []

    # Get error message if redirected from /chat due to an error
    error_message = session.pop('error_message', None)

    return render_template("chat_no_js.html", chat_history=chat_history, error_message=error_message)

@app.route("/chat", methods=["POST"])
def handle_chat():
    """Handles incoming chat messages from the HTML form."""
    user_input = request.form.get("message") # Get message from form data
    if not user_input:
        # Redirect back with an error or handle differently
        session['error_message'] = "No message provided."
        return redirect(url_for('index'))

    # Retrieve chat history from session
    chat_history = session.get('chat_history', [])

    # Add user message to history
    chat_history.append({"role": "user", "parts": [user_input]})

    try:
        # Start a chat session using the history
        chat_session = model.start_chat(history=chat_history)
        response = chat_session.send_message(user_input)

        # Add model response to history
        chat_history.append({"role": "model", "parts": [response.text]})

        # Store updated history back in session
        session['chat_history'] = chat_history

    except Exception as e:
        error_type = type(e).__name__
        print(f"Error in /chat route ({error_type}): {e}")
        user_error_message = f"Sorry, I encountered an error ({error_type}). Please try again later."
        if "API key not valid" in str(e) or "GOOGLE_API_KEY" in str(e):
             user_error_message = "API key configuration error. Cannot contact the AI."
        # Store error in session to display on redirect
        session['error_message'] = user_error_message
        # Don't save the failed interaction history parts if needed
        # session['chat_history'] = chat_history[:-2] # Remove user input and failed model response attempt

    # Redirect back to the main page to display updated history (or error)
    return redirect(url_for('index'))

# +++ New Voice Chat Routes (Now Server-Side STT/TTS) +++
@app.route("/voice")
def voice_index():
    """Renders the VOICE chat page."""
    session.pop('voice_chat_history', None)
    return render_template("voice_chat.html")

@app.route("/voice_chat", methods=["POST"])
def handle_voice_chat():
    # Check if clients initialized correctly
    if not speech_client or not tts_client:
        print("ERROR: Cloud clients not initialized.")
        return jsonify({'error': 'Internal server error: Cloud clients not available.', 'message': 'Internal server error: Cloud clients not available.'}), 500

    # --- Check for Initial Greeting Request ---    
    if request.is_json:
        try:
            data = request.get_json()
            if data and data.get("action") == "GET_GREETING":
                print("Received GET_GREETING request.")
                session.pop('voice_chat_history', None) 
                voice_chat_history = []
                try:
                    chat_session = model.start_chat(history=voice_chat_history)
                    response = chat_session.send_message("Start the conversation by greeting the user warmly, introducing yourself as vdhya AI, stating your purpose, and then asking for their name.")
                    greeting_text = response.text
                    print(f"Generated Greeting + Name Request: {greeting_text}")
                    
                    voice_chat_history.append({"role": "model", "parts": [greeting_text]})
                    session['voice_chat_history'] = voice_chat_history
                    
                    greeting_audio_content = synthesize_tts(greeting_text)
                    if greeting_audio_content:
                        audio_base64 = base64.b64encode(greeting_audio_content).decode('utf-8')
                        return jsonify({'text': greeting_text, 'audio': audio_base64})
                    else:
                        raise Exception("Failed to synthesize greeting audio.")
                        
                except Exception as e:
                    print(f"ERROR getting/synthesizing initial greeting: {e}")
                    error_msg = "Sorry, I couldn't start the conversation."
                    # We can't easily synthesize audio for this JSON error response
                    return jsonify({'error': 'Greeting Error', 'message': error_msg}), 500
        except Exception as e:
            print(f"INFO: Failed to parse JSON, assuming audio data. Error: {e}")
            pass 
            
    # --- If not greeting request, assume Audio Data for STT ---    
    audio_data = request.data
    if not audio_data:
        print("ERROR: No audio data received (and not a greeting request).")
        return jsonify({'error': 'No Audio Data', 'message': 'Error: No audio data received.'}), 400

    # --- Speech-to-Text ---    
    transcribed_text = ""
    try:
        config = speech.RecognitionConfig(
            encoding=speech.RecognitionConfig.AudioEncoding.WEBM_OPUS, 
            sample_rate_hertz=48000, 
            language_code="en-US",
        )
        audio = speech.RecognitionAudio(content=audio_data)
        print(f"Sending audio (size: {len(audio_data)}) to Google Cloud STT...")
        stt_response = speech_client.recognize(config=config, audio=audio)
        print("Received response from Google Cloud STT.")
        if stt_response.results:
            transcribed_text = stt_response.results[0].alternatives[0].transcript
            print(f"STT Result: {transcribed_text}")
        else:
            print("STT Warning: No transcription results returned.")
            # Return a JSON response indicating no transcription
            no_catch_text = "Sorry, I didn't quite catch that."
            no_catch_audio_content = synthesize_tts(no_catch_text)
            if no_catch_audio_content:
                 audio_base64 = base64.b64encode(no_catch_audio_content).decode('utf-8')
                 # Send user text as empty? Or maybe what the server thought?
                 # Sending empty user text might be confusing. Let's just send the bot reply.
                 return jsonify({'user_text': '', 'bot_text': no_catch_text, 'audio': audio_base64})
            else:
                 return jsonify({'error': 'STT/TTS Error', 'message': no_catch_text}), 500

    except Exception as e:
        print(f"ERROR during STT: {e}")
        error_msg = "Sorry, there was an error processing your speech."
        return jsonify({'error': 'STT Error', 'message': error_msg}), 500

    # --- Gemini Interaction ---    
    voice_chat_history = session.get('voice_chat_history', [])
    voice_chat_history.append({"role": "user", "parts": [transcribed_text]}) # History uses actual transcription
    bot_reply_text = ""
    try:
        print(f"Sending to Gemini: {transcribed_text}")
        chat_session = model.start_chat(history=voice_chat_history)
        response = chat_session.send_message(transcribed_text)
        raw_bot_reply_text = response.text
        print(f"Received from Gemini (raw): {raw_bot_reply_text}")
        
        # <<< ENHANCED: Clean the response text >>>
        # Remove markdown bold
        cleaned_text = raw_bot_reply_text.replace("**", "") 
        # Remove markdown list bullets (* or - followed by space) at the start of lines
        # We use regex for potentially better handling of multiline text
        cleaned_text = re.sub(r"^\s*[-*]\s+", "", cleaned_text, flags=re.MULTILINE)
        # Assign cleaned text back
        bot_reply_text = cleaned_text
        print(f"Cleaned bot reply text: {bot_reply_text}")
        
        voice_chat_history.append({"role": "model", "parts": [bot_reply_text]}) # Store cleaned text in history
        session['voice_chat_history'] = voice_chat_history
    except Exception as e:
        print(f"ERROR during Gemini interaction: {e}")
        error_msg = "Sorry, there was an error communicating with the AI."
        return jsonify({'error': 'Gemini Error', 'message': error_msg}), 500

    # --- Text-to-Speech ---    
    # Use the cleaned text for TTS
    tts_audio_content = synthesize_tts(bot_reply_text) 
    if tts_audio_content:
        audio_base64 = base64.b64encode(tts_audio_content).decode('utf-8')
        # Return transcription, CLEANED bot reply, and audio
        return jsonify({ 
            'user_text': transcribed_text, 
            'bot_text': bot_reply_text, # Send cleaned text
            'audio': audio_base64 
        })
    else:
        error_msg = "Sorry, there was an error generating the audio response."
        # Include texts (cleaned bot text) even if TTS fails
        return jsonify({'error': 'TTS Error', 'message': error_msg, 'user_text': transcribed_text, 'bot_text': bot_reply_text}), 500

# Helper function to synthesize text (returns audio content or None)
def synthesize_tts(text):
    if not tts_client:
        print("Error: TTS client not available for synthesis.")
        return None
    try:
        print(f"Synthesizing TTS for: {text[:50]}...")
        synthesis_input = texttospeech.SynthesisInput(text=text)
        voice = texttospeech.VoiceSelectionParams(
            language_code="en-US",
            ssml_gender=texttospeech.SsmlVoiceGender.NEUTRAL
        )
        audio_config = texttospeech.AudioConfig(
            audio_encoding=texttospeech.AudioEncoding.MP3
        )
        response = tts_client.synthesize_speech(
            input=synthesis_input, voice=voice, audio_config=audio_config
        )
        print("TTS Synthesis successful.")
        return response.audio_content # Return only the audio content
    except Exception as e:
        print(f"ERROR during TTS synthesis: {e}")
        return None

# Remove synthesize_error_message as errors now return JSON
# def synthesize_error_message(message): ... 

if __name__ == "__main__":
    # Create templates directory if it doesn't exist
    if not os.path.exists("templates"):
        os.makedirs("templates")
    # NOTE: We are no longer dynamically creating chat.html here.
    # We will create templates/chat_no_js.html manually or in the next step.
    print("Flask app starting. Ensure templates/chat_no_js.html exists.")
    print("Access at http://127.0.0.1:5001")
    app.run(debug=True, port=5001)