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

# Gemini config
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-1.5-flash")

# Twilio client
client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

# Flask app
app = Flask(__name__)
CORS(app)

@app.route("/")
def home():
    return "💎 Diamond WhatsApp Bot is running!"

@app.route("/whatsapp", methods=["POST"])
def whatsapp():
    incoming_msg = request.values.get("Body", "").strip()
    sender = request.values.get("From", "")

    # Gemini prompt to extract filters (now includes measurements)
    prompt = f"""
You are a diamond search assistant.

Extract structured filters (as JSON) from the following customer query. Only return a valid JSON.

Supported fields:
- colorcode (e.g., 'E', 'F', 'G')
- claritycode (e.g., 'VS1', 'VVS2', 'SI1')
- cut (e.g., 'Ideal', 'Excellent')
- polish (e.g., 'Excellent')
- symmetry (e.g., 'Excellent')
- price_max (integer, maximum price user wants)
- price_min (integer, if mentioned)
- shapecode (e.g., 'BR', 'PR')
- measurements (e.g., '11.02 x 10.93 x 6.65')

Message: "{incoming_msg}"

Example response:
{{
  "measurements": "11.02 x 10.93 x 6.65"
}}
"""

    try:
        response = model.generate_content(prompt)
        print("Gemini response:", response.text)

        match = re.search(r"\{.*\}", response.text.strip(), re.DOTALL)
        if not match:
            raise ValueError("Could not extract JSON from Gemini response")

        filters = json.loads(match.group(0))

        # Build SQL query dynamically
        query = "SELECT * FROM bot_test_BR WHERE 1=1"
        params = []

        if "colorcode" in filters:
            query += " AND colorcode = %s"
            params.append(filters["colorcode"].upper())

        if "claritycode" in filters:
            query += " AND claritycode = %s"
            params.append(filters["claritycode"].upper())

        if "cut" in filters:
            query += " AND cut = %s"
            params.append(filters["cut"].capitalize())

        if "polish" in filters:
            query += " AND polish = %s"
            params.append(filters["polish"].capitalize())

        if "symmetry" in filters:
            query += " AND symmetry = %s"
            params.append(filters["symmetry"].capitalize())

        if "shapecode" in filters:
            query += " AND shapecode = %s"
            params.append(filters["shapecode"].upper())

        if "price_max" in filters:
            query += " AND price <= %s"
            params.append(filters["price_max"])

        if "price_min" in filters:
            query += " AND price >= %s"
            params.append(filters["price_min"])

        if "measurements" in filters:
            query += " AND measurements = %s"
            params.append(filters["measurements"])

        # Fetch matching diamonds
        conn = mysql.connector.connect(
            host=DB_HOST, user=DB_USER, password=DB_PASSWORD, database=DB_NAME
        )
        cursor = conn.cursor(dictionary=True)
        cursor.execute(query, tuple(params))
        diamonds = cursor.fetchall()
        cursor.close()
        conn.close()

        if not diamonds:
            msg = "❌ No matching diamonds found. Try changing your filter."
            media_url = None
        else:
            msg_parts = []
            media_urls = []
            for d in diamonds[:3]:  # Limit to 3 diamonds
                msg_parts.append(f"""💎 *Diamond Option*
• Description: {d.get('description', '')}
• Shape: {d.get('shapecode', '')}
• Color: {d.get('colorcode', '')}
• Clarity: {d.get('claritycode', '')}
• Cut: {d.get('cut', '')}
• Polish: {d.get('polish', '').strip()}
• Symmetry: {d.get('symmetry', '')}
• Measurements: {d.get('measurements', '')}
• Price: ${d.get('price', '')}""")
                if d.get("img_url"):
                    media_urls.append(d["img_url"])

            msg = "\n\n".join(msg_parts)
            media_url = media_urls[:10]

    except Exception as e:
        msg = f"⚠️ Failed to process your query: {str(e)}"
        media_url = None

    # msg += "\n\nYou can ask things like:\n• Show E color diamonds\n• I want VVS2 clarity under $300\n• Ideal cut round diamonds"

    client.messages.create(
        from_=TWILIO_NUMBER,
        to=sender,
        body=msg,
        media_url=media_url
    )

    return "OK", 200

if __name__ == "__main__":
    app.run(debug=True)