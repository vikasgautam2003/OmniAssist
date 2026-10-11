import json
import uuid
from collections.abc import Iterator

import httpx
import streamlit as st
import styles

API_URL = "http://localhost:8000"
MIN_PASSWORD_LENGTH = 12

SUGGESTIONS = (
    "Summarise my document",
    "What are the key points?",
    "What is this about?",
)

st.set_page_config(
    page_title="OmniAssist",
    page_icon="◆",
    layout="centered",
    initial_sidebar_state="expanded",
)
styles.inject()


def start_session(token: str) -> None:
    """Store the token and begin a fresh conversation."""
    st.session_state.token = token
    st.session_state.conversation_id = str(uuid.uuid4())
    st.session_state.messages = []
    st.rerun()


def end_session() -> None:
    """Forget everything about the signed-in user."""
    for key in ("token", "conversation_id", "messages", "indexed"):
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
    st.markdown('<div class="auth-pad"></div>', unsafe_allow_html=True)

    # Streamlit renders every element in its own container, so an unclosed
    # <div> from st.markdown wraps nothing. Columns are how centring is done.
    _, middle, _ = st.columns([1, 6, 1])

    with middle:
        styles.brand("Ask questions about your own documents.")
        login_tab, signup_tab = st.tabs(["Log in", "Sign up"])

        for tab, (label, path) in zip(
            (login_tab, signup_tab),
            (("Log in", "/auth/login"), ("Sign up", "/auth/signup")),
            strict=True,
        ):
            with tab, st.form(f"form-{path}"):
                # A form batches input and submits once, instead of re-running
                # the script on every keystroke a bare text_input would.
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


def upload_document(name: str, data: bytes) -> None:
    """Send a PDF to be indexed, and report the outcome in the sidebar."""
    try:
        response = httpx.post(
            f"{API_URL}/documents",
            headers={"Authorization": f"Bearer {st.session_state.token}"},
            files={"file": (name, data, "application/pdf")},
            timeout=180.0,
        )
    except httpx.HTTPError:
        st.sidebar.error("Could not reach the server.")
        return

    if response.status_code == 401:
        end_session()
        return

    if response.status_code >= 400:
        # 400 carries a message written for the user -- "this needs OCR" --
        # so showing it is more useful than a generic failure.
        st.sidebar.error(response.json().get("detail", "Upload failed."))
        return

    passages = response.json()["passages"]
    st.sidebar.success(f"Indexed {name} into {passages} passages.")


def fetch_documents() -> list[str]:
    try:
        response = httpx.get(
            f"{API_URL}/documents",
            headers={"Authorization": f"Bearer {st.session_state.token}"},
            timeout=10.0,
        )
    except httpx.HTTPError:
        return []

    return list(response.json()) if response.status_code == 200 else []


def render_sidebar() -> list[str]:
    """Draw the sidebar and return the documents currently indexed."""
    with st.sidebar:
        styles.brand("Grounded answers")

        st.markdown(
            '<div class="side-label">Add a document</div>', unsafe_allow_html=True
        )
        upload = st.file_uploader(
            "Add a PDF", type="pdf", key="upload", label_visibility="collapsed"
        )

        # Streamlit re-runs the whole script on every interaction, so the
        # uploader still holds the file afterwards. Without remembering what
        # was indexed, every later keystroke would re-upload it.
        if upload is not None and st.session_state.get("indexed") != upload.file_id:
            with st.spinner("Indexing..."):
                upload_document(upload.name, upload.getvalue())
            st.session_state.indexed = upload.file_id

        documents = fetch_documents()

        st.markdown('<div class="side-label">Documents</div>', unsafe_allow_html=True)

        if documents:
            for document in documents:
                st.markdown(
                    f'<div class="doc">📄<span class="doc-name">{document}</span></div>',
                    unsafe_allow_html=True,
                )
            st.markdown(
                '<span class="pill pill-on"><span class="dot"></span>'
                "Answers are grounded</span>",
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                '<div class="doc" style="color:var(--muted)">Nothing indexed yet</div>',
                unsafe_allow_html=True,
            )
            st.markdown(
                '<span class="pill"><span class="dot"></span>'
                "General knowledge only</span>",
                unsafe_allow_html=True,
            )

        st.markdown('<div class="side-label">Session</div>', unsafe_allow_html=True)
        if st.button("New conversation", use_container_width=True):
            start_session(st.session_state.token)
        if st.button("Log out", use_container_width=True):
            end_session()

    return documents


def render_welcome(documents: list[str]) -> None:
    """Shown instead of an empty transcript, so the first screen is not blank."""
    grounded = (
        f"Ask about {len(documents)} indexed document"
        f"{'s' if len(documents) > 1 else ''}, or anything else."
        if documents
        else "Upload a PDF in the sidebar to ground answers in your own documents."
    )
    st.markdown(
        f'<div class="empty"><div class="empty-title">Start a conversation</div>'
        f'<div class="empty-text">{grounded}</div></div>',
        unsafe_allow_html=True,
    )

    for column, suggestion in zip(
        st.columns(len(SUGGESTIONS)), SUGGESTIONS, strict=True
    ):
        with column, st.container():
            if st.button(suggestion, use_container_width=True, key=f"s-{suggestion}"):
                st.session_state.pending = suggestion
                st.rerun()


def render_chat() -> None:
    documents = render_sidebar()

    styles.brand("Ask questions about your own documents.")

    if not st.session_state.messages:
        render_welcome(documents)

    # No custom avatar: st.chat_message only accepts an emoji, an image path
    # or a URL, and treats anything else as a path. "◆" is a dingbat, not an
    # emoji, so it was read as a filename and raised on every assistant reply.
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    # A suggestion chip queues its text and re-runs; the queued value is taken
    # here so both entry points go through exactly the same code path.
    pending = st.session_state.pop("pending", None)
    prompt = st.chat_input("Ask anything...") or pending

    if not prompt:
        return

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
    st.rerun()


# The gate. Streamlit has no routing: the script runs top to bottom on every
# interaction, so "am I signed in?" is re-derived here each time.
if "token" not in st.session_state:
    render_auth()
    st.stop()

render_chat()
