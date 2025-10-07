from flask import Flask, request, jsonify, render_template
from datetime import datetime
from zoneinfo import ZoneInfo 
from bs4 import BeautifulSoup
import pyttsx3
import wolframalpha
import spacy
import re
from dotenv import load_dotenv
import os
import requests
import wikipedia
import threading

#Setup 
app = Flask(__name__)

#Text-to-Speech (skip on Render) 
def speak_async(text):
    if os.getenv("RENDER") == "true":
        return  # Skip TTS on Render
    def run():
        engine = pyttsx3.init()
        engine.say(text)
        engine.runAndWait()
    threading.Thread(target=run).start()

# Load environment variables 
load_dotenv()
WOLFRAM_APP_ID = os.getenv("WOLFRAM_APP_ID")
client = wolframalpha.Client(WOLFRAM_APP_ID)
OPENWEATHER_KEY = os.getenv("OPENWEATHER_KEY")
NEWS_API_KEY = os.getenv("NEWS_API_KEY")

# Initialize APIs and NLP 
nlp = spacy.load("en_core_web_sm")  # Load small English model

def get_time():
    now = datetime.now(ZoneInfo("Asia/Kolkata"))
    return f"The current time is {now.strftime('%I:%M %p')}"

def solve_math(query):
    query_lower = query.lower()
    num_words = {
        "zero": "0", "one": "1", "two": "2", "three": "3", "four": "4",
        "five": "5", "six": "6", "seven": "7", "eight": "8", "nine": "9",
        "ten": "10"
    }
    for word, digit in num_words.items():
        query_lower = query_lower.replace(word, digit)

    query_lower = re.sub(r"square of (\d+)", r"(\1**2)", query_lower)
    query_lower = re.sub(r"cube of (\d+)", r"(\1**3)", query_lower)
    query_lower = re.sub(r"(\d+)\s+to the power of\s+(\d+)", r"(\1**\2)", query_lower)
    query_lower = query_lower.replace("divided by", "/").replace("over", "/")
    query_lower = query_lower.replace("multiplied by", "*").replace("times", "*")
    query_lower = query_lower.replace("plus", "+").replace("minus", "-").replace("subtracted by","-")
    query_clean = re.sub(r"[^0-9+\-*/(). ]", "", query_lower)

    try:
        result = eval(query_clean)
        return f"The answer is: {result}"
    except:
        try:
            res = client.query(query)
            answer = next(res.results).text
            return f"The answer is: {answer}"
        except:
            return "Sorry, I couldn't solve that."

def set_reminder(msg):
    time_match = re.search(r'(\d{1,2}(:\d{2})?\s?(am|pm)?)', msg, re.IGNORECASE)
    if time_match:
        time_str = time_match.group(1).strip()
        return f"Sure, I will remind you at {time_str}."
    else:
        return "Sure, I will remind you soon."

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

def get_latest_news(topic="AI"):
    url = f"https://newsapi.org/v2/everything?q={topic}&apiKey={NEWS_API_KEY}&language=en&pageSize=3"
    try:
        response = requests.get(url)
        data = response.json()
        if data["status"] == "ok" and data["articles"]:
            headlines = [article["title"] for article in data["articles"][:3]]
            return f"Here are the top {topic} news headlines: {'; '.join(headlines)}."
        else:
            return "No news found on that topic."
    except:
        return "Error fetching news."

def search_wikipedia(query):
    try:
        summary = wikipedia.summary(query, sentences=2)
        return summary
    except:
        return "Sorry, I couldn't find information on that."

def search_web(query):
    # Try Wikipedia first
    try:
        summary = wikipedia.summary(query, sentences=2)
        return summary
    except:
        pass  # Wikipedia failed, fallback to scraping

    # Fallback: Web scraping
    try:
        url = f"https://html.duckduckgo.com/html/?q={query}"
        headers = {"User-Agent": "Mozilla/5.0"}
        res = requests.get(url, headers=headers, timeout=5)
        soup = BeautifulSoup(res.text, "html.parser")
        snippet = soup.find("a", {"class": "result__snippet"})
        return snippet.get_text() if snippet else "No relevant info found."
    except Exception as e:
        return "Error fetching search results."

def linkify(text):
    url_regex = r'(https?://[^\s]+)'
    return re.sub(url_regex, r'<a href="\1" target="_blank">\1</a>', text)

# NLP Command Processor
def process_command(text):
    text_lower = text.lower().strip()
    commands = re.split(r'\band\b|;', text_lower)  # Split multiple commands
    responses = []

    for cmd in commands:
        cmd = cmd.strip()
        #Greetings 
        greetings = ["hi", "hello", "hey", "good morning", "good afternoon", "good evening"]
        import random
        if any(re.search(rf'\b{greet}\b', cmd) for greet in greetings):
            responses.append(random.choice([
                "Hello! How can I assist you today?",
                "Hi there! What can I do for you?",
                "Good to see you! How can I help?",
            ]))
            continue

        #  Browser Commands 
        if "open browser" in cmd or "launch browser" in cmd:
            if os.getenv("RENDER") == "true":
                responses.append("Click here to open Google:https://www.google.com")
            else:
                import webbrowser
                webbrowser.open("https://www.google.com")
                responses.append("Opening your web browser.")
            continue

        #  Time 
        if "time" in cmd:
            responses.append(get_time())
            continue

        #  Weather
        if "weather" in cmd:
            match = re.search(r'weather in ([a-zA-Z\s]+)', cmd)
            if match:
                city = match.group(1).strip()
                responses.append(get_weather(city))
                continue

        # News 
        if "news" in cmd:
            match = re.search(r'news on ([a-zA-Z\s]+)', cmd)
            topic = match.group(1).strip() if match else "AI"
            responses.append(get_latest_news(topic))
            continue

        #  Math 
        if any(word in cmd for word in ["calculate", "solve", "what is", "compute", "evaluate"]) or re.match(r"^[0-9+\-*/(). ]+$", cmd):
            responses.append(solve_math(cmd))
            continue

        #  Wikipedia 
        if any(phrase in cmd for phrase in ["who is", "what is", "tell me about"]):
            topic = cmd.replace("who is","").replace("what is","").replace("tell me about","").strip()
            if topic:
                responses.append(search_wikipedia(topic))
                continue

        #  Reminder 
        if "remind" in cmd:
            responses.append(set_reminder(cmd))
            continue

        # Fallback 
        responses.append("I couldn't understand that part: " + cmd)

    final_response = " ".join(responses)
    speak_async(final_response)
    final_response = linkify(final_response)
    return final_response



# Flask Routes 
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/command', methods=['POST'])
def handle_command():
    data = request.json
    user_input = data.get("command", "")
    response = process_command(user_input)
    speak_async(response)
    return jsonify({"response": response})

if __name__ == "__main__":
    app.run(debug=True)