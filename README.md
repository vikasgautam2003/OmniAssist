# 🤖 OmniAssist

A streaming AI assistant built as a **production engineering exercise** — one codebase evolved release by release, with the operational discipline each stage actually requires.

**v0.1** — streaming chat with conversation memory, behind a provider-agnostic LLM layer.

---

## Why this exists

Most open-source AI assistants are demos: no persistence, no tenancy, no observability, no cost control, no CI. This project builds the same capability *with* those concerns, adding each one at the version where it becomes necessary rather than all at once.

---

## Architecture

```
┌──────────────┐     HTTP      ┌──────────────┐    HTTPS    ┌──────────┐
│  Streamlit   │──────────────▶│   FastAPI    │────────────▶│ Provider │
│     UI       │◀── SSE ───────│   backend    │◀── stream ──│  (Groq)  │
└──────────────┘               └──────┬───────┘             └──────────┘
                                      │
                               conversation store
                                (in-memory, v0.1)
```

**Layering — dependencies point one way only:**

```
routes/  ──▶  services/  ──▶  clients/
 HTTP        business logic    vendor SDK
```

- `services/` knows nothing about HTTP → testable with no server
- `clients/` knows nothing about the app → swappable for any vendor
- exactly one file imports the provider SDK

The UI never holds an API key: it calls this backend, which calls the provider. That single choke point is where auth, rate limiting, cost tracking and caching will live in later versions.

---

## Quickstart

**Prerequisites:** [uv](https://docs.astral.sh/uv/), and a free API key from [console.groq.com](https://console.groq.com)

```bash
git clone https://github.com/vikasgautam2003/OmniAssist.git
cd OmniAssist
uv sync

cp .env.example .env
# edit .env and paste your key
```

**Run the backend:**
```bash
uv run uvicorn app.main:app --reload --port 8000
```

**Run the UI** (second terminal):
```bash
uv run streamlit run ui/streamlit_app.py
```

Open http://localhost:8501

---

## API

| Method | Path | Returns |
|---|---|---|
| `GET` | `/healthz` | `{"status": "ok"}` — liveness only; makes no provider call |
| `POST` | `/chat/{conversation_id}` | `text/event-stream` — reply streamed as SSE |
| `GET` | `/docs` | Interactive OpenAPI documentation |

```bash
curl -N -X POST localhost:8000/chat/demo \
  -H 'Content-Type: application/json' \
  -d '{"message":"Count from 1 to 5"}'
```

```
data: "1"

data: "2"

data: [DONE]
```

SSE payloads are JSON-encoded — model output contains newlines, and a raw newline would terminate the frame early.

---

## Configuration

All configuration comes from the environment and is validated at import. A missing or invalid value **prevents the process from starting** rather than failing on the first user request.

| Variable | Required | Default |
|---|---|---|
| `LLM_API_KEY` | ✅ | — |
| `LLM_PROVIDER` | | `groq` |
| `LLM_MODEL` | | `openai/gpt-oss-120b` |
| `MAX_TOKENS` | | `4096` |
| `APP_ENV` | | `local` |

`LLM_PROVIDER` and `APP_ENV` are `Literal`-constrained, so a typo is rejected at startup with the valid options listed. The API key is a `SecretStr` and never appears in logs or tracebacks.

---

## Project structure

```
app/
├── config.py            typed settings, fail-fast at import
├── main.py              FastAPI app + /healthz
├── routes/chat.py       HTTP layer, SSE framing
├── services/chat.py     history, trimming, accumulation
└── clients/
    ├── base.py          LLMClient Protocol, LLMError — no vendor imports
    ├── groq_client.py   the only file that imports groq
    └── factory.py       composition root
tests/fakes.py           keyless fake client
ui/streamlit_app.py      chat interface
```

---

## Development

```bash
uv run ruff format app/ tests/ ui/     # layout
uv run ruff check --fix app/ tests/ ui/ # lint
uv run mypy app/ tests/ ui/             # types
```

CI runs all three on every push and pull request — **without an API key**. Nothing in the pipeline calls a paid service.

---

## Deliberately not in v0.1

Listed because knowing what's missing matters as much as what's present:

| Missing | Arrives in | Why not now |
|---|---|---|
| Persistence | v0.2 | History lives in process memory and dies on restart — by design, to make the need concrete |
| Authentication | v0.2 | No users yet |
| Automated tests | v0.2 | The fake client and injectable layers exist so they can be added without refactoring |
| Tool use, PDFs, data analysis | v0.3 | The client abstraction is the foundation they build on |
| Docker, cloud deploy | v0.4 | Nothing to deploy until there's something worth running |
| Monitoring, evals, cost tracking | v1.0 | Meaningful only with real traffic |

---

## Roadmap

| Version | Adds |
|---|---|
| **v0.1** ✅ | Streaming chat with conversation memory |
| v0.2 | PostgreSQL, auth, PDF upload + RAG, pytest |
| v0.3 | Tool-use framework, Redis, background jobs, structured logging |
| v0.4 | Multi-tenancy, RBAC, Docker, AWS, continuous deployment |
| v1.0 | Monitoring, alerting, LLM evals, load testing, cost tracking |

Design rationale is recorded in [LEARN_SHEET.md](LEARN_SHEET.md); the build sequence in [BUILD_LOG.md](BUILD_LOG.md).
