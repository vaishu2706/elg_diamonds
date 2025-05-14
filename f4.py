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

# Shape name to code mapping
shape_name_to_code = {
    "round": "BR",
    "br": "BR",
    "princess": "PR",
    "pr": "PR",
    "pear": "PS",
    "ps": "PS",
    "emerald": "EM",
    "em": "EM",
    "cushion": "CU",
    "cu": "CU",
    "radiant": "RAD",
    "rad": "RAD",
    "marquee": "MQ",
    "marquise": "MQ",
    "mq": "MQ",
    "heart": "HS",
    "hs": "HS",
    "asscher": "AS",
    "as": "AS",
    "oval": "OV",
    "ov": "OV"
}

# Cutgrade, polish, symmetry mappings
cutgrade_name_to_code = {
    "ideal": "ID",
    "id": "ID",
    "excellent": "EX",
    "ex": "EX",
    "very good": "VG",
    "vg": "VG",
    "good": "GD",
    "gd": "GD",
    "fair": "FR",
    "fr": "FR"
}

polish_name_to_code = {
    "excellent": "EX",
    "ex": "EX",
    "very good": "VG",
    "vg": "VG",
    "good": "GD",
    "gd": "GD",
    "fair": "FR",
    "fr": "FR"
}

symmetry_name_to_code = {
    "excellent": "EX",
    "ex": "EX",
    "very good": "VG",
    "vg": "VG",
    "good": "GD",
    "gd": "GD",
    "fair": "FR",
    "fr": "FR"
}

# Static image URL mapping by shapecode
shape_image_map = {
    "BR": "http://128.199.21.237:5174/assets/Round-DYMaxzIn.jpg",
    "PS": "http://128.199.21.237:5174/assets/Pear-uo1n2hk9.jpg",
    "EM": "http://128.199.21.237:5174/assets/Emrald-Dzmrk8MG.jpg",
    "PR": "http://128.199.21.237:5174/assets/Princess-P1BLJHQ5.jpg",
    "CU": "http://128.199.21.237:5174/assets/Cushion-IgOinUGl.jpg",
    "RAD": "http://128.199.21.237:5174/assets/Radiant-fjOgV3qu.jpg",
    "MQ": "http://128.199.21.237:5174/assets/Marquise-TVUAe-f0.jpg",
    "HS": "http://128.199.21.237:5174/assets/Heart-KG2hVKhC.jpg",
    "AS": "http://128.199.21.237:5174/assets/Asscher-CLyN8W6L.jpg",
    "OV": "http://128.199.21.237:5174/assets/Oval-BhxXtcLz.jpg"
}

@app.route("/")
def home():
    return "Gemini + Twilio + Diamonds API is running"

@app.route("/whatsapp", methods=["POST"])
def whatsapp():
    incoming_msg = request.values.get("Body", "").strip()
    sender = request.values.get("From", "")

    try:
        # Gemini prompt: ask for all possible fields
        prompt = f"""
You are a JSON extractor. Only output a valid JSON object. No explanations.

Extract any relevant diamond database fields and their values from the WhatsApp message below.
Supported fields include (but are not limited to): shapecode, colorcode, claritycode, labcode, cutgrade, polish, symmetry, lwd, price1, weight,id,code,etc.
If the user mentions a shape name (like "round"), convert it to the correct shapecode (BR, PR, PS, EM, CU, RAD, MQ, HS, AS, OV).
If weight is mentioned like "1.5ct", assign both min_weight and max_weight to that number.

Format:
{{
  "shapecode": "...",     # optional
  "colorcode": "...",     # optional
  "claritycode": "...",   # optional
  "labcode": "...",       # optional
  "cutgrade": "...",      # optional
  "polish": "...",        # optional
  "symmetry": "...",      # optional
  "lwd": "...",           # optional
  "price1": 0,            # optional
  "weight": 0.0,          # optional
  "min_weight": 0.0,      # optional
  "max_weight": 0.0,      # optional
  "id": 0,              # optional
  "code": "..."          # optional
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

        # Map shape names to codes if needed
        if "shapecode" in params:
            code = shape_name_to_code.get(params["shapecode"].strip().lower())
            if code:
                params["shapecode"] = code
            else:
                params["shapecode"] = params["shapecode"].upper()

        # Map cutgrade names to codes if needed
        if "cutgrade" in params:
            code = cutgrade_name_to_code.get(params["cutgrade"].strip().lower())
            if code:
                params["cutgrade"] = code
            else:
                params["cutgrade"] = params["cutgrade"].upper()

        # Map polish names to codes if needed
        if "polish" in params:
            code = polish_name_to_code.get(params["polish"].strip().lower())
            if code:
                params["polish"] = code
            else:
                params["polish"] = params["polish"].upper()

        # Map symmetry names to codes if needed
        if "symmetry" in params:
            code = symmetry_name_to_code.get(params["symmetry"].strip().lower())
            if code:
                params["symmetry"] = code
            else:
                params["symmetry"] = params["symmetry"].upper()

        # Build SQL query dynamically for all fields
        query = """
        SELECT shapecode, colorcode, claritycode, labcode, cutgrade, lwd, polish, symmetry, price1, weight, id, code
        FROM diamondsInventory WHERE 1=1
        """
        values = []

        for field, value in params.items():
            if field in ["min_weight", "max_weight"]:
                continue  # handled below
            if value is not None and value != "":
                query += f" AND {field} = %s"
                values.append(value)

        # Handle min_weight and max_weight for weight range
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

        # Execute query
        cur = conn.cursor(dictionary=True)
        cur.execute(query, values)
        results = cur.fetchall()
        cur.close()

        # Limit the number of diamonds sent
        max_results = 5
        total_found = len(results)
        results = results[:max_results]

        if results:
            # Send a summary message first
            summary_msg = f"Found {total_found} diamonds matching your criteria. Showing top {len(results)} results:"
            client.messages.create(
                from_=TWILIO_NUMBER,
                to=sender,
                body=summary_msg
            )
            for r in results:
                shape = r.get("shapecode", "")
                image_url = shape_image_map.get(shape)

                message = (
                    f"💎 *{shape} Diamond*\n"
                    f"id: {r.get('id', '')}\n"
                    f"code: {r.get('code', '')}\n"
                    f"Weight: {r.get('weight', '')} ct\n"
                    f"Color: {r.get('colorcode', '')}\n"
                    f"Clarity: {r.get('claritycode', '')}\n"
                    f"Cut: {r.get('cutgrade', '')}\n"
                    f"Lab: {r.get('labcode', '')}\n"
                    f"Polish: {r.get('polish', '')}, Symmetry: {r.get('symmetry', '')}\n"
                    f"lwd: {r.get('lwd', '')}\n"
                    f"Price: ${r.get('price1', '')}"
                )

                if image_url:
                    # Send each diamond as WhatsApp message with image
                    client.messages.create(
                        from_=TWILIO_NUMBER,
                        to=sender,
                        body=message,
                        media_url=[image_url]
                    )
                else:
                    # Send message stating image not available
                    client.messages.create(
                        from_=TWILIO_NUMBER,
                        to=sender,
                        body=message + "\n\nImage: Not available"
                    )
        else:
            client.messages.create(
                from_=TWILIO_NUMBER,
                to=sender,
                body="No diamonds found for your criteria. Try a different query."
            )

    except Exception as e:
        client.messages.create(
            from_=TWILIO_NUMBER,
            to=sender,
            body=f"Sorry, couldn't understand your request. Error: {str(e)}"
        )

    return "OK", 200

# Run the Flask app
if __name__ == "__main__":
    app.run(debug=True)