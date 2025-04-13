// Check for browser support for MediaRecorder and getUserMedia
if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
    alert('Your browser does not support microphone access (getUserMedia).');
}
if (!window.MediaRecorder) {
     alert('Your browser does not support MediaRecorder API.');
}

// Get DOM elements
const startButton = document.getElementById('startButton');
const stopButton = document.getElementById('stopButton');
const statusDiv = document.getElementById('status');
const transcriptDiv = document.getElementById('transcript');

let mediaRecorder;
let audioChunks = [];
let isRecording = false;
let audioStream = null; // Store the stream to stop tracks later

// Function to add messages to the transcript display
// Updated to handle audio status rather than text
function addToTranscript(speaker, statusText) {
    const p = document.createElement('p');
    p.textContent = `${speaker}: ${statusText}`;
    p.classList.add(speaker === 'user' ? 'user-speech' : 'bot-speech');

    // Clear initial message if present
    const initialMessage = transcriptDiv.querySelector('em');
    if (initialMessage) {
        transcriptDiv.removeChild(initialMessage.parentNode);
    }

    transcriptDiv.appendChild(p);
    transcriptDiv.scrollTop = transcriptDiv.scrollHeight; // Scroll to bottom
}

// Function to play received audio blob
function playAudio(audioBlob) {
    try {
        const audioUrl = URL.createObjectURL(audioBlob);
        const audio = new Audio(audioUrl);

        audio.onerror = (e) => {
            console.error("Error playing audio:", e);
            statusDiv.textContent = "Error playing audio response.";
            addToTranscript("system", "Error playing audio response.");
            startButton.disabled = false; // Re-enable start button on error
        };

        audio.onended = () => {
            console.log("Audio playback finished.");
            URL.revokeObjectURL(audioUrl); // Clean up object URL
            statusDiv.textContent = "Ready. Press Start Listening.";
            startButton.disabled = false; // Re-enable start button after playback
        };

        addToTranscript("Vdhya AI", "[Speaking...] ▶️"); // Indicate bot is speaking
        statusDiv.textContent = "Vdhya AI speaking...";
        startButton.disabled = true; // Disable start button while playing
        audio.play();

    } catch (e) {
        console.error("Error setting up audio playback:", e);
        statusDiv.textContent = "Error setting up audio playback.";
        addToTranscript("system", "Error setting up audio playback.");
        startButton.disabled = false;
    }
}

// Function to send audio blob to the backend and handle response
async function sendAudioToBackend(audioBlob) {
    statusDiv.textContent = 'Sending audio to Vdhya AI...';
    addToTranscript("You", "[Sent Audio] 🎙️"); // Indicate user audio sent
    startButton.disabled = true; // Disable button while processing

    try {
        // Use the same /voice_chat endpoint
        const response = await fetch('/voice_chat', {
            method: 'POST',
            headers: {
                // Set content type based on how audio was recorded
                // Adjust if using a different MIME type in MediaRecorder
                // 'audio/webm' is common, check browser compatibility
                'Content-Type': 'audio/webm;codecs=opus'
            },
            body: audioBlob
        });

        if (!response.ok) {
            // Try to get error text, otherwise use status text
            let errorMsg = `Server error: ${response.status} ${response.statusText}`;
            try {
                 // If the server sent an audio error message back
                if (response.headers.get("Content-Type")?.includes("audio")){
                    console.log("Received audio error message from server.");
                    const errorAudioBlob = await response.blob();
                    playAudio(errorAudioBlob); // Play the spoken error
                    // No need to throw here, error is handled by playing it
                    return; // Exit the function
                } else {
                    // Otherwise, assume text error
                    const errorData = await response.text();
                    errorMsg = errorData || errorMsg;
                }
            } catch (e) { /* Ignore if reading error body fails */ }
            throw new Error(errorMsg);
        }

        // Check if response is audio
        if (response.headers.get("Content-Type")?.includes("audio")){
             const receivedAudioBlob = await response.blob();
             playAudio(receivedAudioBlob); // Play the bot's audio reply
        } else {
            // Handle unexpected non-audio response
             const textResponse = await response.text();
             console.error("Received non-audio response:", textResponse);
             throw new Error("Received unexpected response format from server.");
        }

    } catch (error) {
        console.error('Error sending/receiving audio:', error);
        statusDiv.textContent = `Error: ${error.message}`;
        addToTranscript("system", `Error: ${error.message}`);
        startButton.disabled = false; // Re-enable button on error
    }
}

// --- MediaRecorder Setup and Handlers ---
function startRecording() {
    if (isRecording) return;

    navigator.mediaDevices.getUserMedia({ audio: true, video: false })
        .then(stream => {
            audioStream = stream; // Store stream
            // Configure MediaRecorder - check browser support for mimeType
            // Common options: 'audio/webm;codecs=opus', 'audio/ogg;codecs=opus', 'audio/wav'
            const options = { mimeType: 'audio/webm;codecs=opus' };
            try {
                 mediaRecorder = new MediaRecorder(stream, options);
            } catch (e) {
                console.warn("Specified mimeType possibly not supported, trying default:", e);
                mediaRecorder = new MediaRecorder(stream);
            }

            audioChunks = []; // Clear previous chunks

            mediaRecorder.ondataavailable = event => {
                if (event.data.size > 0) {
                    audioChunks.push(event.data);
                    console.log("Audio chunk added, size:", event.data.size);
                }
            };

            mediaRecorder.onstop = () => {
                console.log("Recording stopped. Total chunks:", audioChunks.length);
                if (audioChunks.length > 0) {
                    const audioBlob = new Blob(audioChunks, { type: mediaRecorder.mimeType });
                    console.log("Audio Blob created, type:", audioBlob.type, "size:", audioBlob.size);
                    sendAudioToBackend(audioBlob);
                } else {
                     console.warn("No audio chunks recorded.");
                     statusDiv.textContent = "No audio detected. Try again.";
                     startButton.disabled = false;
                }
                // Stop the tracks to turn off the mic light/indicator
                if (audioStream) {
                     audioStream.getTracks().forEach(track => track.stop());
                     audioStream = null;
                }
            };

            mediaRecorder.onerror = (event) => {
                console.error("MediaRecorder error:", event.error);
                statusDiv.textContent = `Recording error: ${event.error.name}`;
                 addToTranscript("system", `Recording error: ${event.error.name}`);
                isRecording = false;
                startButton.classList.remove('hidden');
                stopButton.classList.add('hidden');
                startButton.disabled = false;
                 // Stop tracks on error too
                if (audioStream) {
                     audioStream.getTracks().forEach(track => track.stop());
                     audioStream = null;
                }
            };

            mediaRecorder.start();
            isRecording = true;
            statusDiv.textContent = "Listening... Speak now.";
            startButton.classList.add('hidden');
            stopButton.classList.remove('hidden');
            console.log("MediaRecorder started, state:", mediaRecorder.state, "mimeType:", mediaRecorder.mimeType);

        }).catch(err => {
            console.error('Error accessing microphone:', err);
            statusDiv.textContent = `Mic access error: ${err.name}. Please allow microphone access.`;
            addToTranscript("system", `Mic access error: ${err.name}`);
        });
}

function stopRecording() {
    if (!isRecording || !mediaRecorder) return;

    if (mediaRecorder.state === 'recording') {
         try {
            mediaRecorder.stop(); // This will trigger the 'onstop' event
            isRecording = false;
            // Don't stop tracks here, wait for onstop to process data
            console.log("MediaRecorder stop requested.");
            statusDiv.textContent = "Processing audio...";
        } catch (e) {
            console.error("Error stopping MediaRecorder:", e);
            statusDiv.textContent = "Error stopping recording.";
        }
    }

    startButton.classList.remove('hidden');
    stopButton.classList.add('hidden');
    // Re-enable button will happen after processing/playback
    startButton.disabled = true;
}

// Event Listeners
startButton.addEventListener('click', startRecording);
stopButton.addEventListener('click', stopRecording);

// --- Initial Bot Greeting --- 
// We need a way to get the initial greeting audio. Let's trigger it separately.
async function getInitialGreetingAudio() {
     statusDiv.textContent = 'Connecting to Vdhya AI...';
     startButton.disabled = true;
     try {
         // Send a specific request, perhaps GET or POST with a special flag?
         // Let's adapt the POST /voice_chat to handle a specific "GET_GREETING" message
         const response = await fetch('/voice_chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }, // Send JSON for this specific request
            body: JSON.stringify({ action: "GET_GREETING" })
        });
        if (!response.ok) {
            let errorMsg = `Server error: ${response.status} ${response.statusText}`;
             try {
                 if (response.headers.get("Content-Type")?.includes("audio")){
                    const errorAudioBlob = await response.blob();
                    playAudio(errorAudioBlob);
                    return;
                } else {
                    const errorData = await response.text();
                    errorMsg = errorData || errorMsg;
                }
            } catch (e) {} 
            throw new Error(errorMsg);
        }
        
        if (response.headers.get("Content-Type")?.includes("audio")){
             const audioBlob = await response.blob();
             playAudio(audioBlob); // Plays the greeting
             // Status will be updated during playback by playAudio()
        } else {
             throw new Error("Received non-audio response for greeting.");
        }

    } catch (error) {
        console.error('Error fetching initial greeting:', error);
        statusDiv.textContent = `Error connecting: ${error.message}`;
        addToTranscript("system", `Error connecting: ${error.message}`);
        startButton.disabled = false;
    }
}

// Load initial greeting when the page loads
window.addEventListener('load', getInitialGreetingAudio); 