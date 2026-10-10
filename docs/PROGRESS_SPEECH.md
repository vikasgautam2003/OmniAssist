# OmniAssist — Mid-Term Progress Speech
*Target: ~6 minutes spoken. Section headings map 1:1 to the slide deck.*

---

## 1. Opening — what I am building

Good morning. I am building **OmniAssist**, a multimodal AI assistant — the kind of
system that can hold a conversation, read a document you upload and answer questions
about it, and eventually generate documents, charts and images on request.

Let me be precise about the scope, because this is where most student AI projects
overstate themselves. **I am not training a language model.** I am building the
production system *around* one. The intelligence is rented from an API; the
engineering — how requests are routed, how data is isolated per user, how failures
are contained, how the thing is tested and deployed — is entirely mine. That is
also the honest description of what an AI engineer does in industry today.

## 2. The core idea — why the architecture looks like this

The heart of OmniAssist is **tool-use**. Rather than writing one giant program that
tries to handle every request, the language model is given a catalogue of tools and
decides which to call. "Summarise this PDF" routes to the document tool. "Chart this
data" routes to the data tool.

The significance is that **adding a capability becomes adding a tool, not rewriting
the application.** That single decision is what lets a project scale from a chatbot
to a do-everything assistant without the codebase collapsing under its own weight.

## 3. Where this sits alongside my internship
*(Slide 8 — Organisation & My Role)*

Briefly, the context. I am an Implementation Intern at **Rocketlane Technologies**
in Chennai, on a twelve-month paid internship that began in February. Rocketlane
builds a customer-onboarding and professional-services automation platform, and the
Implementation function takes a newly signed customer from contract to a working,
configured deployment.

My work there is split across two technologies: **React.js** for the customer-facing
interfaces, and **Python** for the server-side and integration work behind them. I
have delivered custom applications on the **NICE**, **Wealthbox** and **Confa**
engagements — built to each customer's own onboarding process rather than configured
from a template.

I mention this because the two feed each other. The internship supplies the React
experience that version 0.4 of this project depends on, and the discipline of
building against a named customer's stated requirements. The project supplies the
backend architecture, retrieval and testing practice I bring back to the
implementation work.

## 4. What is finished

**Version 0.1 is shipped and tagged** — a working conversational assistant:

- A **FastAPI** backend that streams responses token-by-token over Server-Sent
  Events, so replies appear as they are generated rather than after a long pause.
- A **provider-agnostic LLM layer.** The application never imports the vendor's SDK
  directly; it depends on an interface. Swapping providers is a configuration
  change, not a rewrite. It currently runs on Groq's free tier — the project has a
  hard zero-rupee budget, and the architecture is what makes that survivable.
- A **Streamlit** interface and a **GitHub Actions** pipeline that enforces
  formatting, linting and type-checking on every push.

**Version 0.2 is three-quarters complete** — turning that chatbot into a real
application:

- **PostgreSQL** persistence with **Alembic** migrations, so the schema has a
  version history the same way the code does.
- **Authentication** — Argon2id password hashing and JWT sessions. Conversations are
  now owned. Ownership is enforced in the database query itself, not as a check the
  application can forget to perform.
- **An automated test suite** that runs with no API key and no database, which is
  precisely why it can run in CI.

## 5. What I am working on right now

The current block is **retrieval-augmented generation** — the feature that lets you
upload a PDF and ask questions about it.

The pipeline is: extract the text, split it into chunks, convert each chunk into a
numerical vector that captures its meaning, store those in **pgvector**, and at
question time retrieve the few most relevant chunks and hand them to the model as
context.

The first stage — PDF text extraction — is complete and tested. The remaining
stages are chunking, embedding, vector storage and retrieval.

One decision from this block is worth sharing, because it shows the discipline the
project is built on. Embedding models cost money. So the embedder sits behind the
same kind of interface as the LLM client: the default implementation runs **locally,
free**, and a cloud provider can be dropped in later by changing one line. The
constraint produced a better design than an unlimited budget would have.

## 6. What remains

- **v0.3** — the tool-use framework itself, plus document and spreadsheet
  generation, background job processing and caching.
- **v0.4** — image generation, multi-tenancy, Docker, and deployment to AWS.
- **v1.0** — agentic multi-step tasks, persistent memory, and the operations layer:
  tracing, monitoring, cost tracking per tenant.

## 7. How it is being built

I want to close on process rather than features, because that is the part I think
matters most.

Every change goes through a feature branch and a pull request. Every version is
tagged and left in a working state before the next begins. The codebase is currently
**1,262 lines across 26 modules, 22 commits, 14 automated tests**, with continuous
integration green throughout.

The most valuable thing I have learned so far was a security defect my own tests did
not catch: an ownership check that appeared to run before a response was sent, but
actually ran *during* it — after the HTTP headers had already gone out. Linting
passed. Type-checking passed. Every test passed. Only tracing the real two-user path
by hand exposed it.

The lesson I took from that is that **green tests are evidence, not proof.** That is
the mindset I am carrying into the rest of this project.

Thank you — I am happy to take questions.
