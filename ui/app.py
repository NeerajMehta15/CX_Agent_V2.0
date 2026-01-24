import uuid

import requests
import streamlit as st

API_URL = "http://localhost:8000/api"

st.set_page_config(page_title="CX Agent", page_icon="💬", layout="centered")
st.title("CX Agent - Customer Support")

# Session state initialization
if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())
if "messages" not in st.session_state:
    st.session_state.messages = []
if "handoff_active" not in st.session_state:
    st.session_state.handoff_active = False

# Sidebar settings
with st.sidebar:
    st.header("Settings")
    tone = st.selectbox("Agent Tone", ["friendly", "professional", "playful"])
    st.divider()
    st.caption(f"Session: {st.session_state.session_id[:8]}...")
    if st.button("New Conversation"):
        st.session_state.session_id = str(uuid.uuid4())
        st.session_state.messages = []
        st.session_state.handoff_active = False
        st.rerun()

# Display chat history
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if msg.get("handoff"):
            st.warning("Transferred to human agent")

# Chat input
if prompt := st.chat_input("Type your message..."):
    # Display user message
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # Send to API
    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            try:
                response = requests.post(
                    f"{API_URL}/chat",
                    json={
                        "message": prompt,
                        "session_id": st.session_state.session_id,
                        "tone": tone,
                    },
                    timeout=30,
                )
                if response.status_code == 200:
                    data = response.json()
                    assistant_msg = data["response"]
                    st.markdown(assistant_msg)

                    msg_data = {"role": "assistant", "content": assistant_msg}

                    if data.get("handoff"):
                        st.warning(f"Handoff triggered: {data.get('handoff_reason', 'unknown')}")
                        msg_data["handoff"] = True
                        st.session_state.handoff_active = True

                    if data.get("tool_calls"):
                        with st.expander("Tools used"):
                            for tool in data["tool_calls"]:
                                st.code(tool)

                    st.session_state.messages.append(msg_data)
                else:
                    st.error(f"API error: {response.status_code}")
            except requests.exceptions.ConnectionError:
                st.error("Cannot connect to the API. Make sure the server is running: `uvicorn src.main:app --reload`")
            except Exception as e:
                st.error(f"Error: {e}")
