# Vocabulary Learning App

A web application that uses Google's Gemini LLM to help users learn and improve their vocabulary through interactive conversations.

## Features

- Interactive chat interface
- Personalized vocabulary learning experience
- Level-based vocabulary assessment
- Progress tracking
- Real-time feedback and corrections

## Setup

1. Make sure you have Python 3.7+ installed
2. Install the required dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Create a `.env` file in the root directory with your Gemini API key:
   ```
   GOOGLE_API_KEY=your_api_key_here
   ```

## Running the Application

1. Start the Flask server:
   ```bash
   python app.py
   ```
2. Open your web browser and navigate to `http://localhost:5000`

## Usage

1. The application will start by asking for your name
2. It will then assess your vocabulary level through a series of questions
3. Based on your level, it will provide appropriate vocabulary exercises
4. You can interact with the AI through the chat interface
5. The AI will provide feedback and corrections as needed

## Project Structure

- `app.py`: Main Flask application
- `templates/index.html`: Web interface
- `requirements.txt`: Python dependencies
- `.env`: Environment variables (API key) 