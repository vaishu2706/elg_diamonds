import os
import json
import mysql.connector
from flask import Flask, request
from flask_cors import CORS
from twilio.rest import Client
import google.generativeai as genai
import re

# Load environment variables
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_NUMBER = f"whatsapp:{os.getenv('TWILIO_NUMBER')}"
DB_HOST = os.getenv("DB_HOST")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_NAME = os.getenv("DB_NAME")

# Configure Gemini
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-2.0-flash")

# Twilio client
client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

# Flask setup
app = Flask(__name__)
CORS(app)

def format_product_details(details):
    """
    Format product details string into bullet points for better readability.
    Assumes details is a string with key-value pairs separated by commas or semicolons.
    """
    if not details:
        return ""
    # Split by comma or semicolon
    items = re.split(r'[;,]\s*', details)
    bullets = [f"• {item.strip()}" for item in items if item.strip()]
    return "\n".join(bullets)

@app.route("/")
def home():
    return "💎 WhatsApp + Gemini + MySQL Bot is running!"

@app.route("/whatsapp", methods=["POST"])
def whatsapp():
    incoming_msg = request.values.get("Body", "").strip()
    sender = request.values.get("From", "")

    # Gemini prompt to extract one or more diamond numbers
    prompt = f"""
You are a JSON extractor. Only output a valid JSON object. No explanations.

From the message below, extract all diamond option numbers (1, 2, 3, etc.) if mentioned.

Format:
{{
  "snos": [1, 3]
}}

If user says something like "I want diamond 2" or "Send options 1 and 3", extract those numbers as an integer array in `snos`.

Message: "{incoming_msg}"
"""

    try:
        # Get response from Gemini
        response = model.generate_content(prompt)

        # Log the raw response content to debug
        print("Gemini Response:", response.text)

        if not response.text.strip():
            raise ValueError("Gemini response is empty")

        # Try to extract JSON object from Gemini response using regex
        match = re.search(r"\{.*\}", response.text.strip(), re.DOTALL)
        if not match:
            raise ValueError(f"Could not extract JSON from Gemini response: {response.text.strip()}")
        json_response = match.group(0)

        try:
            data = json.loads(json_response)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON response: {str(e)}")

        if "snos" in data and isinstance(data["snos"], list) and data["snos"]:
            snos = [int(s) for s in data["snos"] if isinstance(s, int) or (isinstance(s, str) and s.isdigit())]
            if not snos:
                msg = "❌ Sorry, I couldn't understand which diamond(s) you want."
                media_url = None
            else:
                # Connect to DB and fetch data for all requested diamonds
                conn = mysql.connector.connect(
                    host=DB_HOST,
                    user=DB_USER,
                    password=DB_PASSWORD,
                    database=DB_NAME
                )
                cursor = conn.cursor(dictionary=True)
                format_strings = ','.join(['%s'] * len(snos))
                cursor.execute(f"SELECT * FROM bot_test_diamonds WHERE sno IN ({format_strings})", tuple(snos))
                results = cursor.fetchall()
                cursor.close()
                conn.close()

                if results:
                    msg_parts = []
                    media_urls = []
                    for result in results:
                        details = format_product_details(result.get('product_details', ''))
                        msg_parts.append(f"💎 *Diamond {result['sno']}*\n{details}")
                        if result.get("img_url"):
                            media_urls.append(result["img_url"])
                    msg = "\n\n".join(msg_parts)
                    # Only send up to 10 media URLs (Twilio limit per message)
                    media_url = media_urls[:10] if media_urls else None
                else:
                    msg = "❌ Sorry, I couldn't find any diamonds with those numbers."
                    media_url = None
        else:
            msg = "❌ Sorry, I couldn't understand which diamond(s) you want."
            media_url = None

    except ValueError as e:
        msg = f"⚠️ Error: {str(e)}"
        media_url = None
    except Exception as e:
        msg = f"⚠️ Error processing your request: {str(e)}"
        media_url = None

    # Add quick reply options (as text, since WhatsApp API doesn't support real buttons)
    msg += "\n\nReply with a diamond number (e.g., 1 or 2), or ask for multiple (e.g., 1 and 3).\nLet me know if you'd like to:\n• Format product details into bullet points\n• Handle multi-diamond queries (e.g., \"Show diamonds 1 and 3\")\n• Add quick reply buttons or options"

    # Send WhatsApp response
    client.messages.create(
        from_=TWILIO_NUMBER,
        to=sender,
        body=msg,
        media_url=media_url
    )

    return "OK", 200

if __name__ == "__main__":
    app.run(debug=True)