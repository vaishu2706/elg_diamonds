
import streamlit as st
import requests

st.title("💎 ELG Diamond Assistant")
st.write("Chat with our diamond expert assistant")

# Input fields
phone = st.text_input("Enter your phone number")
message = st.text_area("Type your message")

if st.button("Send"):
    if not phone or not message:
        st.warning("Please enter both phone number and message.")
    else:
        with st.spinner("Getting response..."):
            try:
                response = requests.post(
                    "http://127.0.0.1:5000/chat",  # Update to your Flask host if different
                    json={"phone": phone, "message": message}
                )
                if response.status_code == 200:
                    st.success("Response:")
                    st.markdown(response.json()["reply"])
                else:
                    st.error(f"Error from server: {response.text}")
            except Exception as e:
                st.error(f"Failed to connect to Flask server: {e}")
