import streamlit as st
import requests
import json

# --- Configuración de la Página ---
st.set_page_config(
    page_title="Chatbot Pensante",
    page_icon="🤖",
    layout="wide"
)

# --- Título y Descripción de la Aplicación ---
st.title("🤖 Chatbot Sencillo con Ventana de 'Pensamiento' en Tiempo Real")
st.markdown("""
Este chatbot utiliza la API de OpenRouter para transmitir respuestas. Incluye una ventana de "Proceso de Pensamiento"
que muestra los pasos de razonamiento interno del modelo en tiempo real, si el modelo los proporciona.
""")

# --- Configuración de la Barra Lateral ---
with st.sidebar:
    st.header("Controles")

    # --- Botón para Limpiar el Chat ---
    if st.button("🗑️ Limpiar Historial de Chat"):
        st.session_state.messages = []
        st.rerun()

    st.divider()

    st.header("Configuración")

    # --- Lógica de la Clave de API (Primero secretos, luego entrada manual) ---
    # Intenta obtener la clave desde los secretos de Streamlit
    openrouter_api_key = st.secrets.get("openrouter_api_key")

    if openrouter_api_key:
        st.success("✅ Clave de API configurada desde los secretos.")
    else:
        st.warning("Clave de API no encontrada en los secretos.")
        openrouter_api_key = st.text_input(
            "Introduce tu Clave de API de OpenRouter",
            type="password",
            help="Obtén tu clave en https://openrouter.ai/keys"
        )

    st.subheader("Parámetros del Modelo")

    # Nota al usuario sobre la restricción del proveedor
    st.info("""
    Esta aplicación está configurada para enrutar las solicitudes para `qwen/qwen3-32b` exclusivamente a través del proveedor **Groq**, según lo solicitado.
    """)

    # Parámetros del modelo y de generación
    MODEL_NAME = "qwen/qwen3-32b"
    TEMPERATURE = 0.6
    TOP_P = 0.95
    TOP_K = 20
    MIN_P = 0.0

# --- Inicialización del Estado de la Sesión ---
if "messages" not in st.session_state:
    st.session_state.messages = []

# --- Mostrar Historial del Chat ---
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        # Mostrar el proceso de pensamiento para mensajes pasados del asistente si existe
        if message.get("reasoning"):
            with st.expander("Ver Proceso de Pensamiento"):
                st.markdown(message["reasoning"])

# --- Función de Streaming ---
def stream_openrouter_response(messages, api_key):
    """
    Genera fragmentos (chunks) desde el stream de la API de OpenRouter.
    Los fragmentos pueden ser de tipo 'reasoning', 'content', o 'error'.
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
        "reasoning": {"enabled": True} # Solicitar tokens de razonamiento
    }

    url = "https://openrouter.ai/api/v1/chat/completions"

    try:
        with requests.post(url, headers=headers, json=payload, stream=True) as r:
            r.raise_for_status()  # Lanza una excepción para códigos de estado erróneos (4xx o 5xx)
            buffer = ""
            for chunk in r.iter_content(chunk_size=None, decode_unicode=True):
                buffer += chunk
                # Procesar líneas completas
                while '\n' in buffer:
                    line, buffer = buffer.split('\n', 1)
                    if line.strip().startswith('data: '):
                        data_str = line.strip()[6:]
                        if data_str == '[DONE]':
                            return # Fin del stream

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
                            # Ignorar datos malformados o un array de 'choices' vacío
                            continue
    except requests.exceptions.RequestException as e:
        yield {"type": "error", "chunk": f"Error de API: {e}"}

# --- Lógica Principal del Chat ---
if prompt := st.chat_input("Pregúntame lo que sea..."):
    if not openrouter_api_key:
        st.info("Por favor, añade tu clave de API de OpenRouter en la barra lateral para continuar.")
        st.stop()

    # Añadir mensaje del usuario al estado y mostrarlo
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # Preparar la respuesta del asistente
    with st.chat_message("assistant"):
        # Crear elementos de la interfaz para el streaming
        thinking_expander = st.expander("🤔 Proceso de Pensamiento...", expanded=True)
        thinking_placeholder = thinking_expander.empty()
        response_placeholder = st.empty()

        full_response = ""
        thinking_text = ""
        thinking_placeholder.markdown("...") # Texto inicial
        response_placeholder.markdown("▌")   # Efecto de cursor parpadeante

        # Transmitir la respuesta desde la API
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

        # Actualización final sin el cursor
        response_placeholder.markdown(full_response)
        if not thinking_text:
            thinking_expander.markdown("_No se generaron tokens de razonamiento para esta respuesta._")

    # Añadir el mensaje final del asistente (con razonamiento) al estado de la sesión
    st.session_state.messages.append({
        "role": "assistant",
        "content": full_response,
        "reasoning": thinking_text
    })