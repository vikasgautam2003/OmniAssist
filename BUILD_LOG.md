# 🛠️ OmniAssist — BUILD LOG

> **What was built, in order.** Terse by design — for retracing steps, redoing a block, or verifying the process.
> For *why* each decision was made, see [LEARN_SHEET.md](LEARN_SHEET.md).

**Repo:** github.com/vikasgautam2003/OmniAssist · **Stack:** Python 3.12 · uv · FastAPI · Groq (free tier)

---

## 🗺️ ROADMAP

| Version | Adds | Status |
|---|---|---|
| **v0.1** | Streaming chatbot with history | ✅ **shipped** |
| v0.2 | Postgres, auth, PDF upload + RAG, pytest | 🔄 in progress |
| v0.3 | Tool-use framework, Redis cache, Celery jobs, structured logging | ⬜ |
| v0.4 | Multi-tenancy, RBAC, Docker, AWS deploy, CD | ⬜ |
| v1.0 | Monitoring, alerting, LLM evals, load testing, cost tracking | ⬜ |

### v0.1 blocks

| # | Block | Status |
|---|---|---|
| 1 | Repo skeleton + config & secrets | ✅ |
| 2 | LLM client layer (Protocol + adapter + factory) | ✅ |
| 3 | Streaming | ✅ |
| 4 | FastAPI + SSE + conversation history | ✅ |
| 5 | Streamlit UI | ✅ |
| 6 | GitHub Actions CI + README + tag `v0.1` | ✅ |

---

## ✅ BLOCK 1 — Repo skeleton, config & secrets

**Goal:** a project that refuses to start if misconfigured, and cannot leak its API key.

```bash
uv init . --python 3.12
uv add pydantic-settings
uv add --dev ruff mypy
mkdir -p app/routes app/services app/clients tests
touch app/__init__.py app/{routes,services,clients}/__init__.py tests/.gitkeep
```

**Files**

| File | Purpose |
|---|---|
| `pyproject.toml` | manifest + dependency groups (runtime vs `--dev`) |
| `uv.lock` | exact resolved tree — **committed** |
| `.python-version` | pins 3.12 |
| `.gitignore` | `.env`, `.venv/`, `__pycache__`, caches |
| `.env` | real secrets — **never committed** |
| `.env.example` | same keys, fake values — **committed** |
| `app/config.py` | `Settings(BaseSettings)` + module-level `settings = Settings()` |

**Key points**
- `llm_api_key: SecretStr` — no default (required), never prints in logs or tracebacks
- `llm_provider` / `app_env` are `Literal[...]` — typos rejected at startup, not at runtime
- `settings = Settings()` at module level → validation runs at **import**

**Verify**
```bash
uv run python -c "from app.config import settings; print(settings.llm_provider)"   # loads
mv .env .env.bak && uv run python -c "from app.config import settings"; mv .env.bak .env   # must ValidationError
```

---

## ✅ BLOCK 2 — LLM client layer

**Goal:** the provider becomes a config value, not a code dependency.

```bash
uv add groq
```

**Files**

| File | Purpose |
|---|---|
| `app/clients/base.py` | `Message`, `LLMError`, `LLMClient` Protocol — **zero vendor imports** |
| `app/clients/groq_client.py` | the adapter — **the only file importing `groq`** |
| `app/clients/factory.py` | composition root: reads `settings`, returns an `LLMClient` |
| `tests/fakes.py` | `FakeLLMClient` — no key, no network, no inheritance |

**Key points**
- `Protocol` over `ABC` so the fake conforms without inheriting
- Config is **injected via constructor** — the client never imports `settings`
- `max_retries` set explicitly (SDK default is 2 — one call can be three requests)
- `content` is `str | None` → raise `LLMError` when `None`
- Factory returns `-> LLMClient`, not `-> GroqClient`

**Verify**
```bash
uv run python -c "
from app.clients.factory import get_llm_client
print(get_llm_client().chat([{'role':'user','content':'Reply with exactly: OK'}]))"
```

---

## ✅ BLOCK 3 — Streaming

**Goal:** token-by-token output.

**Changes**

| File | Change |
|---|---|
| `app/clients/base.py` | `stream_chat(messages) -> Iterator[str]` added to the Protocol |
| `app/clients/groq_client.py` | `stream=True`; reads `chunk.choices[0].delta.content` |
| `tests/fakes.py` | streams fixed-size chunks; eager/lazy split |

**Key points**
- Separate method, **not** `chat(stream=True)` — a flag would make the return type depend on an argument value
- Streaming path uses **`delta.content`**, not `message.content`
- `None` here is **routine** (role-only first chunk, finish-reason last chunk) → skip, don't raise
- Fake must satisfy `"".join(stream_chat(m)) == chat(m)`
- Eager work (recording the call) goes in a plain function that *returns* the generator

**Verify**
```bash
uv run python -c "
from app.clients.factory import get_llm_client
for p in get_llm_client().stream_chat([{'role':'user','content':'Count to 5'}]):
    print(p, end='', flush=True)"
```

---

## ✅ BLOCK 4 — FastAPI + SSE + history

**Goal:** a real HTTP API that remembers the conversation.

```bash
uv add fastapi "uvicorn[standard]"
```

**Files**

| File | Purpose |
|---|---|
| `app/main.py` | FastAPI app, router wiring, `GET /healthz` |
| `app/routes/chat.py` | `POST /chat/{conversation_id}` → `StreamingResponse` (SSE) |
| `app/services/chat.py` | `ChatService` — history store, trimming, accumulation |

**Request flow**
```
POST /chat/{id} → routes (validate) → service (history + trim)
                → client (stream=True) → chunks
                → service (collect + yield) → routes (SSE frame) → client
                → on completion: full reply appended to history
```

**Key points**
- `data: {json.dumps(chunk)}\n\n` — **JSON-encode**, or a newline in model output ends the SSE frame early
- `data: [DONE]\n\n` sentinel — SSE has no built-in end marker
- `X-Accel-Buffering: no` — or nginx buffers the stream and streaming breaks *only in production*
- `/healthz` makes **no provider call** — a 10s LB probe is 8,640 req/day vs a ~1,000/day free tier
- `_service` is a module-level singleton — history survives between requests (dies on restart: that's v0.2's job)
- Trimming limits what is **sent**; full history stays in the store

**Verify**
```bash
uv run uvicorn app.main:app --reload --port 8000

curl -s localhost:8000/healthz
curl -N -X POST localhost:8000/chat/c1 -H 'Content-Type: application/json' -d '{"message":"Count from 1 to 5"}'
curl -N -X POST localhost:8000/chat/c1 -H 'Content-Type: application/json' -d '{"message":"What number did you stop at?"}'
```
Second call must answer **5** — that proves history works end to end.
(`-N` disables curl buffering; without it you see nothing until the end.)

---

## ✅ BLOCK 5 — Streamlit UI

**Goal:** a chat interface that talks to our API — never to the provider.

```bash
uv add streamlit httpx
mkdir -p ui
```

**Files**

| File | Purpose |
|---|---|
| `ui/streamlit_app.py` | chat UI; parses SSE from the backend |

**Key points**
- ⚠️ **Streamlit re-runs the entire script on every interaction.** Module-level code runs again each time; local variables are wiped.
- `st.session_state` is the only thing that survives a re-run — holds `conversation_id` and `messages`
- Past messages must be **redrawn** every run (the replay loop) — Streamlit doesn't remember what it painted
- `timeout=None` on `httpx.stream` — a default timeout kills long replies mid-flight
- `st.write_stream(gen)` renders token by token **and returns the full text** to store
- UI holds **no API key** — it calls our FastAPI, which calls the provider (single choke point)
- Named `streamlit_app.py`, not `app.py`: `ui/app.py` collides with the `app/` package (both resolve to module `app`) and mypy refuses

**Verify**
```bash
uv run uvicorn app.main:app --reload --port 8000     # terminal 1
uv run streamlit run ui/streamlit_app.py             # terminal 2
```
1. "Count from 1 to 5" → appears progressively
2. "What number did you stop at?" → answers 5
3. Refresh → new `conversation_id`; the old conversation is stranded in server memory forever (that's what v0.2's database fixes)

## ✅ BLOCK 6 — CI + README + release

**Goal:** the quality gate runs on a machine, not on discipline.

**Files**

| File | Purpose |
|---|---|
| `.github/workflows/ci.yml` | format → lint → types, on push to main and every PR |
| `README.md` | problem, architecture, quickstart, API, what's deliberately missing |

**Key points**
- `uv sync --locked` installs **exactly** `uv.lock` and **fails if the lock is stale** — nobody can add a dependency without committing the lockfile (D2's payoff)
- **No secrets in the workflow.** None of the three tools imports the code, so no API key is needed (D5) — verified locally with `.env` moved away
- Triggers on **both** `push: main` and `pull_request`: the PR run catches problems before merge, the main run records whether main is healthy
- Three **named** steps, not one combined command — a failure shows as `Lint ✗` instead of a log to scan
- Tag with `git tag -a v0.1`: branches move, tags don't. v0.4's pipeline deploys and rolls back to tags — **you can't roll back to a branch**

**Verify**
```bash
uv sync --locked
mv .env .env.bak
env -u LLM_API_KEY -u GROQ_API_KEY sh -c '
uv run ruff format --check app/ tests/ ui/
uv run ruff check app/ tests/ ui/
uv run mypy app/ tests/ ui/'
mv .env.bak .env
gh run list --limit 2       # both runs green
```

---

## ✅ v0.2 · BLOCK 1 — pytest and the safety net

**Goal:** lock down current behaviour *before* the storage layer is replaced.

```bash
uv add --dev pytest pytest-cov
touch tests/__init__.py
```

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["."]
addopts = "-q"
```

**Files**

| File | Purpose |
|---|---|
| `tests/test_chat_service.py` | 5 tests: streaming, history accumulation, trimming cap, full-history retention, copy-on-read |
| `tests/__init__.py` | makes `tests` a real package — without it mypy sees `fakes` and `tests.fakes` as two modules |
| `.github/workflows/ci.yml` | `Tests` step added |

**Key points**
- Tests use `FakeLLMClient` — **no network, no key, ~0.01s**; verified passing with `.env` moved away
- Assert on **what the provider received** (`fake.calls[-1]`), never on `service._store` — implementation assertions break during the very refactor they should protect
- Trimming gets **two** tests: one for the cap, one proving the cap wasn't achieved by deleting data
- `get_history()` returns `list(...)` — a copy. The live list let callers corrupt internal state, and would have behaved differently once backed by SQL
- `pythonpath = ["."]` so `app.*` and `tests.*` both resolve without `sys.path` hacks in test files

**Verify**
```bash
uv run pytest
mv .env .env.bak && env -u LLM_API_KEY uv run pytest; mv .env.bak .env
```

---

## 🔁 STANDARD WORKFLOW (every block)

```bash
git checkout main && git pull
git checkout -b feat/block-N-name
# ... build ...
uv run ruff format app/ tests/
uv run ruff check --fix app/ tests/
uv run mypy app/ tests/
git add -A && git status --short          # confirm .env is NOT listed
git commit -m "feat: ..."
git push -u origin feat/block-N-name
gh pr create --fill
gh pr merge --squash --delete-branch
git checkout main && git pull             # don't skip this
```

**Quality gate — all three, every time:**
```bash
uv run ruff format --check app/ tests/    # layout
uv run ruff check app/ tests/             # lint (import order, unused vars)
uv run mypy app/ tests/                   # types
```
`ruff format` and `ruff check` are **different tools with different jobs**. Passing one says nothing about the other.
