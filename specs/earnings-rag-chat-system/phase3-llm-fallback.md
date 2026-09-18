# Phase 3: LLM-Unavailability Fallback

**Depends on:** `phase2-retrieval-generation.md`
**Status:** Not started

## Design components touched

Failure Modes — LLM unavailable (`system-design.md` §10); `docs/adr/ADR-007-llm-fallback.md`.

## Objective

The query function from Phase 2 never fails outright or crashes when the LLM is unavailable — whether because no API key is configured, or because a runtime call fails (timeout, rate limit, provider error). In both cases it falls back to a retrieval-only response: the raw matching excerpts and their citations, without an LLM-generated answer, flagged as degraded so the caller (eventually the Chat UI in Phase 5) can render it distinctly.

## Independently testable when

Calling the query function with no API key configured returns a degraded response with excerpts + citations and a `degraded: true` flag, rather than raising an exception or refusing to run. Simulating a runtime LLM failure (e.g. an invalid key discovered only at call time, or a forced exception) mid-session produces the same degraded response shape for that turn. Neither case requires the Chat UI to exist yet.

## Tasks

### 3.1 Missing-API-key fallback

- **Type:** AFK
- **Blocked by:** Phase 2 (task 2.2)
- **PRD reference:** PRD §6 (Non-Functional Requirements)
- **System design reference:** `docs/adr/ADR-007-llm-fallback.md`, §10 Failure Modes

**Scope:** Detect at query time that no LLM API key is configured, and instead of raising or refusing, return the retrieval results (excerpts + citations) from Phase 2's retrieval step directly, with no LLM call attempted, flagged as a degraded response.

**Acceptance criteria:**
- [ ] Running a query with no API key set returns excerpts + citations and a `degraded: true` flag, not an exception (ADR-007)
- [ ] The app does not refuse to start or block usage over a missing key (ADR-007)
- [ ] Demoable or verifiable in isolation (unset the API key, call the query function)

### 3.2 Runtime LLM call failure fallback

- **Type:** AFK
- **Blocked by:** 3.1
- **PRD reference:** PRD §6 (Non-Functional Requirements)
- **System design reference:** `docs/adr/ADR-007-llm-fallback.md`

**Scope:** Wrap the Claude Haiku call (added in Phase 2, task 2.2) with error handling covering exceptions, timeouts, and non-success responses. On any such failure, fall back to the same degraded retrieval-only response used in task 3.1, for that query only — it does not affect subsequent queries once the LLM becomes available again.

**Acceptance criteria:**
- [ ] Simulating an LLM call failure (e.g. a forced exception or invalid key mid-session) returns the same degraded response shape as task 3.1, not an unhandled exception (ADR-007)
- [ ] A subsequent query, once the LLM call succeeds again, returns a normal (non-degraded) answer
- [ ] Demoable or verifiable in isolation (mock/force an LLM call failure and confirm graceful degradation)
