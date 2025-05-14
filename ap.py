
from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
from db import get_db_connection
from utils import parse_user_input
import logging

app = Flask(__name__)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@app.route("/whatsapp", methods=["POST"])
def whatsapp():
    # Get the incoming message from the user
    incoming_msg = request.values.get("Body", "").strip()
    user_number = request.values.get("From", "").split(":")[-1]
    
    # Log the incoming message for debugging
    logger.info(f"User message: {incoming_msg}")
    
    # Create the Twilio MessagingResponse object
    resp = MessagingResponse()
    msg = resp.message()

    # Define the response based on the incoming message
    if incoming_msg.lower() in ["hi", "hello"]:
        msg.body("""Hello! 👋 Welcome to ELG your guide to the finest lab-grown diamonds 💎

Please type what you'd like to explore:
1. Lab Diamonds
2. Lab Jewelry
3. Lab Melee
4. Track My Order
5. Talk to Support

(Reply with the number or keyword. E.g., "1" or "Lab Diamonds")""")
    elif incoming_msg.lower() in ["1", "lab diamonds"]:
        msg.body("""Great choice! 💎 Let’s help you find the lab-grown diamond.

Please share the following details:
Shape 
Carat 
Color 
Clarity 

(Example: 
Round 
1.5ct
D color
VS1 
)""")
    elif incoming_msg.lower().startswith("add to cart"):
        try:
            product_number = int(incoming_msg.split()[-1])
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("INSERT INTO cart1 (user_number, diamond_id) VALUES (%s, %s)", (user_number, product_number))
            conn.commit()
            msg.body("✅ Added to cart successfully.")
        except Exception as e:
            logger.error(f"Error adding to cart: {e}")
            msg.body("❌ Could not add to cart. Please try again.")
    elif incoming_msg.lower() in ["quote", "yes"]:
        msg.body("Sure! Please share your preferences again so our team can prepare a personalized quote.\n👉 https://elgdiamonds.com/custom-quote")
    elif "\n" in incoming_msg or "," in incoming_msg:
        preferences = parse_user_input(incoming_msg)
        logger.info(f"Extracted Preferences: {preferences}")

        if preferences:
            try:
                shape = preferences['shape'].capitalize()
                carat = float(str(preferences['carat']).replace("ct", "").strip())
                color = preferences['color'].upper().strip()
                clarity = preferences['clarity'].upper().strip()

                # Match frontend's defined carat ranges
                if 0.7 <= carat < 0.9:
                    carat_min, carat_max = 0.7, 0.89
                elif 0.9 <= carat < 1.0:
                    carat_min, carat_max = 0.9, 0.99
                elif 1.0 <= carat < 1.5:
                    carat_min, carat_max = 1.0, 1.49
                elif 1.5 <= carat < 2.0:
                    carat_min, carat_max = 1.5, 1.99
                elif 2.0 <= carat < 3.0:
                    carat_min, carat_max = 2.0, 2.99
                elif 3.0 <= carat < 4.0:
                    carat_min, carat_max = 3.0, 3.99
                elif 4.0 <= carat < 5.0:
                    carat_min, carat_max = 4.0, 4.99
                elif 5.0 <= carat <= 6.0:
                    carat_min, carat_max = 5.0, 6.0
                else:
                    msg.body("❌ Invalid carat range. Please choose between 0.7 and 6.0 carats.")
                    return str(resp)

                conn = get_db_connection()
                cursor = conn.cursor(dictionary=True)
                query = """
                    SELECT * FROM diamonds 
                    WHERE shape=%s AND carat BETWEEN %s AND %s AND color=%s AND clarity=%s 
                    LIMIT 4
                """
                cursor.execute(query, (shape, carat_min, carat_max, color, clarity))
                results = cursor.fetchall()

                if results:
                    reply = "Thanks for the details! Here’s what we found 👇\n"
                    for i, row in enumerate(results, 1):
                        reply += f"\n{i}. {row['title']}\n🔗 {row['product_url']}\nReply: 'add to cart {row['id']}' to add\n"
                    reply += "\nWant to explore more? 👉 http://128.199.21.237:5174/diamond-search"
                    msg.body(reply)
                else:
                    cursor.execute("INSERT INTO quote_requests (user_number, preferences) VALUES (%s, %s)", (user_number, incoming_msg))
                    conn.commit()
                    msg.body("❌ No match found. Would you like us to prepare a custom quote for you?\nReply 'Quote' or 'Yes'")
            except Exception as e:
                logger.error(f"Database error: {e}")
                msg.body("⚠️ Something went wrong while searching. Please try again later.")
        else:
            msg.body("⚠️ Please follow the format: Shape, Carat, Color, Clarity")
    else:
        msg.body("❓ Sorry, I didn’t get that. Please reply with a valid option (1-5) or say 'Hi' to start again.")

    # Return the response as a string, this is what will be sent to WhatsApp
    return str(resp)

if __name__ == "__main__":
    app.run(debug=True)
