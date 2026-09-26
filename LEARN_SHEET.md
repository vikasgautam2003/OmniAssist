# 📚 OmniAssist — LEARN SHEET

**Owner:** Vikas · **Started:** 2026-08-02 · **Current version:** v0.1 · **Status:** v0.1 shipped ✅ · **v0.2 in progress** — Block 1 (tests) complete
**v0.1:** 🎉 **SHIPPED** — all 6 blocks complete, CI green, tagged `v0.1`

> Every concept learned, every decision made, and *why*. Append-only — superseded entries are struck through, never deleted, because the reasoning trail is worth more than a tidy document.

---

## 🗂️ DECISION LOG

| # | Decision | Why | Reversible? |
|---|----------|-----|-------------|
| **D1** | Flagship project = **OmniAssist**, one evolving codebase Aug→Dec | Real engineering is ~90% working in an existing codebase. Three greenfield toys don't teach that; one evolving system does. | No — this is the program |
| **D2** | Dependency tool = **`uv`** | 10–100× faster than pip, but the real reason is the **lockfile by default** → reproducible builds, a hard CI/CD requirement later. Replaces venv + pip + pip-tools + pyenv. | Yes, but painful |
| **D3** | **Model/provider lives in `.env`, never in code** | Switching models becomes a deploy, not a diff. Paid off within 48 hours (see D10). | n/a — principle |
| **D4** | **CI moves from v0.4 → v0.1** | *CI is necessary the moment code exists. CD is necessary the moment there's somewhere to deploy.* Lint/format/type-check now; tests v0.2; build+deploy v0.4. | No |
| **D5** | **CI must never require a live `LLM_API_KEY`** | A pipeline calling the live API is expensive (tokens per PR), flaky (network blip → red build → you start ignoring red builds → CI is now worthless), and a leak surface (real key in every fork's CI). | No — constraint |
| **D6** | Consequence of D5: **LLM client must be injectable** from Block 2 | So tests can substitute a fake. Design decisions in week one are what make week twelve possible. | No |
| **D7** | v0.1 stores conversation state in an **in-process dict** — deliberately inadequate | You must *feel* the failure (restart = amnesia; multi-instance = amnesia) before Postgres in v0.2 means anything. | Yes — that's v0.2 |
| **D8** | **LLM access sits behind a narrow interface in `app/clients/`** — provider is config, not a code dependency | Surveyed 18 models across 6 vendors; prices move monthly, free tiers vary wildly. The senior answer isn't "pick the right vendor," it's "make the vendor swappable." Also satisfies D6 and enables cost/capability routing in v1.0. **Interview story: *"my LLM layer is provider-agnostic and I route by cost/capability"* beats any vendor name.** | No — this is the design |
| ~~D9~~ | ~~Dev model = `claude-haiku-4-5`~~ | *Superseded by D10 (budget = $0). Kept for the reasoning trail.* | — |
| **D10** | **v0.1 runs on Groq free tier — `llama-3.3-70b-versatile`** | Budget is $0. Groq = ~1,000 req/day, 30 RPM, **no credit card, ongoing**; Anthropic has no free tier. v0.1 needs ~200 requests total. ⚠️ **Groq ≠ Grok** — Groq is an inference provider serving open-weight models (free); Grok is xAI's model ($25 credits then paid). Config is provider-neutral: `LLM_PROVIDER` / `LLM_API_KEY` / `LLM_MODEL`. | Yes — that's the point of D8 |
| **D11** | **Conversation history must be trimmed** (Block 4), not left unbounded | Groq's free tier caps ~**14,400 tokens/minute**. Per C10, a 40-turn conversation is ~40K tokens in *one* request — over the entire per-minute budget. **A limit that makes you build it right beats unlimited quota that lets you build it wrong.** | No |
| **D13** | **Model switched to `openai/gpt-oss-120b`** on Groq | Changed by editing **one line of `.env`** — zero code changes. Live proof that D3 + D8 work. | Yes — one line |
| **D16** | **Tests come before the database**, not after | v0.2 Block 2 replaces the in-memory store with PostgreSQL — surgery on the core. Tests written against *current* behaviour are a characterisation: they pin down what works today so the refactor can't silently change it. Writing them afterwards means verifying the new thing against nothing. *"Changing existing code safely — tests as the safety net."* | No |
| **D14** | **Interrupted streams save nothing** (option A) — a disconnect mid-reply leaves the user message with no assistant reply | Only complete assistant responses are stored; a partial must never be recorded as if it were whole. **Accepted consequence:** history can hold a dangling user turn, so the model may see two user messages in a row. The production refinement (roll back the user message on `GeneratorExit`, keeping history strictly alternating) is logged for v0.2. | Yes |
| **D15** | Streamlit entrypoint is **`ui/streamlit_app.py`**, not `ui/app.py` | `ui/app.py` resolves to a module named `app`, colliding with the `app/` package; mypy refuses to check either. **Renaming beats configuring around it** — `--exclude ui` would have silenced type checking on a whole directory of real code. | Yes |
| **D12** | **The git repo is rooted at the project, not the parent folder** | Learned the hard way — `git init` had landed at `projects/`, mixing study notes with product code. See C13. | No |

---

## 🧠 CONCEPTS LEARNED

### C1 — The Claude/LLM API is stateless
There is no conversation stored on the provider's side. **Every request resends the entire message history.** The "memory" is 100% yours.

Three consequences that shape the whole architecture:
1. **Conversation state is your problem.** v0.1 keeps it in RAM → dies on restart → earns the database in v0.2.
2. **Cost grows quadratically with conversation length.** Turn 20 resends turns 1–19. This is *why* prompt caching, token counting, and context compaction exist.
3. **Externalized state is what makes a service scalable** — see C2.

### C2 — Persistence ≠ statelessness (two prizes, one change)
Moving history out of process RAM into a database gives you **two** things:

| Property | What it buys |
|---|---|
| **Durability** | Restart/crash doesn't lose the conversation |
| **Statelessness** | *Any* instance can serve *any* request |

The second is the bigger deal. If history lives in process #1's RAM and the load balancer routes the next message to process #2, the assistant has amnesia — **the app is unscalable and no number of servers fixes it.**

### C3 — 12-Factor config (Factor III): separate config from code
Config = anything that varies between laptop / staging / prod.

- **Security:** a key in source is in git history *forever* — every fork, every CI log. Rotation is the only fix, and you find out too late.
- **Deployability:** one artifact, many environments. If dev and prod need different *builds*, you can't promote a tested image to prod — you can only hope.

Pattern: `.env` (real values, **gitignored**) + `.env.example` (same keys, fake values, **committed**). The *shape* of config is public and versioned; the *values* are private.

### C4 — Fail fast at startup
❌ Amateur: `os.getenv("KEY")` scattered around → returns `None` → app boots → crashes on the first user request at 2am.
✅ Production: validate **all** config once at import time → missing value → **the process refuses to start.**

| Behaviour | What actually happens |
|---|---|
| App **won't start** | Orchestrator sees the container die → halts the rollout → old version keeps serving. **Automatic, silent, zero users harmed.** |
| App **starts then 500s** | Rollout completes → healthy-looking container serves errors → **someone gets paged. That's an incident.** |

Same bug. Two completely different nights.

### C5 — Config validation ≠ health check
| Check | Question | When |
|---|---|---|
| **Config validation** | "Is my configuration present and well-formed?" | Once, at startup |
| **Health / readiness probe** | "Are my dependencies reachable *right now*?" | Continuously, in prod |

Validating the key at startup proves a key **exists**. It does **not** prove the key is valid, that you have quota, or that the provider is up. Config is a *static* property of your deployment; dependency health is a *live* property of the world. Conflating them is how people build health checks that lie.

### C6 — The single choke point (why the UI never calls the LLM directly)
- **v0.4 (React in the browser):** a key shipped to a browser is a key on the internet. Absolute rule.
- **v0.1 (Streamlit is server-side, so the key isn't browser-exposed):** the reason is **architectural control**. Every LLM call funnels through one service you own — the single door where auth, rate limiting, per-user cost tracking, structured logging, retries, and caching get installed. If the UI called the provider directly, none of those have anywhere to live.

Bonus: swapping Streamlit → React in v0.4 doesn't move the LLM logic an inch.

### C7 — CI ≠ CD
| | Question it answers | Triggered by | Needed when |
|---|---|---|---|
| **CI** | "Did I break it?" | Every push | **The moment code exists** |
| **CD** | "Is it live?" | Merge to main | The moment there's somewhere to deploy |

Roadmap: v0.1 lint/format/type-check → v0.2 pytest + coverage gate → v0.3 service containers for integration tests → v0.4 Docker build + registry + **deploy**, dependency scanning → v1.0 LLM eval suite, load-test job, blue-green/canary.

### C8 — Production-grade means *sequencing*, not maximalism
> "We'll clean that up later" is a banned phrase. So is writing Terraform for a service that doesn't exist.

The bar: **at every version, the thing runs, and everything it has is done properly.** v0.1 has no database — and its config, git hygiene, error handling, and CI are showable to a staff engineer. Bolting on Kubernetes in week one is a monument, not a system.

### C9 — API billing is separate from chat subscriptions
Pro / Max / **Team** / Enterprise are **claude.ai** products (humans logging into a chat UI). The **API** is billed separately with its own credits. **A Team seat does not grant API access for your application.** Model access isn't gated by subscription tier; what scales with spend is your **rate limits**.

### C10 — LLM cost mechanics, and how bills run away
You pay **per token, per call** — input and output, at different rates. No subscription, no cap. 1,000 calls = 1,000 charges.

**The quadratic problem.** Because the API is stateless (C1), you resend the whole conversation every turn. Assuming ~1,000 tokens added per turn, on a $5/$25 model:

| Turn | Input tokens sent | Cost of that one turn |
|---|---|---|
| 1 | 200 | $0.02 |
| 10 | 9,200 | $0.07 |
| 30 | 29,200 | $0.17 |
| 50 | 49,200 | $0.27 |

**One 50-turn conversation ≈ $7** — not the ~$1 intuition predicts, because turn 50 re-sent turns 1–49. This is *why* prompt caching exists (v0.3 cuts the repeated prefix to ~10%).

**Three ways cost runs away:**
1. **Retry loop with no cap** — error → retry → error → retry, overnight. Retries need a *maximum*.
2. **Streamlit re-runs the entire script on every interaction** ⚠️ *(will bite in Block 5)* — every click re-executes the file top to bottom. An API call at module level = a billable call per interaction. People discover this via their invoice.
3. **Unbounded history** — turn 200 sends 200K tokens *every turn*.

Combined: a retry loop firing a 50-turn conversation 500 times ≈ **$3,500 overnight**, from a one-line bug.

**Where this grows up:** v0.3 structured logging of tokens + cost per call → v0.3 prompt caching → v1.0 per-tenant cost tracking. *You cannot build cost tracking in v1.0 if you never learned what drives cost in v0.1.*

### C11 — Dependency isolation: virtualenv → Docker
Without isolation, every project on your machine shares one set of packages. Project A needs `pydantic 1.x`, Project B needs `2.x` — they cannot coexist. You break one by fixing the other. That's **dependency hell**.

A **virtual environment** (`.venv/`) is a private folder with its own interpreter and packages. Three things it protects:
1. **Package conflicts between projects** (the main event — venv isolates `site-packages`)
2. **The system Python**, which macOS/Linux use for OS tooling — polluting it breaks system tools
3. **Reproducibility** — without isolation you can't tell what your project *needs* vs what's incidentally installed, so you can't produce a trustworthy dependency list → unreproducible builds → "works on my machine"

> **The same instinct at a bigger scope is Docker.** Isolate dependencies so it runs the same everywhere — at the language level that's a virtualenv, at the OS level that's a container. Remember this in v0.4.

### C12 — `.python-version` ≠ `requires-python`
Two different mechanisms, often confused:

| | What it says | Who reads it | Shape |
|---|---|---|---|
| **`.python-version`** | "Use *exactly* this interpreter" | `uv` / `pyenv`, when building `.venv` | A **pin**: `3.12` |
| **`requires-python`** (pyproject) | "This project *works on* these versions" | Dependency resolvers, and installers | A **constraint**: `>=3.12` |

The first controls *your* environment. The second shapes *resolution* — it's how a resolver knows not to hand you a package that dropped 3.12 support. You need both.

**Why pinning matters at all** — the three concrete failure modes it kills:
1. **Stdlib behaviour changes** between minor versions
2. **C-extension ABI mismatch** — a wheel built for 3.12 physically will not load on 3.14
3. **Different dependency resolution** — the same install can pick *different package versions* per Python version

Together those are the entire content of the phrase *"works on my machine."*

**Also: boring is a virtue in production.** We pinned 3.12 despite 3.14 being installed. You don't run bleeding-edge language versions on a project whose dependencies you don't control — you'd spend evenings on someone's incompatible C extension instead of learning architecture.

### C13 — Repo boundaries: one repo = one deployable unit
Learned by getting it wrong: `git init` had landed at `projects/`, so the repo contained study notes *and* product code. Three reasons that's broken:

1. **A repo should be one deployable unit.** In v0.4 you build a Docker image from it — your study notes don't belong in the image.
2. **Your portfolio link** should open OmniAssist, not a folder of planning markdown.
3. **CI triggers on the whole repo** — editing a plan doc would fire the pipeline for nothing.

**Also: the project name is not cosmetic.** It becomes the import path, the package name, the GitHub URL, and the Docker image tag. Fix it on day one; unwinding it in v0.4 is miserable.

### C14 — Presence validation ≠ value protection (`SecretStr`)
Making a key **required** (C4) and keeping it **out of logs** are different problems. A plain `str` key is invisible to git but fully visible to `repr()`, `str()`, tracebacks, framework error pages, and any observability tool that serialises objects.

> **Secrets rarely leak because someone committed them. They leak because something *printed* them.**

`SecretStr` renders as `SecretStr('**********')` and requires `.get_secret_value()` to read. Accidental exposure becomes impossible; deliberate access still works. Verified empirically: `'gsk_' in repr(settings)` went `True` → `False`.

### C15 — Validate values, not just presence (`Literal`)
`llm_provider: str` accepts `"bananacloud"`. `app_env: str` accepts `"prodution"` — which in v0.4 would silently take the *non-production* branch **in production**. A typo that validates is worse than one that crashes, because the failure surfaces far from its cause.

`Literal["groq", "anthropic"]` rejects it at startup, naming the permitted values. **Real payoff:** `LLM_PROVIDER=grok` — a typo actually made repeatedly in this project's own planning — is now impossible to deploy. *Encode the mistakes you personally make into the type system.*

### C16 — Formatting ≠ linting
Two different jobs, both in CI:

| Tool | Job | Caught here |
|---|---|---|
| `ruff format` | Layout — whitespace, line breaks, quotes | stray blank lines |
| `ruff check` | Convention & correctness — import order, unused vars, bugs | `I001` import order |

`ruff format` reported "already formatted" while `ruff check` still failed. Passing one says nothing about the other. Import order convention: **stdlib → third-party → local**, alphabetical within groups.

### C17 — Git tracks files, not directories
An empty `tests/` directory simply does not exist to git. Commit, clone elsewhere, and the folder is gone. Convention: an empty `.gitkeep` file to hold the directory open. (`.gitkeep` is not a git feature — purely a naming convention.)

### C18 — Commit messages: Conventional Commits, and *why* not *how*
`feat:` / `fix:` / `chore:` prefixes are machine-readable and later drive changelog generation and semantic versioning. The **body** should explain *what changed and why* — the diff already shows *how*. Six months on, the body is the only record of why `SecretStr` is there.

### C19 — Verify behaviour, not exit codes
`git check-ignore -v .env.example` exits **0** when *any* pattern matches — **including a negation** (`!.env.example`). Branching on that exit code produced a false "wrongly ignored" alarm. The definitive test was behavioural: does `git add --dry-run` succeed, and does the file appear in `git status`? *Don't trust a tool's exit code whose semantics you haven't checked.*

### C20 — Dependency Inversion, and why `Protocol` over `ABC`
> **High-level code must not depend on low-level code. Both depend on an abstraction.**

The trap: `from groq import Groq` inside `services/` welds business logic to one vendor. Every service imports it; swapping providers touches all of them; testing needs a live key.

The fix: `services/ → LLMClient (interface) ← GroqClient`. The arrow from the vendor points **up** at your contract — that's the "inversion."

| | `ABC` | `Protocol` ← chosen |
|---|---|---|
| Conformance | must **inherit** | just **has the methods** |
| Typing | nominal | structural (checked duck typing) |
| Test double must inherit? | yes | **no** |

Decisive reason: `FakeLLMClient` satisfies the contract *without importing or inheriting anything from production code*, and mypy still verifies it. **Proven:** one `talk(client: LLMClient)` function drove a live Groq client and a keyless fake.

### C21 — The composition root
Exactly one place is allowed to know both the global config **and** the concrete implementations: the factory. Everything downstream receives an `LLMClient` and never learns which one.

Two deliberate details in `factory.py`:
- **Returns `-> LLMClient`, not `-> GroqClient`.** Annotate the concrete type and callers start reaching for vendor-specific attributes; the abstraction leaks within a week.
- **The vendor import sits inside the function.** Importing the factory doesn't pull `groq` into memory; a Groq-only deployment never loads the Anthropic SDK.

### C22 — Static typing catches what passing tests do not
The live call returned `"OK"` — green, working, shipped. mypy then found `message.content` is `str | None` while `chat()` promised `-> str`.

Failure mode if unfixed: `chat()` returns `None`; three layers up something calls `.strip()`; `AttributeError` in a file unrelated to the cause. **Bugs that surface far from their origin are the expensive kind.** The happy path is common, which is exactly why tests alone miss this.

**Corollary — not every type error is your bug.** mypy also flagged `Settings()` for a "missing argument" it can't know is populated from `.env` at runtime. Correct fix: enable `plugins = ["pydantic.mypy"]` (verified: 3 errors → 2). Wrong fix: `# type: ignore`, which would also silence real errors.

### C23 — The adapter boundary translates types *and* errors
Two leaks the adapter must stop:

**Types.** Your `Message` is `dict[str, str]`; the SDK wants `ChatCompletionUserMessageParam`. `cast()` at that seam is legitimate — translating is the adapter's whole job. The alternative leaks vendor TypedDicts into `services/`. *A cast at a boundary is fine; a cast inside business logic is a smell.*

**Errors.** Services must never catch `groq.RateLimitError`. The adapter raises a vendor-neutral `LLMError`. **A vendor leaks upward through its exception types just as easily as through its imports.**

### C24 — How to read an unfamiliar API (the FDE skill)
Six questions to answer from the docs — *copying exact names, never guessing*: **auth** · **exact call path** · **request shape** · **response extraction path** · **exception class names** · **streaming mechanics**.

Then **verify against the installed library, not the docs or your memory** — `inspect.signature`, `dir()`. Doing so surfaced two things the quickstart never mentioned:
1. **`max_retries=2` is the default** — one logical call can be three HTTP requests, tripling cost and burning rate limit during exactly the moments you're already throttled. *Never inherit a default you didn't choose.*
2. **14 exception classes exist**, including `RateLimitError` — which D11 guarantees you will hit on the free tier.

> **"It raises errors when something goes wrong" is never an acceptable answer about an API.** Retry logic, alerting and user-facing messages all branch on class names.

**Also noted for Block 3:** streaming uses `chunk.choices[0].delta.content` — **`delta`, not `message`.** Different shape from the non-streaming path.

### C25 — A parameter that changes the return type should have been a separate function
`chat(messages, stream: bool)` would return `str | Iterator[str]` — forcing *every* caller to narrow a union, including the 90% who passed `stream=False` and know exactly what they're getting. `@overload` can paper over it, but that's machinery invented to solve a self-inflicted problem.

Also: flag arguments hide intent (`chat(msgs, True)` says nothing) and a Protocol declaring **two methods** forces every implementer — including the fake — to provide both. A bool can be silently ignored.

### C26 — Streaming is a UX and reliability feature, not a performance one
| Reason | Effect |
|---|---|
| **Perceived latency** | Total time is unchanged (sometimes marginally worse). Reading starts immediately. |
| **Timeouts** | Long generations exceed proxy/LB timeouts; flowing bytes keep the connection alive (bites in v0.4). |
| **Cancellation** | User stops a bad generation → stop paying for tokens (C10). |

Measured: first token 0.58s vs total 0.86s. Small on Groq (very fast); on a slower provider generating 500 tokens the gap becomes ~0.4s vs ~8s. **The benefit scales with generation length.**

### C27 — Generator laziness, and the eager/lazy split
**A function containing `yield` does not execute when called** — it returns a generator; the body runs only on iteration.

This bit for real: `self.calls.append(...)` inside the generator body meant the call was never recorded until something iterated. `stream_chat(msgs)` then `assert len(fake.calls) == 1` **failed**.

> **Pattern: if a generator function must do anything eagerly — validate arguments, record a call, acquire a resource — split it into a plain function that returns the generator.**

```python
def stream_chat(self, messages):     # plain function — body runs on call
    self.calls.append(messages)
    return self._stream()

def _stream(self):                   # generator — runs on iteration
    ...
    yield piece
```

**Same property in the real client, deliberately:** `GroqClient.stream_chat` issues no HTTP request until iterated. Good (don't pay for an unconsumed stream) — but an `AuthenticationError` surfaces at the first `for` loop, not at the call site.

### C28 — A test double that lies gives you confidence you haven't earned
The fake yielded `word + " "`, so `"".join(stream_chat(m))` was `'one two three '` while `chat(m)` returned `'one two three'`. Real provider chunks concatenate **exactly**.

> **Invariant the fake must uphold: `"".join(client.stream_chat(m)) == client.chat(m)`**

Why it matters: Block 4 accumulates streamed chunks into history. A test on the unfaithful fake stores a trailing space and **passes**; production stores something different. *A test that passes while the real path is broken is worse than no test.* Fix: yield fixed-size character slices — exact reconstruction by construction, and closer to real token boundaries than word-splitting.

### C29 — The same value can mean different things in different contexts
`content` is `str | None` in both methods. The correct handling is **opposite**:

| Context | Meaning of `None` | Response |
|---|---|---|
| `chat()` — the whole reply | Anomaly: model produced nothing | **raise `LLMError`** |
| `stream_chat()` — one chunk | Routine: first chunk carries the role, last carries a finish reason | **skip and continue** |

Decide what a value *means in context* before deciding what to do with it. That judgement is most of what separates correct code from merely defensive code.

### C30 — Server-Sent Events: the whole protocol, and its three traps
SSE is **an ordinary HTTP response that never ends**: `Content-Type: text/event-stream`, then `data: <payload>\n\n` per event. A **blank line terminates an event**. That's it.

**Why SSE over WebSockets here:** token streaming is one-directional. SSE is plain HTTP (proxies, LBs and CDNs pass it), browsers reconnect automatically, and there's no upgrade handshake. WebSockets buy bidirectionality we don't need and cost infrastructure config in v0.4. *Pick the least powerful tool that solves the problem — it has the fewest failure modes.*

Three traps, all hit or avoided in Block 4:

1. **🔴 Payloads must be JSON-encoded.** Model output is full of newlines. A raw `data: hello\nworld\n\n` becomes **two malformed events** — the client sees a truncated reply and blames the model. `json.dumps(chunk)` escapes the newline inside a quoted string so the frame stays one line. Seen live in our own output: `data: "  \n"`.
2. **`[DONE]` sentinel.** SSE has no end-of-stream marker, so the client can't distinguish "finished" from "connection dropped." Convention borrowed from OpenAI's API.
3. **`X-Accel-Buffering: no`.** Without it nginx buffers the whole response and delivers it at the end — **streaming silently stops working only in production**, the worst place to find out.

Also: never buffer server-side. Collecting all chunks then returning them is a slow non-streaming endpoint with extra steps.

### C31 — A health check must be cheap, or it becomes the load
It is tempting to have `/healthz` verify the LLM is reachable. Do the arithmetic first:

> A load balancer probes every **10 seconds** = **8,640 requests/day**. The Groq free tier is ~**1,000/day**.
> **The health check alone would exhaust the entire quota eight times over, serving zero users.**

This is C5 with a price tag. Split the two questions:

| Probe | Question | On failure |
|---|---|---|
| **Liveness** (`/healthz`) | Is the process alive? | Restart the container |
| **Readiness** (`/readyz`, v0.4) | Can I serve traffic *right now*? | Remove from the LB — **don't** restart |

### C32 — Trim what you *send*; keep what you *store*
`trimmed = history[-max_history:]` is a **slice, not a mutation**. Verified: 12 messages stored, 4 sent. Trimming bounds the request payload; it is not forgetting.

Two things to know about the choice:
- **Message count is a proxy for token count.** The real limit is ~14,400 tokens/min (D11) and messages vary wildly in length. Proper token counting needs a tokenizer — deferred to v0.3 with observability. *Know you chose a proxy, and why.*
- **A naive window can start mid-exchange.** Our trimmed payload opened with an `assistant` message — from the model's view, it spoke first, unprompted. Same family as D14's dangling user turn: **don't send the model state that couldn't occur in a real conversation.**

### C33 — Streamlit re-runs the entire script on every interaction
Every click, every message, every widget change re-executes the file from line 1.

| | Consequence |
|---|---|
| Module-level code | **Runs again each time** — an API call there fires per click (C10, with a bill) |
| Local variables | **Wiped** — history vanishes every message |
| `st.session_state` | The only thing that survives; holds `conversation_id` and `messages` |

Corollary: past messages must be **redrawn** on every run — Streamlit doesn't remember what it painted. Also `timeout=None` on the streaming HTTP call, since a default timeout kills long replies mid-flight.

### C34 — Syntactically valid dead code is harder than a crash
The Streamlit page rendered a title and nothing else — **no error**. The entire `st.chat_input` block had been indented one level, nesting it inside a function that merely got *defined*. Valid Python, never executed.

> **Diagnostic: when a script "does nothing," list its module-level statements** (`ast.parse(...).body`). If the thing you expected to run isn't there, it's nested inside something.

A crash tells you where to look. Silent dead code tells you nothing — which is why this class of bug eats hours.

### C35 — Fix the name, don't configure around the collision
`ui/app.py` and the `app/` package both resolve to a module named `app`; mypy refused to check either and suggested `--exclude`, `__init__.py`, or `--explicit-package-bases`.

**All three suppress the symptom.** Renaming to `ui/streamlit_app.py` removes the cause, and is a better name anyway. `--exclude ui` would have disabled type checking across a whole directory of real code — **a config flag that silences a checker is a liability you'll forget you added.**

### C36 — `uv sync --locked` turns reproducibility into an enforced rule
The flag installs **exactly** `uv.lock` and **fails the build if the lock is out of date** with `pyproject.toml`.

Two guarantees that follow:
- CI cannot quietly resolve different versions than your laptop has
- Nobody can add a dependency without committing the lockfile

This is D2's payoff arriving: the reason for choosing `uv` was never speed, it was the lock. **A convention enforced by a machine is a rule; one enforced by discipline is a suggestion.**

### C37 — Tags are immutable; branches move
`v0.1` is a permanent pointer to one commit. `main` will keep moving; the tag won't.

Why it matters concretely:
- `git diff v0.1..HEAD` tells you exactly what changed since a known-good state — essential when a v0.2 migration breaks something
- It makes v0.2 an *evolution* of a shipped release rather than a rewrite (D1)
- In v0.4 the deploy pipeline deploys and rolls back to **tags** — **you cannot roll back to a branch**

### C38 — Test behaviour, not implementation
```python
assert len(fake.calls[-1]) == 3          # ✅ what the provider received
assert service._store["c1"] == [...]     # ❌ reaching into private state
```
The first survives the PostgreSQL migration; the second breaks the moment `_store` stops being a dict — and a "safety net" that breaks during the refactor it was built for is just noise you have to fix while already mid-surgery.

Corollary: **don't test the library.** Not that pydantic validates or that FastAPI routes — only your own logic (history accumulates, trimming caps the payload, the full conversation survives).

The trimming case is deliberately **two** tests, not one: the first asserts the cap, the second asserts the cap wasn't achieved by *deleting* data. Merged into a single test, you'd likely assert only the half you were thinking about.

### C39 — Accessors must not hand out internal state
`get_history` returned `self._store.get(cid, [])` — **the live list**. Proven: a caller appended to it and corrupted the service's history from outside.

**Why it's a migration landmine, not just poor style:** when `_store` becomes a SQL query, `get_history` will build a *fresh list from rows* and mutation will do nothing. Any code that accidentally relies on the leak keeps working until the database lands, then fails in a way that looks unrelated to the migration.

> **Make the in-memory version behave the way the database version will, so the swap is invisible.** Today's shortcut is tomorrow's migration bug.

Fix: `return list(...)`.

### C40 — Regression tests exist to stop a fixed bug coming back
`test_get_history_returns_a_copy` proves nothing about the feature — it exists solely so nobody reintroduces the leak. A bug found once is a bug worth pinning; the fix is cheap now and invisible later.

### C41 — A half-declared package breaks static analysis
mypy: *"Source file found twice under different module names: `fakes` and `tests.fakes`."* With no `__init__.py`, `tests/fakes.py` was a top-level module `fakes`; the import `from tests.fakes import ...` made it `tests.fakes` as well. One file, two identities.

mypy offered `--explicit-package-bases` and `MYPYPATH`. Both configure around it. The real problem was that `tests/` was being *used* as a package without being *declared* as one — `touch tests/__init__.py` fixed the cause. Same principle as C35.

*(Shell aside: zsh does not treat `#` as a comment interactively by default, so a pasted trailing comment becomes pytest arguments. `setopt interactive_comments` fixes it.)*

---

## 📊 REFERENCE — LLM API pricing (2026-08-02)

**Anthropic** (authoritative):

| Model | Model ID | Context | Input /1M | Output /1M |
|---|---|---|---|---|
| Claude Opus 5 | `claude-opus-5` | 1M | $5.00 | $25.00 |
| Claude Sonnet 5 | `claude-sonnet-5` | 1M | $3.00 ($2 intro to 2026-08-31) | $15.00 ($10 intro) |
| Claude Haiku 4.5 | `claude-haiku-4-5` | 200K | $1.00 | $5.00 |

**Cross-provider snapshot** — *third-party aggregators, verify before committing money*:

| Tier | Model | Input /1M | Output /1M |
|---|---|---|---|
| Frontier | Claude Opus 5 · GPT-5.5 | $5.00 · $5.00 | $25.00 · $30.00 |
| Frontier | Claude Sonnet 5 · GPT-5.4 · Gemini 3.1 Pro · Grok 4.5 | $3.00 · $2.50 · $2.00 · $2.00 | $15.00 · $15.00 · $12.00 · $6.00 |
| Budget | Claude Haiku 4.5 · Llama 3.3 70B (Groq) · DeepSeek V4 Pro | $1.00 · $0.59 · $0.44 | $5.00 · $0.79 · $0.87 |
| Ultra-budget | Grok 4.1 Fast · DeepSeek V4 Flash · Mistral Small 3.2 · GPT-4.1-nano | $0.20 · $0.14 · $0.10 · $0.10 | $0.50 · $0.28 · $0.30 · $0.40 |

**Free tiers:** Gemini **1,500 req/day, no card, no expiry** · **Groq ~1,000 req/day, no card** ⬅️ *ours* · Cerebras 1M tok/day · xAI $25 credits + up to $150/mo **in exchange for data sharing** · OpenAI $5/3mo · **Anthropic: none**

**Three traps spotted while comparing:**
1. ***"Free" always has a price — find it.*** xAI's generous tier is paid for with your conversation data.
2. **Grok doubles its rate above 200K tokens** — a pricing cliff sitting exactly where conversation history grows unboundedly (C10). *Pricing structure is an architectural input, not trivia.*
3. **Never build on an announced-EOL model** (Gemini 2.5 Flash-Lite retires 2026-10-16) — a self-inflicted migration.

**Anthropic API gotchas (for when we add it):** model IDs are complete as written — **never append a date suffix** · on Opus 5 thinking is **on by default** and `max_tokens` caps thinking **plus** response text together · `temperature`/`top_p`/`top_k` are **rejected (400)** — steer with prompting · stream for long outputs or you'll hit SDK HTTP timeouts.

---

## ✅ SELF-CHECK HISTORY

**2026-08-02 — v0.1 design quiz: 3/3**

| Q | Verdict | Sharpening applied |
|---|---|---|
| What happens to history if FastAPI restarts? | ✅ | Missed that externalized state also buys **horizontal scalability** → C2 |
| Why fail at startup, not first request? | ✅ | Said "know if the API is working" — that's a **health check**, not config validation → C5 |
| Why does the UI call FastAPI, not the LLM? | ✅ | Correct for v0.4's browser; for v0.1's server-side Streamlit the real reason is the **single choke point** → C6 |

**2026-08-02 — Block 1 Step 1 quiz: 2/2**

| Q | Verdict | Sharpening applied |
|---|---|---|
| Why pin the Python version? | ✅ Strong | Named reproducibility; added the 3 concrete failure modes + the `.python-version` vs `requires-python` distinction → C12 |
| What breaks without a virtualenv? | ✅ Right instinct | It's mostly *packages*, not Python; plus system-Python pollution and unreproducible dependency lists → C11 |

**2026-08-02 — Block 1 adversarial code review of `app/config.py`: 3 findings, 2 real defects**

| # | Severity | Finding | Outcome |
|---|---|---|---|
| 1 | 🔴 Security | API key leaked via `repr()` / `str()` / tracebacks | Fixed with `SecretStr` → C14 |
| 2 | 🟠 Correctness | Invalid values accepted (`bananacloud`, `prodution`) | Fixed with `Literal` → C15 |
| 3 | 🟡 Style | Inconsistent blank lines + unsorted imports | Fixed via `ruff format` + `ruff check --fix` → C16 |

Final state: 6/6 verification checks pass — lint clean, format clean, three distinct invalid configs rejected at startup, happy path loads, zero key leakage.

**2026-08-02 — Block 2 API-reference reading: 5/6**

Correct on auth, call path, message shape, response extraction, streaming flag. Weak on **errors** — "it raises exceptions" is not actionable; the answer needed class names. Introspection then found `max_retries=2` silently on by default, which the docs did not surface.

**2026-08-02 — Block 2 mypy review: 3 findings**

| # | Type | Finding | Outcome |
|---|---|---|---|
| 1 | False positive | `Settings()` "missing argument" — mypy can't see `.env` | Enabled `pydantic.mypy` plugin → C22 |
| 2 | Structural | `dict[str,str]` vs SDK TypedDicts | `cast` at the adapter seam → C23 |
| 3 | 🔴 **Real bug** | `content` is `str \| None`, signature promised `str` | Raise `LLMError` → C22/C23 |

Final: mypy clean, ruff clean, live call returns `OK`, fake works with no `.env` and no key.

**2026-08-02 — Block 3 review: 2 findings, both real**

| # | Finding | Outcome |
|---|---|---|
| 1 | Fake's stream didn't reconstruct its own `chat()` (trailing space) | Fixed-size chunking → C28 |
| 2 | 🔴 `self.calls` never recorded — eager work sat inside a generator body | Eager/lazy split → C27 |

Design question answered correctly: separate `stream_chat()` over a `stream: bool` flag → C25.

**Block 4 review — 2 findings**

| Finding | Outcome |
|---|---|
| Trimmed window can open with an `assistant` message (state that can't occur in a real conversation) | Logged for v0.2 → C32 |
| First chunk is `""` — passes the `is not None` guard and emits a useless SSE frame | Logged → C30 |

Design questions answered 4/4, including the interrupted-stream policy (→ D14).

**Block 5 review — 1 finding**

| Finding | Outcome |
|---|---|
| 🔴 Whole chat block indented inside `stream_reply()` — valid syntax, never executed, no error shown | Dedented; AST diagnostic learned → C34 |

Plus a module-name collision caught by mypy → C35 / D15.

**Block 6 — CI verified**

`ruff format --check`, `ruff check` and `mypy` all pass **with no `.env` and no API key present** — D5 proven, not assumed. `uv sync --locked` confirms the lockfile is in sync. Two green CI runs (PR + main), ~35s each.

---

## 🧱 BLOCK PROGRESS — v0.1

| Block | Status |
|---|---|
| **1 — Repo skeleton + config & secrets** | ✅ **COMPLETE** (2026-08-02) — 8/8 steps · commit `6e40a75` · [github.com/vikasgautam2003/OmniAssist](https://github.com/vikasgautam2003/OmniAssist) |
| **2 — LLM client (D8 interface + GroqClient + factory + fake)** | ✅ **COMPLETE** (2026-08-02) |
| **3 — Streaming** | ✅ **COMPLETE** (2026-08-02) |
| **4 — FastAPI + SSE + history** | ✅ **COMPLETE** |
| **5 — Streamlit UI** | ✅ **COMPLETE** |
| **6 — CI + README + tag `v0.1`** | ✅ **COMPLETE** |

---

## 🧾 CHANGE LOG

| Date | What |
|---|---|
| 2026-08-02 | `FLAGSHIP_PROJECT.md` — CI added to v0.1 best practices & stack; recorded CI-moves-to-v0.1 decision + the no-live-key constraint |
| 2026-08-02 | `FLAGSHIP_PROJECT.md` — v0.1 block list expanded to 6 blocks |
| 2026-08-02 | `FLAGSHIP_PROJECT.md` — stack switched to provider-agnostic LLM layer (Groq default); Groq-free-tier decision recorded |
| 2026-08-02 | `LEARN_SHEET.md` created, then lost in a folder cleanup, then rebuilt in full — **now correctly located at `projects/omniassist/`** |
| 2026-08-02 | Project scaffolded: `uv init . --python 3.12`, renamed `ai` → `omniassist`, `pyproject.toml` name fixed, git repo re-rooted at the project (D12, C13) |
| 2026-08-02 | **Block 1 COMPLETE** — `.gitignore`, `.env`/`.env.example`, `app/config.py` (fail-fast + `SecretStr` + `Literal`), `tests/.gitkeep`, genesis commit `6e40a75`, pushed to `github.com/vikasgautam2003/OmniAssist` (private) |
| 2026-08-02 | Security audit on committed tree: `.env` absent, no `gsk_` key anywhere in git history, `.venv` excluded, `uv.lock` + `.env.example` committed — **5/5 clean** |
| 2026-08-02 | `~/Downloads/OmniAssist_Project_Synopsis.docx` generated in the college template format (5 sections, 15 references, 2,799 words) |
| 2026-08-02 | **Block 2 COMPLETE** — `app/clients/{base,groq_client,factory}.py` + `tests/fakes.py`; `LLMClient` Protocol, `LLMError`, composition root, keyless fake; mypy + pydantic plugin configured; concepts C20–C24 |
| 2026-08-02 | **Block 3 COMPLETE** — `stream_chat()` on the Protocol, `GroqClient` (stream=True, `delta.content`, None-skipped), faithful chunking fake with eager/lazy split; concepts C25–C29 |
| 2026-09-22 | **Block 4 COMPLETE** — `POST /chat/{id}` SSE endpoint, `GET /healthz`, `ChatService` with history + trimming; concepts C30–C32, decision D14 |
| 2026-09-22 | **Block 5 COMPLETE** — `ui/streamlit_app.py` chat UI consuming SSE; concepts C33–C35, decision D15 |
| 2026-09-22 | **Block 6 COMPLETE** — GitHub Actions CI (format/lint/types, no API key), README; concepts C36–C37 |
| 2026-09-22 | **🎉 v0.1 SHIPPED** — 6/6 blocks, CI green, tagged `v0.1` |
| 2026-09-26 | **v0.2 Block 1 COMPLETE** — pytest configured, 5 tests on `ChatService` running with no key; `get_history` returns a copy; `self._client` made private; `tests/__init__.py` added; pytest wired into CI. Concepts C38–C41, decision D16 |
