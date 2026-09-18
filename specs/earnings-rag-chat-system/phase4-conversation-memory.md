# Phase 4: Conversation Memory (Multi-Turn)

**Depends on:** `phase2-retrieval-generation.md`
**Status:** Not started

## Design components touched

Conversation Memory (`system-design.md` §2), Data Model — turn/summary/episodic fact (§3), Data Flow (§5); `docs/adr/ADR-006-conversation-memory.md`.

## Objective

Make the Phase 2 query function conversation-aware: follow-up questions that refer to earlier turns (e.g. "how about Microsoft?") retrieve correctly because retrieval itself sees conversational context, not just the bare latest message. Long sessions stay coherent via a bounded window plus compaction of older turns into a running summary, and specific facts established earlier remain recoverable mid-session via in-session episodic memory, even after their raw turn has been compacted away.

## Independently testable when

A scripted multi-turn conversation (no UI) demonstrates: (a) a follow-up question with no restated context retrieves the correct company/topic's chunks, (b) a conversation exceeding the bounded window size still produces coherent answers via the compaction summary, and (c) a fact established early in the conversation is still correctly referenced in a later answer after compaction has folded that turn away, via episodic memory.

## Tasks

### 4.1 Bounded window, retrieval-aware follow-ups

- **Type:** AFK
- **Blocked by:** Phase 2 (task 2.2)
- **PRD reference:** FR2
- **System design reference:** `docs/adr/ADR-006-conversation-memory.md`, §5 Data Flow

**Scope:** Maintain the last N raw turns (e.g. 6) in session state. Use the full window (not just the bare latest message) to construct the retrieval query, and include it in the generation prompt.

**Acceptance criteria:**
- [ ] A follow-up question that only makes sense given a prior turn (e.g. "how about Microsoft?" after asking about Apple's revenue) retrieves the correct company's chunks (FR2, ADR-006)
- [ ] The window caps at N turns — older turns are not included directly in the retrieval query or prompt once compaction (task 4.2) is in place
- [ ] Demoable or verifiable in isolation (scripted 2–3 turn conversation with an elliptical follow-up)

### 4.2 Compaction

- **Type:** AFK
- **Blocked by:** 4.1
- **PRD reference:** FR2
- **System design reference:** `docs/adr/ADR-006-conversation-memory.md`

**Scope:** When a turn ages out of the bounded window, fold it into a running LLM-generated conversation summary instead of dropping it. The summary is included in every subsequent prompt alongside the current window.

**Acceptance criteria:**
- [ ] A scripted conversation exceeding the window size (e.g. 8+ turns) produces a non-empty running summary reflecting the earliest turns (ADR-006)
- [ ] Answers late in a long conversation remain coherent with respect to early-conversation context, despite the window truncating raw turns
- [ ] Demoable or verifiable in isolation (scripted conversation longer than the window size)

### 4.3 In-session episodic memory

- **Type:** AFK
- **Blocked by:** 4.2
- **PRD reference:** FR2, PRD §7 Success Criteria (multi-turn)
- **System design reference:** `docs/adr/ADR-006-conversation-memory.md`, §3 Data Model

**Scope:** Extract structured facts per turn (`{turn, company, metric, quarter, value}`) into a session-scoped list, held in memory only (not persisted to disk, not available across sessions — this is explicitly in-session only per ADR-006).

**Acceptance criteria:**
- [ ] A fact established early in a scripted conversation (e.g. turn 2) is still correctly referenced in a later answer (e.g. turn 10) after compaction has folded turn 2's raw content away (ADR-006, PRD §7)
- [ ] Episodic memory is empty/reset at the start of a new session (no cross-session persistence — ADR-006)
- [ ] Demoable or verifiable in isolation (scripted long conversation referencing an early fact after compaction)
