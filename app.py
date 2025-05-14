from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
from twilio.rest import Client
import mysql.connector
import json
import os
import logging
import re
from dotenv import load_dotenv
from openai import OpenAI

# Flask App
app = Flask(__name__)

# Load env variables
load_dotenv()

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# OpenAI client
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Twilio client
account_sid = os.getenv("TWILIO_ACCOUNT_SID")
auth_token = os.getenv("TWILIO_AUTH_TOKEN")
twilio_number = os.getenv("TWILIO_NUMBER")
twilio_client = Client(account_sid, auth_token)

# Send outgoing WhatsApp message
def send_whatsapp_message(to_number, body_text):
    try:
        message = twilio_client.messages.create(
            from_=f"whatsapp:{twilio_number}",
            body=body_text,
            to=f"whatsapp:+91{to_number}"
        )
        logger.info(f"✅ Message sent to {to_number}: {message.body}")
    except Exception as e:
        logger.error(f"❌ Error sending message to {to_number}: {e}")

# Test route to send message manually
@app.route('/send-test', methods=['GET'])
def send_test():
    send_whatsapp_message("9346542588", "👋 Hello from ELG! Welcome to our diamond collection bot.")
    return "✅ WhatsApp message sent to 9346542588"

# MySQL connection
def connect_db():
    return mysql.connector.connect(
        host="128.199.21.237",
        user="thapala_admin",
        password="Thapala@123",
        database="ELG_Diamonds"
    )

# Extract user preferences using GPT
def extract_preferences_from_text(user_message):
    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "user",
                    "content": f"""
Extract diamond preferences from this message:
\"{user_message}\"

Return in JSON format only like this (do not add explanation):
{{
  "shape": "",
  "carat": "",
  "color": "",
  "clarity": "",
  "cut": "",
  "price": ""
}}
"""
                }
            ],
            temperature=0.2
        )
        content = response.choices[0].message.content

        try:
            return json.loads(content)
        except json.JSONDecodeError:
            match = re.search(r"\{.*\}", content, re.DOTALL)
            if match:
                return json.loads(match.group())
            else:
                return {"error": "Could not parse preferences"}
    except Exception as e:
        return {"error": str(e)}

# WhatsApp Webhook
@app.route('/whatsapp', methods=['POST'])
def whatsapp():
    incoming_msg = request.values.get("Body", "").strip()
    user_phone = request.values.get("From", "").replace("whatsapp:", "")

    logger.info(f"📩 Incoming from {user_phone}: {incoming_msg}")

    resp = MessagingResponse()
    msg = resp.message()

    conn = connect_db()
    cursor = conn.cursor(dictionary=True)

    # Check if user exists
    cursor.execute("SELECT * FROM users WHERE phone = %s", (user_phone,))
    user = cursor.fetchone()

    if not user:
        welcome_message = (
            "Hello! 👋 Welcome to ELG — your guide to the finest lab-grown diamonds 💎\n"
            "It seems you're a new visitor. Feel free to explore our offerings below.\n"
            "(Please note: To proceed with purchases, registration is required.)\n\n"
            "Please type what you'd like to explore:\n"
            "1. Lab Diamonds\n2. Lab Jewelry\n3. Lab Melee\n4. Track My Order"
        )
        msg.body(welcome_message)
        return str(resp)

    # Greet returning users
    if incoming_msg.lower() in ["hi", "hello"]:
        msg.body(
            "Hello! 👋 Welcome back to ELG — your guide to the finest lab-grown diamonds 💎\n"
            "You're a registered user. How can we assist you today?\n\n"
            "Please type what you'd like to explore:\n"
            "1. Lab Diamonds\n2. Lab Jewelry\n3. Lab Melee\n4. Track My Order"
        )
        return str(resp)

    if incoming_msg.lower() in ["1", "lab diamonds"]:
        msg.body(
            "Great choice! 💎 Let’s help you find the perfect lab-grown diamond.\n"
            "Please share your preferences like this:\n"
            "Example: I want a round diamond, 1.5 carat, D color, VS1 clarity, ideal cut, under $5000"
        )
        return str(resp)

    # Extract preferences from user's message
    preferences = extract_preferences_from_text(incoming_msg)
    if "error" in preferences:
        msg.body(f"Error parsing preferences: {preferences['error']}")
        return str(resp)

    # Search diamonds
    query = """
    SELECT shape, carat, color, clarity, cut, price FROM diamondsInventory
    WHERE shape = %s AND carat >= %s AND color = %s AND clarity = %s AND cut = %s AND price <= %s
    LIMIT 3
    """
    cursor.execute(query, (
        preferences['shape'],
        preferences['carat'],
        preferences['color'],
        preferences['clarity'],
        preferences['cut'],
        preferences['price']
    ))
    results = cursor.fetchall()

    if results:
        product_list = "\n".join([
            f"{i+1}. {r['shape']} - {r['carat']}ct - {r['color']} - {r['clarity']} - {r['cut']} - ${r['price']}"
            for i, r in enumerate(results)
        ])
        reply = (
            f"Thanks for the details! Based on your preferences, here’s what we found 👇\n\n{product_list}\n\n"
            "🔗 [View More Listings](http://128.199.21.237:5174/diamond-search)"
        )
    else:
        reply = (
            "It looks like we don’t have an exact match right now.\n"
            "Would you like us to prepare a custom quote for you?\nType \"Quote\" to proceed."
        )

    msg.body(reply)
    cursor.close()
    conn.close()
    return str(resp)

# Run Flask app
if __name__ == '__main__':
    app.run(debug=True)
