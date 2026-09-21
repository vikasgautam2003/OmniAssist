import json
import uuid
from collections.abc import Iterator

import httpx
import streamlit as st

API_URL = "http://localhost:8000"

st.title("OmniAssist")

if "conversation_id" not in st.session_state:
    st.session_state.conversation_id = str(uuid.uuid4())

if "messages" not in st.session_state:
    st.session_state.messages = []


for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])


def stream_reply(user_message: str) -> Iterator[str]:
    url = f"{API_URL}/chat/{st.session_state.conversation_id}"

    with httpx.stream(
        "POST", url, json={"message": user_message}, timeout=None
    ) as response:
        for line in response.iter_lines():
            if not line.startswith("data: "):
                continue

            payload = line[len("data: ") :]

            if payload == "[DONE]":
                break

            yield json.loads(payload)


if prompt := st.chat_input("Ask something"):
    st.session_state.messages.append({"role": "user", "content": prompt})

    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        reply = st.write_stream(stream_reply(prompt))

    st.session_state.messages.append({"role": "assistant", "content": reply})
