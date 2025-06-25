import streamlit as st
import requests
import json

# --- Page Configuration ---
st.set_page_config(
    page_title="Thinking Chatbot",
    page_icon="🤖",
    layout="wide"
)

# --- App Title and Description ---
st.title("🤖 Simple Chatbot with Real-Time 'Thinking' Window")
st.markdown("""
This chatbot uses the OpenRouter API to stream responses. It features a "Thinking Process"
window that shows the model's internal reasoning steps in real-time, if the model provides them.
""")

# --- Sidebar Configuration ---
with st.sidebar:
    st.header("Controls")

    # --- Clear Chat Button ---
    if st.button("🗑️ Clear Chat History"):
        st.session_state.messages = []
        st.rerun()

    st.divider()

    st.header("Configuration")

    # --- API Key Logic (Secrets first, then manual input) ---
    # Try to get the key from Streamlit secrets
    openrouter_api_key = st.secrets.get("openrouter_api_key")

    if openrouter_api_key:
        st.success("✅ API key configured from secrets.")
    else:
        st.warning("API key not found in secrets.")
        openrouter_api_key = st.text_input(
            "Enter your OpenRouter API Key",
            type="password",
            help="Get your key from https://openrouter.ai/keys"
        )


    st.subheader("Model Parameters")

    # Note to user about the provider constraint
    st.info("""
    This app is configured to route requests for `qwen/qwen3-32b` exclusively through the **Groq** provider, as requested.
    """)

    # Model and generation parameters
    MODEL_NAME = "qwen/qwen3-32b"
    TEMPERATURE = 0.6
    TOP_P = 0.95
    TOP_K = 20
    MIN_P = 0.0

# --- Session State Initialization ---
if "messages" not in st.session_state:
    st.session_state.messages = []

# --- Display Chat History ---
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        # Display the thinking process for past assistant messages if it exists
        if message.get("reasoning"):
            with st.expander("View Thinking Process"):
                st.markdown(message["reasoning"])

# --- Streaming Function ---
def stream_openrouter_response(messages, api_key):
    """
    Yields chunks from the OpenRouter API stream.
    Chunks can be of type 'reasoning', 'content', or 'error'.
    """
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://luminchat.streamlit.app/",
        "X-Title": "Lumin Chat"
    }

    payload = {
        "model": MODEL_NAME,
        "messages": messages,
        "stream": True,
        "temperature": TEMPERATURE,
        "top_p": TOP_P,
        "top_k": TOP_K,
        "min_p": MIN_P,
        "provider": {
            "only": ["groq"]
        },
        "reasoning": {"enabled": True} # Request reasoning tokens
    }

    url = "https://openrouter.ai/api/v1/chat/completions"

    try:
        with requests.post(url, headers=headers, json=payload, stream=True) as r:
            r.raise_for_status()  # Raise an exception for bad status codes (4xx or 5xx)
            buffer = ""
            for chunk in r.iter_content(chunk_size=None, decode_unicode=True):
                buffer += chunk
                # Process complete lines
                while '\n' in buffer:
                    line, buffer = buffer.split('\n', 1)
                    if line.strip().startswith('data: '):
                        data_str = line.strip()[6:]
                        if data_str == '[DONE]':
                            return # End of stream

                        try:
                            data_obj = json.loads(data_str)
                            delta = data_obj.get("choices", [{}])[0].get("delta", {})

                            reasoning_chunk = delta.get("reasoning")
                            if reasoning_chunk:
                                yield {"type": "reasoning", "chunk": reasoning_chunk}

                            content_chunk = delta.get("content")
                            if content_chunk:
                                yield {"type": "content", "chunk": content_chunk}

                        except (json.JSONDecodeError, IndexError):
                            # Ignore malformed data or empty choices array
                            continue
    except requests.exceptions.RequestException as e:
        yield {"type": "error", "chunk": f"API Error: {e}"}

# --- Main Chat Logic ---
if prompt := st.chat_input("Ask me anything..."):
    if not openrouter_api_key:
        st.info("Please add your OpenRouter API key in the sidebar to continue.")
        st.stop()

    # Add user message to state and display it
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # Prepare for assistant's response
    with st.chat_message("assistant"):
        # Create UI elements for streaming
        thinking_expander = st.expander("🤔 Thinking Process...", expanded=True)
        thinking_placeholder = thinking_expander.empty()
        response_placeholder = st.empty()

        full_response = ""
        thinking_text = ""
        thinking_placeholder.markdown("...") # Initial text
        response_placeholder.markdown("▌")   # Blinking cursor effect

        # Stream the response from the API
        for part in stream_openrouter_response(st.session_state.messages, openrouter_api_key):
            if part["type"] == "reasoning":
                thinking_text += part["chunk"]
                thinking_placeholder.markdown(thinking_text)
            elif part["type"] == "content":
                full_response += part["chunk"]
                response_placeholder.markdown(full_response + "▌")
            elif part["type"] == "error":
                response_placeholder.error(part["chunk"])
                break

        # Final update without the cursor
        response_placeholder.markdown(full_response)
        if not thinking_text:
            thinking_expander.markdown("_No reasoning tokens were generated for this response._")

    # Add the final assistant message (with reasoning) to session state
    st.session_state.messages.append({
        "role": "assistant",
        "content": full_response,
        "reasoning": thinking_text
    })