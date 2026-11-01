# 🛠️ OmniAssist — BUILD LOG

> **What was built, in order.** Terse by design — for retracing steps, redoing a block, or verifying the process.
> For *why* each decision was made, see [LEARN_SHEET.md](LEARN_SHEET.md).

**Repo:** github.com/vikasgautam2003/OmniAssist · **Stack:** Python 3.12 · uv · FastAPI · Groq (free tier)

---

## 🗺️ ROADMAP

| Version | Adds | Status |
|---|---|---|
| **v0.1** | Streaming chatbot with history | ✅ **shipped** |
| **v0.2** | Postgres, auth, PDF upload + RAG, pytest | ✅ **shipped** `v0.2` |
| **v0.3** | Tool-use framework, Celery jobs, structured logging | ✅ **feature-complete** |
| v0.4 | Multi-tenancy, RBAC, Docker, AWS deploy, CD | 🔄 Block 1 done |
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

## ✅ v0.2 · BLOCK 2 — PostgreSQL

**Goal:** conversation history survives a restart, and lives outside the process.

```bash
brew install postgresql@17 pgvector && brew services start postgresql@17
createdb omniassist && psql omniassist -c 'CREATE EXTENSION IF NOT EXISTS vector;'
uv add sqlalchemy "psycopg[binary]" alembic
uv run alembic init migrations
```

**Files**

| File | Purpose |
|---|---|
| `app/domain.py` | `Message` — imports nothing, so a cycle is impossible |
| `app/repositories/base.py` | `ConversationRepository` Protocol |
| `app/repositories/memory.py` | in-memory implementation (unit tests) |
| `app/repositories/postgres.py` | SQL implementation |
| `app/db/models.py` | `Conversation`, `MessageRow` |
| `app/db/session.py` | cached engine + session factory |
| `migrations/` | Alembic; `env.py` reads the URL from `Settings` |

**Key points**
- **Two separate steps:** Protocol + in-memory first (a failing test means the *refactor* is wrong), then Postgres (a failing test means the *SQL* is wrong). Never both at once.
- Separate `messages` table, not a JSON column — JSON means loading the whole blob to read ten rows and rewriting it to append one
- `Index("ix_messages_conversation_created", "conversation_id", "created_at")` — every read is "this conversation, chronological, limited"
- `server_default=func.now()` + `timezone=True` — the database owns the clock
- `ON DELETE CASCADE` — the FK made a bug visible that the dict had hidden (it created parents implicitly)
- `INSERT ... ON CONFLICT DO NOTHING` for the parent row: `SELECT`-then-`INSERT` is a check-then-act race
- `ORDER BY created_at, id` — `now()` is the *transaction* start time, so timestamps alone are not a total order
- Engine cached per process: an `Engine` owns a connection pool, one per request exhausts Postgres
- `env.py` sets `sqlalchemy.url` from `Settings`, not `alembic.ini` — one source of truth, and no credential in version control

**Verify**
```bash
uv run alembic upgrade head
uv run alembic downgrade -1 && uv run alembic upgrade head   # reversibility
psql -P pager=off omniassist -c '\d messages'
```
Then send a message in one Python process and read it back in **another** — that is the proof, not a restart.

---

## ✅ v0.2 · BLOCK 3 — Authentication

**Goal:** conversations belong to someone. Until they do, anyone who guesses an ID reads another user's history.

```bash
uv add argon2-cffi pyjwt email-validator
```

**Files so far**

| File | Purpose |
|---|---|
| `app/security/password.py` | `hash_password` / `verify_password` (argon2id) |
| `app/security/tokens.py` | `create_access_token` / `decode_access_token` (HS256) |
| `app/db/models.py` | `UserRow` — UUID PK, unique email |
| `app/domain.py` | `User` frozen dataclass |
| `app/repositories/{base,memory,postgres}.py` | `UserRepository` + `EmailAlreadyExistsError` |

**Key points**
- Argon2id, not bcrypt: **memory-hard**, which denies GPU parallelism rather than only slowing each guess
- `verify_password` catches **only** `VerifyMismatchError`; `InvalidHashError` means corrupt data and must surface
- UUID PK for users — integers in URLs are enumerable and leak user count and signup order
- `unique=True` on email is the *guarantee*; the application's duplicate check is only the error message
- A JWT is **signed, not encrypted** — the payload is readable without the key. Pin `algorithms=["HS256"]`; never let the token choose.
- `EmailAlreadyExistsError` is raised by **both** repositories (Postgres translates `IntegrityError`), so no caller imports sqlalchemy and the fake stays behaviourally identical

**Steps 3.3c–3.6**

| File | Purpose |
|---|---|
| `app/schemas/auth.py` | request/response models; email normalised **once**, shared by signup and login |
| `app/routes/auth.py` | `POST /auth/signup` (201/409), `POST /auth/login` (200/401), `GET /auth/me` |
| `app/routes/deps.py` | `get_current_user` + the `CurrentUser` alias |
| `migrations/…add_user_id…` | `conversations.user_id` FK (deletes orphan rows first) |
| `ui/streamlit_app.py` | auth gate, token in `session_state`, 401 → re-login |

**Key points**
- Login returns an identical 401 for unknown-email and wrong-password, **and** verifies against a throwaway hash when the user is missing — otherwise the ~2 ms vs ~53 ms difference reveals which emails exist
- `HTTPBearer(auto_error=False)`: FastAPI's default 403 is the wrong code for a missing header
- The user is **looked up**, not trusted from the token — a JWT cannot be revoked before it expires
- Ownership lives in the repository's `WHERE` clause, never a check beside the query
- Another user's conversation returns **404**, never 403
- The `ON CONFLICT DO NOTHING` upsert became unsafe once the row had an owner — it now verifies ownership in the same transaction
- 🔴 `stream_reply` is **not** a generator: it was, so the route's `except` wrapped a call that ran nothing and the ownership check fired mid-stream, too late for a 404

**Verify**
```bash
uv run pytest                                  # 8 tests, no DB, no key
uv run uvicorn app.main:app --reload --port 8000
uv run streamlit run ui/streamlit_app.py
```
Sign up in one browser, sign up in a private window, and confirm neither can see the other's conversation.

---

## ✅ v0.2 · BLOCK 4 — RAG (retrieval-augmented generation)

**Goal:** upload a PDF and ask questions about it. The assistant answers from *your* document, not from its training data.

```bash
uv add pypdf fastembed pgvector
```

**The pipeline**

```
PDF ──extract──► text ──chunk──► passages ──embed──► vectors ──store──► pgvector
                                                                            │
question ──embed──► similarity search ◄─────────────────────────────────────┘
                           │
                    top-k passages ──► grounded prompt ──► LLM ──► streamed answer
```

**Step 4.1 — PDF to text**

| File | Purpose |
|---|---|
| `app/services/pdf.py` | `extract_text(bytes)` + `PdfExtractionError` |
| `tests/fakes.py` | `make_pdf()` — a real PDF assembled byte by byte, no reportlab |

- Takes **bytes**, not a path or an upload object: no filesystem, no HTTP, testable in one line
- One `except PyPdfError` contains all fourteen of the library's error types — they share a base class
- A document with **no text layer** (a scan) is rejected with an OCR hint. An upload that appears to succeed while storing nothing is a worse failure than an error.

**Step 4.2 — Chunking**

| File | Purpose |
|---|---|
| `app/services/chunking.py` | `chunk_text(text, *, size, overlap)` |
| `app/config.py` | `chunk_size=1000`, `chunk_overlap=150` |

- Keyword-only arguments: `chunk_text(body, 150, 1000)` type-checks perfectly and silently produces garbage
- Boundary preference paragraph → line → sentence → space, restricted to the **last fifth** of the window so one early space cannot produce a 7-character chunk
- 🔴 **Review caught silent data loss.** `start += size - overlap` ignored the boundary-adjusted `end`; 32 of 45 characters vanished with no error. Fixed with `start = max(end - overlap, start + 1)`. The test that found it asserts *conservation* — no input text is lost — not behaviour.

**Step 4.3 — Embeddings**

| File | Purpose |
|---|---|
| `app/embeddings/base.py` | `Embedder` protocol, `EmbeddingError`, `EMBEDDING_DIMENSIONS` |
| `app/embeddings/local.py` | `LocalEmbedder` — `bge-small-en-v1.5` via fastembed, 384 dims |
| `app/embeddings/factory.py` | `get_embedder()`, cached |
| `tests/fakes.py` | `FakeEmbedder` — deterministic vectors from a hash |

- **Embedders are not interchangeable like LLM providers.** Dimensions differ, and even at equal width the semantic spaces differ — a mismatch returns plausible nonsense, not an error. Hence `dimensions` (schema derived, not guessed) and `model_id` (stale vectors detectable).
- Queries and documents are embedded by **separate methods**: bge wants an instruction prefix on queries only
- `LocalEmbedder` is imported **inside** the factory, so importing the factory does not load onnxruntime. No test constructs it — CI never downloads the 130 MB model.

**Step 4.4 — Vector storage**

| File | Purpose |
|---|---|
| `app/db/models.py` | `DocumentChunk` — `vector(384)`, `document_name`, `chunk_index`, `model_id` |
| `app/repositories/{base,memory,postgres}.py` | `ChunkRepository` + both implementations |
| `migrations/…create_document_chunks.py` | **hand-written** |

- Autogenerate would never emit `CREATE EXTENSION IF NOT EXISTS vector` — it diffs models and has no concept of a missing extension
- The width is a literal in the migration on purpose: a migration must build the same schema a year from now, so it cannot read today's config
- **No vector index yet.** HNSW and IVFFlat are both approximate; a sequential scan at this scale is exact and fast, and IVFFlat built on an empty table locks in poor recall.
- `search()` filters by `user_id` **inside the query** — unscoped retrieval answers one user from another's documents
- Cosine distance (`<=>`) because that is what the model was trained for; a different operator ranks worse with no error

**Step 4.5 — Retrieval into chat**

| File | Purpose |
|---|---|
| `app/services/retrieval.py` | `Retriever.find(user_id, question)` |
| `app/services/chat.py` | optional retriever; grounded system message |
| `app/config.py` | `retrieval_top_k=4` |

- **The augmented prompt is never stored.** History keeps the raw question: storing passages would grow history by thousands of characters per turn and re-send context retrieved for an older question.
- Nothing retrieved → prompt untouched. An empty context block makes the assistant refuse questions it could answer.
- The grounding instruction's third line — *say so plainly when the passages do not contain the answer* — is most of the difference between RAG and a chatbot that was shown some text
- ⚠️ **Prompt injection is unmitigated and logged as D32.** Retrieved text enters the prompt and the model cannot tell instructions from data.

**🔴 Incident — `main` broken by an automatic branch update**

GitHub's **"Update branch"** button merged `main` into the feature branch and resolved five files in `main`'s favour, discarding the Step 4.4 changes to them. PR #15 squashed *that* merge commit rather than the pushed work, so `main` stopped importing entirely: `db/models.py` imports `EMBEDDING_DIMENSIONS`, which `embeddings/base.py` no longer defined.

CI reported `failure` on `main` for **two consecutive merges** and nobody looked. See C80 and C81.

---

## 🔄 v0.3 — Tool use (design done, build pending)

**Design:** `DESIGN_v0.3.md`, written before any code. The questions it settles
— how tools are declared, how the loop is bounded, why streaming and tools
conflict, what a failing tool does, and that `Message` must stop being a dict —
each change the shape of code in three layers at once.

**The hinge of the whole project.** Today a new capability is new application
code. After Block 1 it is a new *tool*, which is why blocks 2–4 are hours each
rather than days.

**Why this order.** Block 1 first because everything after it is a *tool*, and
a tool cannot exist before the thing that runs tools. Blocks 2–4 next, because
each is small once the framework exists and together they prove the claim that
capabilities became cheap. Block 5 (queue) after the tools, because the queue
only matters once something slow exists to put in it. Block 6 (logging) last,
because it instruments everything before it — written earlier, it would have to
be revised after every block.

| # | Block | Status |
|---|-------|--------|
| 1 | Tool-use framework: `Tool` protocol, registry, bounded loop, `Message` refactor | ✅ |
| 2 | Document generation (PDF) as a tool | ✅ |
| 3 | Spreadsheet generation (Excel) as a tool | ✅ |
| 4 | Charts as a tool | ✅ |
| 5 | Background jobs — Celery + Redis; moves indexing out of the request (D36) | ✅ |
| 6 | Structured logging — latency, tokens and cost per request | ✅ |

**Decisions already taken (D38–D42):** tools declared vendor-neutrally in JSON
Schema with the adapter translating · the loop bounded by `max_tool_iterations`
· tool loop runs non-streaming, only the final answer streams · `Message`
becomes a dataclass carrying tool fields · **no tool with side effects in Block
1**, because a tool catalogue turns prompt injection from speech into action
(C90).

---

### Block 1 — the framework ✅

**Why first:** every later capability is a tool, and a tool cannot exist before
the thing that runs tools. Done in two commits on purpose — the `Message`
refactor has no behaviour change, so if the loop misbehaves later `git bisect`
can tell the two apart.

**Files**

| File | Purpose |
|---|---|
| `app/tools/base.py` | `Tool` protocol, `ToolSpec`, `ToolError` |
| `app/tools/registry.py` | name → tool; runs calls and **never raises** |
| `app/tools/calculator.py` | the first tool — pure, AST-whitelisted |
| `app/clients/base.py` | `StreamEvent`; `stream_chat` takes a catalogue |
| `app/clients/groq_client.py` | `tool_to_wire()` + tool-call accumulation |
| `app/services/chat.py` | the bounded loop (`_stream`, `_turn`) |
| `app/domain.py` | `Message` dataclass + `ToolCall` (earlier commit) |

**Key points**
- **D40 superseded by D44 during implementation.** Streaming and tool detection
  happen in one pass: ending the loop leaves you holding the final text, so
  "stream it afterwards" means regenerating it or faking it
- Providers send tool calls **in fragments keyed by `index`** — id and name
  first, arguments a few characters at a time. One accumulator reassembles them
- `ToolRegistry.run()` **never raises**: a bad tool call is the model's problem
  to recover from, not a 500 for a user who did nothing wrong
- The calculator **parses to an AST and whitelists node types**. `eval()` would
  be remote code execution, and the input can come from an uploaded PDF
- `2 ** 10_000_000` is plain arithmetic that hangs the process — the exponent is
  capped, which is cheaper than a timeout
- The loop is bounded by `max_tool_iterations`; on exhaustion the model is told
  to stop, so the user gets an answer rather than a request that dies

**Verify**
```bash
uv run pytest                      # 79 tests
# live: the model calls the tool and uses the result
uv run python -c "..."             # 48271 * 9183 -> 443272593 ✓
```

---

### Blocks 2–4 — three generator tools ✅

**Why together:** they exist to *prove* the framework's claim. If adding a
capability is still expensive, Block 1 did not work. Built in one sitting, which
is the evidence.

**Why Block 2 carries the shared piece.** All three produce files, and a tool
returns a string — so the artifact store had to exist before the first of them.
Built once in Block 2; Blocks 3 and 4 reuse it unchanged.

**Files**

| File | Purpose |
|---|---|
| `app/artifacts/{base,postgres,memory}.py` | `ArtifactStore` protocol and implementations |
| `app/db/models.py` | `ArtifactRow` + migration `409f9e6d475e` |
| `app/tools/artifacts.py` | `safe_filename()`, `store()`, `rows_from()` — shared by all three |
| `app/tools/documents.py` | `create_document` (fpdf2) |
| `app/tools/spreadsheets.py` | `create_spreadsheet` (openpyxl) |
| `app/tools/charts.py` | `create_chart` (matplotlib) |
| `app/routes/artifacts.py` | `GET /artifacts/{id}`, scoped to the owner |
| `app/tools/base.py` | `ToolContext` added to the protocol |

**Key points**
- **The bytes never enter the conversation.** Base64 would be re-sent to the
  model every later turn — roughly 70k tokens for a 200 KB PDF it cannot read
- **`ToolContext` is passed by the service, never by the model.** Identity
  cannot be a JSON argument the model composes
- Artifacts live in **PostgreSQL**: a container filesystem is ephemeral, and
  bytes in a column cannot be path-traversed. S3 in v0.4 is one file
- Three outputs, three injections: spreadsheet **formulas** (`=`), filename
  **header injection**, PDF **latin-1** limits
- `matplotlib.use("Agg")` before importing pyplot, and `plt.close()` in a
  `finally` — pyplot holds every figure until closed

**Verify**
```bash
uv run pytest                       # 97 tests
```
Live: one question produced a bar chart *and* a spreadsheet, the model choosing
both tools in a single turn.

---

### Block 5 — background jobs ✅

**Why after the tools, not before:** a queue only matters once something slow
exists to put in it. Indexing was the slow thing all along, but building the
queue first would have meant designing it against a guess.

**Files**

| File | Purpose |
|---|---|
| `app/jobs/celery_app.py` | the Celery app; broker, serialisation, pool |
| `app/jobs/indexing.py` | the work as a **plain function**, plus a thin task wrapper |
| `app/routes/documents.py` | upload now returns **202 + job id**; `/documents/jobs/{id}` |
| `ui/streamlit_app.py` | polls the job instead of holding the request |
| `app/config.py` | `redis_url` |

**Measured**

| | Before | After |
|---|---|---|
| Request returns in | ~27s | **0.06s** |
| Work takes | 27s | 27s |

Nothing got faster — the *wait* moved. Worth stating plainly.

**Key points**
- The upload is **stored first and only an id is queued**: Redis holds payloads
  in memory and is not a file store
- The work is a plain function; the task decorator only parses UUIDs and
  delegates, so four tests run it with no broker and no Redis
- The job **re-checks ownership**: task arguments travel through a broker and
  must not be trusted more than a request
- `task_acks_late=True` — a worker killed mid-task would otherwise lose the job

**Three bugs only a running worker found**
1. `NotRegistered` — the worker imports the app module, not the tasks module;
   fixed with `include=[...]`
2. macOS fork safety — prefork children start with an empty registry; pool is
   now chosen by platform
3. An **import-time `get_settings()`** that stopped the suite running without
   `.env`, breaking the invariant from D5 — with a comment above it claiming
   the opposite

**Verify**
```bash
brew services start redis
uv run celery -A app.jobs.celery_app:celery_app worker --loglevel=info
uv run pytest        # 104 tests, and still green with no .env
```

---

### Block 6 — structured logging ✅ — v0.3 complete

**Why last:** it instruments everything before it. Written earlier it would
have been revised after every block, and the fields worth logging were not
knowable until the tools and the queue existed.

**Files**

| File | Purpose |
|---|---|
| `app/observability/logging.py` | structlog config, `new_request()`, `bind()` |
| `app/observability/middleware.py` | per-request log line + `X-Request-ID` |
| `app/clients/groq_client.py` | tokens, cost, duration, provider queue time |
| `app/tools/registry.py` | tool name, outcome, duration — **never arguments** |
| `app/jobs/indexing.py` | its own correlation scope; outcome and duration |

**What one question now produces**

```
llm.call   prompt_tokens=178 completion_tokens=48 duration_ms=595.8
           provider_queue_ms=49.7 tools_requested=true
tool.call  tool=calculate outcome=ok duration_ms=0.2
llm.call   prompt_tokens=209 completion_tokens=26 duration_ms=362.8
           provider_queue_ms=210.8 tools_requested=false
```

All three share one `request_id` and `user_id`, bound once by context variable
rather than threaded through every signature.

**Key points**
- **Cost is computed although the rate is zero.** The field exists so token
  counts become money the moment a paid provider is configured, and v1.0 needs
  the history, which cannot be back-filled
- **Tool arguments are never logged** — a model composes them from document
  text, which may be private. There is a test asserting it
- `/healthz` is quiet: 8,640 lines a day saying nothing is a log nobody skims
- Groq attaches `usage` to the final chunk **by default**; OpenAI needs
  `stream_options`. That difference lives in the adapter, like every other one
- A **job starts its own correlation scope** — it has no request to inherit

**Verify**
```bash
uv run pytest           # 110 tests, green with no key, no database, no Redis
```

---

## 🔄 v0.4 — Multi-tenancy and deployment

**Design:** `DESIGN_v0.4.md`, written before any code.

**Why this order.** Block 1 first because it touches every table and every
query — anything built before it gets revised after. The tools next, because
web search is the first *dangerous* tool and needs its own review. The React
front end **third, not first**: it is the most visible block and the most
tempting to start with, which is exactly why it waits, because a UI written
against a single-user API gets built twice. Docker fourth (nothing to package
until the above works), AWS last (the only step that cannot be verified
locally).

| # | Block | Status |
|---|-------|--------|
| 1 | Multi-tenancy + RBAC | ✅ |
| 2 | Web search + image generation tools | ⬜ |
| 3 | React front end | ⬜ |
| 4 | Docker | ⬜ |
| 5 | AWS + CD | ⬜ |

### Block 1 — multi-tenancy and RBAC ✅

**Files**

| File | Purpose |
|---|---|
| `app/domain.py` | `Role`, `Organisation`, `Membership`, `Principal`, **`Scope`** |
| `app/db/models.py` | `organisations`, `memberships`, `organisation_id` on three tables |
| `migrations/…005a57e99cd0` | create, **backfill**, then `NOT NULL` |
| `app/repositories/organisations.py` | real implementation |
| `app/repositories/memory_organisations.py` | the test double |
| `app/routes/deps.py` | `CurrentPrincipal`, `CanManageMembers` |
| `app/routes/organisations.py` | roster and member management |

**Key points**
- **`Scope` carries the boundary** — one dataclass instead of two more
  parameters on ~20 methods, and it deliberately holds no role
- **Isolation in the query, authorisation in the route.** Forgetting isolation
  is a data breach; authorisation is about the action, and the route names it
- **Documents are shared across an organisation, conversations are not**
- The migration **creates an organisation per existing user, backfills, then
  sets NOT NULL**. In production that is three deploys; one is safe here only
  because no old code is running
- Verified: 14 organisations, 112 rows backfilled, **none left untenanted**

**Two things found by running it, not by testing it**
1. Signup's personal workspace made every invitation impossible — one-org-per-
   user and auto-create cannot both hold (C107)
2. The previous block's artifact fix had **never reached `main`**: `git push -q`
   hid the confirmation and the pull request merged the commit before it (C110)

**Verify**
```bash
uv run pytest        # 126 tests, green with no key, no database, no Redis
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
