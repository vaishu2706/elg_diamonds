from flask import Flask, request
from flask_cors import CORS
import mysql.connector
from twilio.rest import Client
import google.generativeai as genai
from dotenv import load_dotenv
import os
import json
import re

# Load environment variables
load_dotenv()

# Configuration
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_NUMBER = f"whatsapp:{os.getenv('TWILIO_NUMBER')}"
DB_HOST = os.getenv("DB_HOST")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_NAME = os.getenv("DB_NAME")

# Gemini setup
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-2.0-flash")

# Twilio client
client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

# Flask setup
app = Flask(__name__)
CORS(app)

# Database connection
conn = mysql.connector.connect(
    host=DB_HOST,
    user=DB_USER,
    password=DB_PASSWORD,
    database=DB_NAME
)

@app.route("/")
def home():
    return "Gemini + Twilio + Diamonds API is running"

@app.route("/whatsapp", methods=["POST"])
def whatsapp():
    incoming_msg = request.values.get("Body", "").strip()
    sender = request.values.get("From", "")

    try:
        # Gemini prompt
        prompt = f"""
You are a JSON extractor. Only output a valid JSON object. No explanations.

Extract these fields from the WhatsApp message. Only include fields that are mentioned:
- shapecode
- colorcode
- claritycode
- min_weight (optional)
- max_weight (optional)

If weight is mentioned like "1.5ct", assign both min_weight and max_weight to that number.

Format:
{{
  "shapecode": "...",     # optional
  "colorcode": "...",     # optional
  "claritycode": "...",   # optional
  "min_weight": 0.0,      # optional
  "max_weight": 0.0       # optional
}}

Message: "{incoming_msg}"
"""

        gemini_response = model.generate_content(prompt)
        gemini_text = gemini_response.text

        # Extract JSON from Gemini output
        try:
            json_text = re.search(r"\{.*\}", gemini_text, re.DOTALL).group(0)
            params = json.loads(json_text)
        except Exception:
            raise ValueError(f"Could not parse Gemini response: {gemini_text}")

        # Build SQL query dynamically
        query = "SELECT * FROM diamondsInventory WHERE 1=1"
        values = []

        if "shapecode" in params:
            query += " AND shapecode = %s"
            values.append(params["shapecode"])

        if "colorcode" in params:
            query += " AND colorcode = %s"
            values.append(params["colorcode"])

        if "claritycode" in params:
            query += " AND claritycode = %s"
            values.append(params["claritycode"])

        if "min_weight" in params and "max_weight" in params:
            min_wt = float(params["min_weight"])
            max_wt = float(params["max_weight"])
            if min_wt == max_wt:
                tolerance = 0.05
                query += " AND weight BETWEEN %s AND %s"
                values.extend([min_wt - tolerance, max_wt + tolerance])
            else:
                query += " AND weight BETWEEN %s AND %s"
                values.extend([min_wt, max_wt])

        query += " LIMIT 4"

        # Execute query
        cur = conn.cursor(dictionary=True)
        cur.execute(query, values)
        results = cur.fetchall()
        cur.close()

        if results:
            message = "\n\n".join([
                f"- {r['shapecode']} | {r['weight']} ct | Color: {r['colorcode']} | Clarity: {r['claritycode']}"
                for r in results
            ])
        else:
            message = "No diamonds found for your criteria. Try a different query."

    except Exception as e:
        message = f"Sorry, couldn't understand your request. Error: {str(e)}"

    # Send WhatsApp response
    client.messages.create(
        from_=TWILIO_NUMBER,
        to=sender,
        body=message,
        #media_url=['https://picsum.photos/200/300']
    )

    return "OK", 200

# Run the Flask app
if __name__ == "__main__":
    app.run(debug=True)
