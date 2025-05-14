


import streamlit as st
import google.generativeai as genai

# Configure Gemini API Key
genai.configure(api_key="AIzaSyAZO_TEsJ45FWzsuc-z_NhPCUy_hNOa3Ek")  # Replace with your actual key

# Initialize Gemini model
model = genai.GenerativeModel("gemini-2.0-flash")

# Session state for persistent chat
if "chat" not in st.session_state:
    st.session_state.chat = model.start_chat(history=[])

if "messages" not in st.session_state:
    st.session_state.messages = []

# Streamlit UI
st.title("💬bot")

# Display previous messages
for message in st.session_state.messages:
    role = "You" if message["role"] == "user" else "Gemini"
    st.markdown(f"**{role}:** {message['text']}")

# Input box
user_input = st.chat_input("Ask something...")

# On user input
if user_input:
    # Add user message
    st.session_state.messages.append({"role": "user", "text": user_input})
    with st.spinner("Gemini is thinking..."):
        try:
            response = st.session_state.chat.send_message(user_input)
            bot_reply = response.text
        except Exception as e:
            bot_reply = f"❌ Error: {str(e)}"
    
    # Add Gemini response
    st.session_state.messages.append({"role": "model", "text": bot_reply})
    st.rerun()

