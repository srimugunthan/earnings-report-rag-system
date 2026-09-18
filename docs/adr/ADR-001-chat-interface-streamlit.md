# ADR-001: Use Streamlit for the chat interface (not a React frontend)

**Status:** Accepted
**Date:** 2026-09-17
**Deciders:** Project owner

---

## Context

The Earnings Report RAG Chat System (PRD.md) needs an interactive, multi-turn chat interface where a user asks natural-language questions about ingested earnings-report PDFs and gets grounded answers with source citations and external links. The PRD's Non-Goals explicitly exclude multi-user auth, accounts, and hosted deployment — this is a single local user running the tool on their own machine. The existing prototype (`prototype/core/*`, `prototype/rag/pipeline.py`, `prototype/earnings/analyzer.py`) is pure Python built on LangChain, with no existing frontend tooling (no `package.json`, no JS build pipeline) anywhere in the repo. Streamlit is already installed in the working environment.

---

## Decision

We will build the chat interface using Streamlit, calling the RAG pipeline directly in-process (Python function calls), rather than standing up a separate REST/HTTP API layer consumed by a React (or other JS) frontend.

---

## Alternatives Considered

| Option | Pros | Cons |
|--------|------|------|
| React frontend + FastAPI/Flask backend API | Scales to many concurrent users; full control over UX/branding; decouples UI from compute via a stateless API | Two codebases (JS + Python) instead of one; requires designing and maintaining an HTTP API, request/response schemas, and CORS; adds a `node_modules`/build toolchain to an otherwise pure-Python repo; none of its scaling/multi-tenant benefits are used since the PRD excludes multi-user and hosted deployment |
| CLI chat loop (terminal REPL) | Simplest possible implementation; zero UI framework dependency | Renders markdown citations/links poorly compared to a web UI; worse experience for a chat-style, multi-turn interaction with source excerpts |
| **Streamlit web app (chosen)** | Pure Python — in-process calls into the existing RAG pipeline, no new language or build step; built-in `st.chat_message`/`st.chat_input` give a working multi-turn chat UI quickly; markdown rendering displays citations and external links cleanly; already installed in the environment | Streamlit's rerun-the-script execution model and session-state handling scale poorly to many concurrent users; less visual/UX customization than a hand-built frontend |

---

## Consequences

**Positive:**
- Single Python codebase — UI and RAG pipeline changes stay trivially in sync, no API contract to maintain.
- Fast to build and iterate (a working chat UI in well under a day).
- No new toolchain (no Node/npm) introduced into a currently pure-Python repo.
- Markdown-native rendering fits the requirement to show source citations and external links (FR4/FR5) with minimal custom rendering code.

**Negative / Accepted Tradeoffs:**
- Streamlit is not a good fit if this system later needs to support multiple concurrent users or be hosted publicly — its rerun/session-state model becomes a real constraint at that scale. This is an accepted tradeoff because the PRD explicitly excludes multi-user auth and hosted deployment for v1.
- UI customization is limited to Streamlit's component set; a fully custom-branded or highly interactive UX would require moving to a hand-built frontend later.

---

## Follow-up Actions

- [ ] If multi-user support or hosted deployment becomes a goal, revisit this decision: introduce a FastAPI (or similar) backend exposing the RAG pipeline over HTTP, and replace the Streamlit UI with a React (or other) frontend. The RAG pipeline module itself is UI-agnostic Python and should not need to change for this migration.
