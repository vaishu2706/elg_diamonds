from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
from twilio.rest import Client
import mysql.connector
import json
import os
import logging
import re
import time
from dotenv import load_dotenv
from openai import OpenAI

app = Flask(__name__)

load_dotenv()

# Set up more detailed logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

account_sid = os.getenv("TWILIO_ACCOUNT_SID")
auth_token = os.getenv("TWILIO_AUTH_TOKEN")
twilio_number = os.getenv("TWILIO_NUMBER")
twilio_client = Client(account_sid, auth_token)

def send_whatsapp_message(to_number, body_text):
    try:
        message = twilio_client.messages.create(
            from_=f"whatsapp:{twilio_number}",
            body=body_text,
            to=f"whatsapp:+91{to_number}"
        )
        logger.info(f"Message sent to {to_number}: {message.body}")
    except Exception as e:
        logger.error(f"Error sending message to {to_number}: {e}")

def connect_db():
    try:
        conn = mysql.connector.connect(
            host="128.199.21.237",
            user="thapala_admin",
            password="Thapala@123",
            database="ELG_Diamonds",
            autocommit=False  # We'll manage transactions explicitly
        )
        logger.info("Database connection established successfully")
        return conn
    except Exception as e:
        logger.error(f"Database connection error: {e}")
        raise

def get_conversation_state(phone):
    """Get the conversation state for a phone number"""
    try:
        # Normalize phone number
        normalized_phone = phone.replace("whatsapp:", "").replace("+", "")
        logger.info(f"Getting state for normalized phone: {normalized_phone}")
        
        conn = connect_db()
        cursor = conn.cursor(dictionary=True)
        
        cursor.execute("SELECT state FROM conversation_state WHERE phone = %s", (normalized_phone,))
        row = cursor.fetchone()
        
        if row:
            state = row['state']
            logger.info(f"Found state for {normalized_phone}: {state}")
        else:
            state = None
            logger.info(f"No state found for {normalized_phone}")
        
        cursor.close()
        conn.close()
        return state
    except Exception as e:
        logger.error(f"Error getting state for {phone}: {e}")
        return None

def set_conversation_state(phone, state):
    """Set the conversation state for a phone number"""
    try:
        # Normalize phone number
        normalized_phone = phone.replace("whatsapp:", "").replace("+", "")
        logger.info(f"Setting state for {normalized_phone} to {state}")
        
        conn = connect_db()
        cursor = conn.cursor(dictionary=True)
        
        # First check if record exists
        cursor.execute("SELECT 1 FROM conversation_state WHERE phone = %s", (normalized_phone,))
        exists = cursor.fetchone() is not None
        
        if exists:
            logger.info(f"Updating existing state for {normalized_phone}")
            cursor.execute("UPDATE conversation_state SET state = %s WHERE phone = %s", 
                         (state, normalized_phone))
        else:
            logger.info(f"Inserting new state for {normalized_phone}")
            cursor.execute("INSERT INTO conversation_state (phone, state) VALUES (%s, %s)", 
                         (normalized_phone, state))
        
        # Commit the transaction
        conn.commit()
        logger.info(f"State change committed for {normalized_phone}")
        
        # Verify the change (for debugging)
        cursor.execute("SELECT state FROM conversation_state WHERE phone = %s", (normalized_phone,))
        row = cursor.fetchone()
        if row:
            logger.info(f"Verified state for {normalized_phone}: {row['state']}")
        else:
            logger.warning(f"WARNING: Could not verify state for {normalized_phone}")
        
        cursor.close()
        conn.close()
        return True
    except Exception as e:
        logger.error(f"Error setting state for {phone}: {e}")
        try:
            conn.rollback()
            conn.close()
        except:
            pass
        return False

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

def check_user_exists(phone):
    """Check if user exists in the users table"""
    try:
        normalized_phone = phone.replace("whatsapp:", "").replace("+", "")
        conn = connect_db()
        cursor = conn.cursor(dictionary=True)
        
        cursor.execute("SELECT * FROM users WHERE phone = %s", (normalized_phone,))
        user = cursor.fetchone()
        
        cursor.close()
        conn.close()
        
        return user is not None
    except Exception as e:
        logger.error(f"Error checking if user exists: {e}")
        return False

def create_user(phone):
    """Create a new user in the users table"""
    try:
        normalized_phone = phone.replace("whatsapp:", "").replace("+", "")
        
        conn = connect_db()
        cursor = conn.cursor()
        
        cursor.execute("INSERT INTO users (phone) VALUES (%s)", (normalized_phone,))
        conn.commit()
        
        cursor.close()
        conn.close()
        
        logger.info(f"Created new user with phone: {normalized_phone}")
        return True
    except Exception as e:
        logger.error(f"Error creating user: {e}")
        return False

@app.route('/whatsapp', methods=['POST'])
def whatsapp():
    incoming_msg = request.values.get("Body", "").strip()
    original_phone = request.values.get("From", "")
    user_phone = original_phone.replace("whatsapp:", "").replace("+", "")
    
    logger.info(f"Incoming message from {original_phone} (normalized: {user_phone}): {incoming_msg}")

    resp = MessagingResponse()
    msg = resp.message()

    # Check if user exists and create if not
    user_exists = check_user_exists(user_phone)
    if not user_exists:
        logger.info(f"New user detected: {user_phone}")
        create_user(user_phone)
        set_conversation_state(user_phone, "awaiting_selection")
        welcome_message = (
            "Hello! 👋 Welcome to ELG — your guide to the finest lab-grown diamonds 💎\n"
            "It seems you're a new visitor. Feel free to explore our offerings below.\n"
            "(Please note: To proceed with purchases, registration is required.)\n"
            "Please type what you'd like to explore:\n"
            "1. Lab Diamonds\n2. Lab Jewelry\n3. Lab Melee\n4. Track My Order"
        )
        msg.body(welcome_message)
        return str(resp)

    # Get the current conversation state
    current_state = get_conversation_state(user_phone)
    logger.info(f"Current state for {user_phone}: {current_state}")
    
    # Default state if none exists
    if current_state is None:
        current_state = "awaiting_selection"
        set_conversation_state(user_phone, current_state)
        logger.info(f"Set default state for existing user {user_phone}: {current_state}")

    # Handle greeting messages
    if incoming_msg.lower() in ["hi", "hello"]:
        msg.body(
            "Hello! Welcome back to ELG — your guide to the finest lab-grown diamonds.\n"
            "Please type what you'd like to explore:\n"
            "1. Lab Diamonds\n2. Lab Jewelry\n3. Lab Melee\n4. Track My Order"
        )
        set_conversation_state(user_phone, "awaiting_selection")
        return str(resp)

    # Handle different conversation states
    if current_state == "awaiting_selection":
        if incoming_msg == "1" or incoming_msg.lower() == "lab diamonds":
            msg.body("Please share your preferences like this:\nExample: I want a round diamond, 1.5 carat, D color, VS1 clarity, ideal cut, under $5000")
            set_conversation_state(user_phone, "awaiting_preferences")
        elif incoming_msg == "2" or incoming_msg.lower() == "lab jewelry":
            msg.body("Our jewelry collection is coming soon! Please check back later or explore our Lab Diamonds.")
            # State remains at awaiting_selection
        elif incoming_msg == "3" or incoming_msg.lower() == "lab melee":
            msg.body("Our Lab Melee collection is coming soon! Please check back later or explore our Lab Diamonds.")
            # State remains at awaiting_selection
        elif incoming_msg == "4" or incoming_msg.lower() == "track my order":
            msg.body("Please provide your order number to track your shipment.")
            set_conversation_state(user_phone, "awaiting_order_number")
        else:
            msg.body("Option not recognized. Please choose:\n1. Lab Diamonds\n2. Lab Jewelry\n3. Lab Melee\n4. Track My Order")

    elif current_state == "awaiting_preferences":
        try:
            preferences = extract_preferences_from_text(incoming_msg)
            if "error" in preferences:
                msg.body(f"Error parsing preferences: {preferences['error']}\n\nPlease try again with format: I want a round diamond, 1.5 carat, D color, VS1 clarity, ideal cut, under $5000")
                return str(resp)

            # Connect to database for diamond search
            conn = connect_db()
            cursor = conn.cursor(dictionary=True)
            
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
            
            cursor.close()
            conn.close()

            if results:
                product_list = "\n".join([
                    f"{i+1}. {r['shape']} - {r['carat']}ct - {r['color']} - {r['clarity']} - {r['cut']} - ${r['price']}"
                    for i, r in enumerate(results)
                ])
                reply = (
                    f"Thanks for the details! Based on your preferences, here's what we found:\n\n{product_list}\n\n"
                    "🔗 [View More Listings](http://128.199.21.237:5174/diamond-search)"
                )
                msg.body(reply)
                set_conversation_state(user_phone, "browsing_results")
            else:
                msg.body("No exact match found. Type 'Quote' if you'd like a custom quote.")
                set_conversation_state(user_phone, "awaiting_quote_confirmation")
        except Exception as e:
            logger.error(f"Error in awaiting_preferences state: {e}")
            msg.body("Sorry, we encountered an error processing your request. Please try again later.")
    
    elif current_state == "awaiting_order_number":
        # Basic validation for order number format
        if re.match(r'^[A-Za-z0-9-]+$', incoming_msg):
            msg.body(f"We're tracking your order {incoming_msg}. Your shipment is in process and will be delivered soon. For more details, please visit our website.")
            set_conversation_state(user_phone, "awaiting_selection")
        else:
            msg.body("Invalid order number format. Please try again with a valid order number.")
    
    elif current_state == "awaiting_quote_confirmation":
        if incoming_msg.lower() == "quote":
            msg.body("Thank you for requesting a custom quote. Our diamond specialist will contact you within 24 hours. Type 'Hi' to return to the main menu.")
            set_conversation_state(user_phone, "awaiting_selection")
        else:
            msg.body("To request a custom quote, please type 'Quote'. Or type 'Hi' to return to the main menu.")
    
    elif current_state == "browsing_results":
        if incoming_msg.lower() in ["more", "view more"]:
            msg.body("Please visit our website for more options: http://128.199.21.237:5174/diamond-search")
        else:
            msg.body("Thank you for browsing our diamonds. Type 'Hi' to restart or a new preference to continue searching.")
            set_conversation_state(user_phone, "awaiting_selection")
    
    else:
        # Fallback for unknown state
        msg.body("Please type 'Hi' to restart our conversation.")
        set_conversation_state(user_phone, "awaiting_selection")

    return str(resp)

# Debug route to test database connectivity
@app.route('/debug', methods=['GET'])
def debug():
    try:
        # Test database connection
        conn = connect_db()
        cursor = conn.cursor(dictionary=True)
        
        # Generate a unique test phone
        test_phone = f"debug_{int(time.time())}"
        
        # Test insert
        cursor.execute("INSERT INTO conversation_state (phone, state) VALUES (%s, %s)", 
                     (test_phone, "debug_state"))
        conn.commit()
        
        # Test select
        cursor.execute("SELECT * FROM conversation_state WHERE phone = %s", (test_phone,))
        inserted_row = cursor.fetchone()
        
        # Get all states
        cursor.execute("SELECT * FROM conversation_state LIMIT 10")
        all_rows = cursor.fetchall()
        
        # Clean up
        cursor.execute("DELETE FROM conversation_state WHERE phone = %s", (test_phone,))
        conn.commit()
        
        cursor.close()
        conn.close()
        
        return {
            "status": "success",
            "message": "Database connectivity test successful",
            "test_record": inserted_row,
            "existing_records": all_rows
        }
    except Exception as e:
        return {
            "status": "error",
            "message": str(e)
        }

if __name__ == '__main__':
    app.run(debug=True)