# Phase 5: Chat UI (Streamlit)

**Depends on:** `phase3-llm-fallback.md`, `phase4-conversation-memory.md` (and transitively `phase1-ingestion-pipeline.md` for task 5.4)
**Status:** Not started

## Design components touched

Chat UI (`system-design.md` §2), startup + render data flow (§5); `docs/adr/ADR-001-chat-interface-streamlit.md`; decision-log row 11.

## Objective

A Streamlit application that wires the fully-wrapped query function (fallback-aware from Phase 3, conversation-aware from Phase 4) into an interactive chat interface: users type questions and see grounded answers with citations, degraded responses are visually distinguished from full answers, multi-turn conversation works end-to-end in the actual UI (not just scripted tests), and a missing/corrupted vector store produces a clear error rather than a crash or silent failure.

## Independently testable when

Running `streamlit run <app>.py` against a fully ingested corpus (Phase 1) gives a working chat: asking a question returns a grounded, cited answer (happy path); simulating LLM unavailability shows a visibly degraded response; asking a follow-up question demonstrates working multi-turn memory; and running the app against an empty/missing `data/vector_db` shows a clear "run ingest.py first" error instead of a crash.

## Tasks

### 5.1 Basic chat shell (single-turn happy path)

- **Type:** AFK
- **Blocked by:** Phase 2 (task 2.2)
- **PRD reference:** FR2
- **System design reference:** `docs/adr/ADR-001-chat-interface-streamlit.md`, §2 Chat UI

**Scope:** A Streamlit app using `st.chat_message`/`st.chat_input`, calling the Phase 2 query function in-process for a single turn, and rendering the answer with its citations. Does not yet handle degraded responses or multi-turn state — those are separate slices below.

**Acceptance criteria:**
- [ ] Launching the app and asking a question (e.g. "What was Apple's Q3 2024 revenue?") renders a grounded answer with citations in the browser (FR2, FR4)
- [ ] The app calls the RAG Query Engine directly as a Python function, with no REST/HTTP layer (ADR-001)
- [ ] Demoable or verifiable in isolation (manual check: launch and ask one question)

### 5.2 Degraded-mode rendering

- **Type:** AFK
- **Blocked by:** 5.1, Phase 3 (task 3.2)
- **PRD reference:** PRD §6 (Non-Functional Requirements)
- **System design reference:** `docs/adr/ADR-007-llm-fallback.md`

**Scope:** When the query function returns a degraded (`degraded: true`) response, render the raw excerpts and citations with a clear, visible "LLM unavailable — showing matching excerpts only" notice, distinct from a normal full-answer render.

**Acceptance criteria:**
- [ ] With no API key configured, the chat UI visibly shows the degraded notice rather than silently showing excerpts as if they were a generated answer (ADR-007)
- [ ] A normal (non-degraded) response is visually distinguishable from a degraded one
- [ ] Demoable or verifiable in isolation (manual check: run with no API key, ask a question)

### 5.3 Multi-turn wiring

- **Type:** AFK
- **Blocked by:** 5.1, Phase 4 (task 4.3)
- **PRD reference:** FR2, PRD §7 Success Criteria
- **System design reference:** `docs/adr/ADR-006-conversation-memory.md`

**Scope:** Wire Streamlit `session_state` to the Phase 4 conversation memory (bounded window, compaction, episodic memory), so a real chat session in the browser exhibits the same multi-turn behavior already verified by Phase 4's scripted tests.

**Acceptance criteria:**
- [ ] Asking a follow-up question in the actual browser UI (e.g. "how about Microsoft?" after asking about Apple) retrieves and answers correctly (FR2, PRD §7)
- [ ] A long in-browser conversation (exceeding the window size) remains coherent via compaction, matching Phase 4's verified behavior
- [ ] Demoable or verifiable in isolation (manual check: hold a multi-turn conversation in the browser, including one follow-up)

### 5.4 Startup vector-store-missing error handling

- **Type:** AFK
- **Blocked by:** 5.1, Phase 1 (task 1.5)
- **PRD reference:** — (operational robustness; ties to FR7's persistence expectation)
- **System design reference:** decision-log row 11, §10 Failure Modes

**Scope:** On app startup, check that the Chroma store exists and is readable. If it's missing or corrupted, show a clear on-screen error directing the user to run `python ingest.py` first — do not attempt to auto-rebuild it and do not silently fall back to an empty-chat state.

**Acceptance criteria:**
- [ ] Launching the app against a missing/empty `data/vector_db` shows a clear, actionable error message instead of crashing or silently starting an unusable chat (row 11)
- [ ] The app does not attempt to trigger ingestion itself under any circumstance (consistent with ADR-005)
- [ ] Demoable or verifiable in isolation (manual check: point the app at a missing vector store directory)
