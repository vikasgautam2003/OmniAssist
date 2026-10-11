"""Visual styling for the Streamlit interface.

Kept out of the app module so the application file stays about behaviour.
Streamlit exposes no theming API beyond a handful of colours, so anything
past that has to be CSS targeted at its `data-testid` attributes.
"""

import streamlit as st

INK = "#E6EDF3"
MUTED = "#8B949E"
ACCENT = "#7C6CFF"
SURFACE = "#151B23"
BORDER = "#242C38"

CSS = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

:root {{
    --ink: {INK};
    --muted: {MUTED};
    --accent: {ACCENT};
    --accent-soft: rgba(124, 108, 255, 0.14);
    --surface: {SURFACE};
    --border: {BORDER};
    --radius: 14px;
}}

/* Narrow on purpose. A blanket [class*="st-"] rule also catches Streamlit's
   icon spans, whose glyphs are font ligatures -- the password reveal icon
   then renders as the literal text "visibility". */
html, body, button, input, textarea, p, h1, h2, h3, h4, label,
[data-testid="stAppViewContainer"], [data-testid="stSidebar"] {{
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
}}
[data-testid="stIconMaterial"], span[data-baseweb="icon"], i, .material-icons,
[class*="material-symbols"] {{
    font-family: 'Material Symbols Rounded', 'Material Icons' !important;
}}

#MainMenu, footer, header {{ visibility: hidden; }}

.block-container {{ padding-top: 2.4rem; padding-bottom: 7rem; max-width: 46rem; }}

/* ---------- brand ---------- */
.brand {{
    display: flex; align-items: center; gap: 0.7rem; margin-bottom: 0.2rem;
}}
.brand-mark {{
    width: 34px; height: 34px; border-radius: 10px; flex: none;
    background: linear-gradient(135deg, var(--accent), #A78BFA);
    display: flex; align-items: center; justify-content: center;
    font-size: 17px; box-shadow: 0 6px 18px rgba(124, 108, 255, 0.35);
}}
.brand-name {{
    font-size: 1.35rem; font-weight: 700; letter-spacing: -0.02em; color: var(--ink);
}}
.brand-sub {{ color: var(--muted); font-size: 0.85rem; margin: 0.1rem 0 1.6rem 0; }}

/* ---------- chat ---------- */
[data-testid="stChatMessage"] {{
    background: transparent; padding: 0.35rem 0; gap: 0.7rem;
}}
[data-testid="stChatMessageAvatarAssistant"] {{
    background: linear-gradient(135deg, var(--accent), #A78BFA);
    color: #fff; border: none;
}}
[data-testid="stChatMessageAvatarUser"] {{
    background: var(--surface); border: 1px solid var(--border); color: var(--muted);
}}
[data-testid="stChatMessage"] [data-testid="stChatMessageContent"] {{
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 0.85rem 1.05rem;
    line-height: 1.62;
}}
[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"])
    [data-testid="stChatMessageContent"] {{
    background: var(--accent-soft);
    border-color: rgba(124, 108, 255, 0.3);
}}
[data-testid="stChatMessageContent"] p:last-child {{ margin-bottom: 0; }}

[data-testid="stChatInput"] {{
    border-radius: var(--radius);
    border: 1px solid var(--border);
    background: var(--surface);
}}
[data-testid="stChatInput"]:focus-within {{
    border-color: var(--accent);
    box-shadow: 0 0 0 3px var(--accent-soft);
}}

/* ---------- empty state ---------- */
.empty {{
    border: 1px dashed var(--border); border-radius: var(--radius);
    padding: 2.1rem 1.6rem; text-align: center; margin: 1.2rem 0 1.6rem 0;
    background: rgba(255, 255, 255, 0.015);
}}
.empty-title {{ font-weight: 600; color: var(--ink); margin-bottom: 0.35rem; }}
.empty-text {{ color: var(--muted); font-size: 0.88rem; line-height: 1.6; }}

/* ---------- sidebar ---------- */
[data-testid="stSidebar"] {{
    background: #0A0E14; border-right: 1px solid var(--border);
}}
[data-testid="stSidebar"] .block-container {{ padding-top: 1.6rem; }}
.side-label {{
    font-size: 0.7rem; font-weight: 600; letter-spacing: 0.09em;
    text-transform: uppercase; color: var(--muted);
    margin: 1.4rem 0 0.6rem 0;
}}
.doc {{
    display: flex; align-items: center; gap: 0.6rem;
    background: var(--surface); border: 1px solid var(--border);
    border-radius: 10px; padding: 0.55rem 0.7rem; margin-bottom: 0.4rem;
    font-size: 0.82rem; color: var(--ink);
}}
.doc-name {{ overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}
.pill {{
    display: inline-flex; align-items: center; gap: 0.4rem;
    font-size: 0.72rem; font-weight: 500; padding: 0.24rem 0.6rem;
    border-radius: 999px; border: 1px solid var(--border); color: var(--muted);
}}
.pill-on {{
    color: #6EE7B7; border-color: rgba(110, 231, 183, 0.3);
    background: rgba(110, 231, 183, 0.08);
}}
.dot {{ width: 6px; height: 6px; border-radius: 50%; background: currentColor; }}

/* ---------- controls ---------- */
.stButton button {{
    border-radius: 10px; border: 1px solid var(--border);
    background: var(--surface); color: var(--ink);
    font-weight: 500; font-size: 0.85rem; transition: all 0.15s ease;
}}
.stButton button:hover {{
    border-color: var(--accent); color: #fff; background: var(--accent-soft);
}}
[data-testid="stFormSubmitButton"] button {{
    background: var(--accent); border: none; color: #fff;
    font-weight: 600; padding: 0.55rem 0;
}}
[data-testid="stFormSubmitButton"] button:hover {{
    background: #6A58FF; color: #fff;
}}

[data-testid="stFileUploaderDropzone"] {{
    background: var(--surface); border: 1px dashed var(--border);
    border-radius: 10px; padding: 0.9rem;
}}
[data-testid="stFileUploaderDropzone"]:hover {{ border-color: var(--accent); }}
/* The browse button stays: hiding it leaves drag-and-drop as the only way in,
   which is not obvious and is impossible on some setups. */
[data-testid="stFileUploaderDropzone"] button {{
    background: var(--accent-soft); border: 1px solid var(--border);
    color: var(--ink); font-size: 0.78rem; padding: 0.3rem 0.7rem;
}}
[data-testid="stFileUploaderDropzone"] button:hover {{
    border-color: var(--accent); background: var(--accent);
    color: #fff;
}}
[data-testid="stFileUploaderDropzoneInstructions"] span {{ font-size: 0.75rem; }}
[data-testid="stFileUploaderDropzoneInstructions"] small {{ font-size: 0.68rem; }}

input, [data-baseweb="input"] {{ border-radius: 10px !important; }}
[data-baseweb="input"]:focus-within {{
    border-color: var(--accent) !important;
    box-shadow: 0 0 0 3px var(--accent-soft) !important;
}}

[data-baseweb="tab-list"] {{ gap: 0.3rem; background: transparent; }}
[data-baseweb="tab"] {{
    border-radius: 9px; padding: 0.35rem 0.95rem; color: var(--muted);
}}
[data-baseweb="tab"][aria-selected="true"] {{
    background: var(--accent-soft); color: var(--ink);
}}
[data-baseweb="tab-highlight"], [data-baseweb="tab-border"] {{ display: none; }}

/* ---------- auth ---------- */
.auth-pad {{ height: 3.2rem; }}
</style>
"""


def inject() -> None:
    st.markdown(CSS, unsafe_allow_html=True)


def brand(subtitle: str) -> None:
    st.markdown(
        '<div class="brand"><div class="brand-mark">◆</div>'
        '<div class="brand-name">OmniAssist</div></div>'
        f'<div class="brand-sub">{subtitle}</div>',
        unsafe_allow_html=True,
    )
