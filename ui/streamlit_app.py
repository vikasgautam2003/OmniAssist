import json
import uuid
from collections.abc import Iterator

import httpx
import streamlit as st

API_URL = "http://localhost:8000"
MIN_PASSWORD_LENGTH = 12

st.set_page_config(page_title="OmniAssist", page_icon="🤖")


def start_session(token: str) -> None:
    """Store the token and begin a fresh conversation."""
    st.session_state.token = token
    st.session_state.conversation_id = str(uuid.uuid4())
    st.session_state.messages = []
    st.rerun()


def end_session() -> None:
    """Forget everything about the signed-in user."""
    for key in ("token", "conversation_id", "messages"):
        st.session_state.pop(key, None)
    st.rerun()


def submit_credentials(path: str, email: str, password: str) -> None:
    try:
        response = httpx.post(
            f"{API_URL}{path}",
            json={"email": email, "password": password},
            timeout=30,
        )
    except httpx.HTTPError:
        st.error("Could not reach the server. Is the API running?")
        return

    if response.status_code in (200, 201):
        start_session(response.json()["access_token"])
    elif response.status_code == 409:
        st.error("An account with that email already exists.")
    elif response.status_code == 401:
        st.error("Incorrect email or password.")
    elif response.status_code == 422:
        st.error(
            f"Check the email format and use at least {MIN_PASSWORD_LENGTH} characters."
        )
    else:
        st.error(f"Unexpected error ({response.status_code}).")


def render_auth() -> None:
    st.title("🤖 OmniAssist")
    st.caption("Sign in to continue.")

    login_tab, signup_tab = st.tabs(["Log in", "Sign up"])

    for tab, (label, path) in zip(
        (login_tab, signup_tab),
        (("Log in", "/auth/login"), ("Sign up", "/auth/signup")),
        strict=True,
    ):
        with tab, st.form(f"form-{path}"):
            # A form batches input and submits once, instead of re-running the
            # script on every keystroke the way a bare text_input would.
            email = st.text_input("Email", key=f"email-{path}")
            password = st.text_input("Password", type="password", key=f"pw-{path}")

            if st.form_submit_button(label, use_container_width=True):
                if not email or not password:
                    st.error("Email and password are required.")
                else:
                    submit_credentials(path, email, password)


def stream_reply(user_message: str) -> Iterator[str]:
    url = f"{API_URL}/chat/{st.session_state.conversation_id}"
    headers = {"Authorization": f"Bearer {st.session_state.token}"}

    with httpx.stream(
        "POST", url, json={"message": user_message}, headers=headers, timeout=None
    ) as response:
        if response.status_code == 401:
            # The token expired while the tab was open. Drop it so the next
            # run renders the login screen instead of a traceback.
            st.session_state.pop("token", None)
            raise PermissionError

        response.raise_for_status()

        for line in response.iter_lines():
            if not line.startswith("data: "):
                continue

            payload = line[len("data: ") :]

            if payload == "[DONE]":
                break

            yield json.loads(payload)


def render_chat() -> None:
    with st.sidebar:
        st.markdown("### OmniAssist")
        if st.button("New conversation", use_container_width=True):
            start_session(st.session_state.token)
        if st.button("Log out", use_container_width=True):
            end_session()

    st.title("🤖 OmniAssist")

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    if prompt := st.chat_input("Ask something"):
        st.session_state.messages.append({"role": "user", "content": prompt})

        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            try:
                reply = st.write_stream(stream_reply(prompt))
            except PermissionError:
                st.rerun()
            except httpx.HTTPError:
                st.error("Could not reach the server.")
                return

        st.session_state.messages.append({"role": "assistant", "content": reply})


# The gate. Streamlit has no routing: the script runs top to bottom on every
# interaction, so "am I signed in?" is re-derived here each time.
if "token" not in st.session_state:
    render_auth()
    st.stop()

render_chat()
