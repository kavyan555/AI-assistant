from flask import Flask, request, jsonify, render_template
import pyttsx3
from datetime import datetime
import wolframalpha
# import spacy
import re
from dotenv import load_dotenv
import os
import requests
import wikipedia
import threading  # Added for async TTS

# --- Setup ---
app = Flask(__name__)

# Text-to-Speech (optional) with threading
def speak_async(text):
    def run():
        engine = pyttsx3.init()
        engine.say(text)
        engine.runAndWait()
    threading.Thread(target=run).start()

load_dotenv()
# WolframAlpha
WOLFRAM_APP_ID = os.getenv("WOLFRAM_APP_ID")
client = wolframalpha.Client(WOLFRAM_APP_ID)
OPENWEATHER_KEY = os.getenv("OPENWEATHER_KEY")
NEWS_API_KEY = os.getenv("NEWS_API_KEY")

# NLP
# nlp = spacy.load("en_core_web_sm")

# --- Core Functions ---
def get_time():
    now = datetime.now()
    return f"The current time is {now.strftime('%I:%M %p')}"

def solve_math(query):
    query_lower = query.lower()
    # Convert number words to digits
    num_words = {
        "zero": "0", "one": "1", "two": "2", "three": "3", "four": "4",
        "five": "5", "six": "6", "seven": "7", "eight": "8", "nine": "9",
        "ten": "10"
    }

    for word, digit in num_words.items():
        query_lower = query_lower.replace(word, digit)

    # Handle "square of X"
    query_lower = re.sub(r"square of (\d+)", r"(\1**2)", query_lower)

    # Handle "cube of X"
    query_lower = re.sub(r"cube of (\d+)", r"(\1**3)", query_lower)

    # Handle "to the power of"
    query_lower = re.sub(r"(\d+)\s+to the power of\s+(\d+)", r"(\1**\2)", query_lower)

    # Other replacements
    query_lower = query_lower.replace("divided by", "/")
    query_lower = query_lower.replace("over", "/")
    query_lower = query_lower.replace("multiplied by", "*")
    query_lower = query_lower.replace("times", "*")
    query_lower = query_lower.replace("plus", "+")
    query_lower = query_lower.replace("minus", "-")

    # Clean up for safe eval
    query_clean = re.sub(r"[^0-9+\-*/(). ]", "", query_lower)

    try:
        result = eval(query_clean)
        return f"The answer is: {result}"
    except:
        # Fallback to WolframAlpha
        try:
            res = client.query(query)
            answer = next(res.results).text
            return f"The answer is: {answer}"
        except:
            return "Sorry, I couldn't solve that."

def set_reminder(msg):
    # Extract time from the message (HH:MM with optional am/pm)
    time_match = re.search(r'(\d{1,2}(:\d{2})?\s?(am|pm)?)', msg, re.IGNORECASE)
    if time_match:
        time_str = time_match.group(1).strip()
        return f"Sure, I will remind you at {time_str}."
    else:
        return "Sure, I will remind you soon."

def search_web(query):
    return f"Searching online for: {query} ... (This is a placeholder)"

# --- New Feature: Weather ---
def get_weather(city):
    url = f"https://api.openweathermap.org/data/2.5/weather?q={city}&appid={OPENWEATHER_KEY}&units=metric"
    try:
        response = requests.get(url)
        data = response.json()
        if data["cod"] == 200:
            temp = data["main"]["temp"]
            desc = data["weather"][0]["description"].capitalize()
            return f"The weather in {city} is {desc} with a temperature of {temp}°C."
        else:
            return "Sorry, I couldn't find that city."
    except:
        return "Error retrieving weather information."

# --- New Feature: News ---
def get_latest_news(topic="AI"):
    url = f"https://newsapi.org/v2/everything?q={topic}&apiKey={NEWS_API_KEY}&language=en&pageSize=3"
    try:
        response = requests.get(url)
        data = response.json()
        if data["status"] == "ok" and data["articles"]:
            headlines = [article["title"] for article in data["articles"][:3]]
            joined = "; ".join(headlines)
            return f"Here are the top {topic} news headlines: {joined}."
        else:
            return "No news found on that topic."
    except:
        return "Error fetching news."

# --- New Feature: Wikipedia ---
def search_wikipedia(query):
    try:
        summary = wikipedia.summary(query, sentences=2)
        return summary
    except:
        return "Sorry, I couldn't find information on that."

# --- Main Command Processor ---
def process_command(text):
    text_lower = text.lower().strip()

    # --- Greetings ---
    greetings = ["hi", "hello", "hey", "good morning", "good afternoon", "good evening"]
    if any(greet in text_lower for greet in greetings):
        responses = [
            "Hello! How can I assist you today?",
            "Hi there! What can I do for you?",
            "Hey! How’s your day going?",
            "Good to see you! How can I help?",
        ]
        import random
        return random.choice(responses)

    # --- Time ---
    if "time" in text_lower:
        return get_time()

    # --- Weather ---
    if "weather" in text_lower:
        match = re.search(r'weather in ([a-zA-Z\s]+)', text_lower)
        if match:
            city = match.group(1).strip()
            return get_weather(city)
        else:
            return "Please specify a city, like 'weather in Bangalore'."

    # --- Math ---
    math_keywords = ["calculate", "solve", "what is", "compute", "evaluate"]
    math_pattern = r"^[0-9+\-*/(). ]+$"
    if any(word in text_lower for word in math_keywords) or re.match(math_pattern, text_lower):
        return solve_math(text_lower)

    # --- News ---
    if "news" in text_lower:
        match = re.search(r'news on ([a-zA-Z\s]+)', text_lower)
        topic = match.group(1).strip() if match else "AI"
        return get_latest_news(topic)

    # --- Wikipedia ---
    if "who is" in text_lower or "what is" in text_lower:
        topic = text_lower.replace("who is", "").replace("what is", "").strip()
        if topic:
            return search_wikipedia(topic)

    # --- Reminder ---
    if "remind" in text_lower:
        return set_reminder(text)

    # --- Fallback ---
    return "Sorry, I can't help with that yet."

# --- Flask Routes ---
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/command', methods=['POST'])
def handle_command():
    data = request.json
    user_input = data.get("command", "")
    response = process_command(user_input)
    speak_async(response)  # Use threaded TTS
    return jsonify({"response": response})

if __name__ == "__main__":
    app.run(debug=True)



