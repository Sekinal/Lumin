import streamlit as st
from openai import OpenAI

# Initialize the OpenAI client with OpenRouter's base URL
client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=st.secrets["OPENROUTER_API_KEY"],  # Use Streamlit secrets to manage API keys
)

# Streamlit app title
st.title("Simple Chatbot using OpenRouter API")

# Initialize session state to store chat history
if "messages" not in st.session_state:
    st.session_state.messages = []

# Display chat history
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# User input
if prompt := st.chat_input("What is up?"):
    # Add user message to chat history
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # Call OpenRouter API
    completion = client.chat.completions.create(
        extra_headers={
            "HTTP-Referer": st.secrets.get("YOUR_SITE_URL", ""),  # Optional
            "X-Title": st.secrets.get("YOUR_SITE_NAME", ""),  # Optional
        },
        model="deepseek/deepseek-chat",
        messages=[
            {"role": m["role"], "content": m["content"]}
            for m in st.session_state.messages
        ],
    )

    # Get the assistant's response
    assistant_response = completion.choices[0].message.content

    # Add assistant response to chat history
    st.session_state.messages.append({"role": "assistant", "content": assistant_response})
    with st.chat_message("assistant"):
        st.markdown(assistant_response)