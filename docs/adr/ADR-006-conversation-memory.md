# ADR-006: Conversation memory — retrieval-aware bounded window with compaction and in-session episodic memory

**Status:** Accepted
**Date:** 2026-09-17
**Deciders:** Project owner

---

## Context

FR2 requires a multi-turn chat where a follow-up question referring to a previous answer works correctly. Retrieval is driven by embedding a query for similarity search; a follow-up phrased elliptically (e.g. "how about Microsoft?" or "how did that compare to last quarter?") cannot be embedded meaningfully on its own — if retrieval only ever sees the raw latest message, it can pull irrelevant chunks regardless of what the LLM sees during generation, silently undermining FR3's grounding requirement. It was settled that retrieval must be conversation-aware, not retrieval-naive.

Separately, sessions may run long across multiple companies and quarters. An unbounded raw-history append would grow the prompt indefinitely (cost and eventual context-limit issues), but naively truncating to a fixed window of recent turns loses information a later question might still need to reference (e.g. a fact established many turns earlier).

The project is explicitly scoped to a single local user; only the document vector store is required to persist across sessions (FR7 / ADR-003). Persisting conversation history across separate app sessions was considered and rejected here as an unstated expansion beyond the PRD's stated goals — it is not required by any current requirement.

---

## Decision

Conversation memory will be implemented with three parts:

1. **Bounded window** — the last N raw turns (e.g. 6) are kept verbatim and used directly for both retrieval-query construction and the generation prompt.
2. **Compaction** — when a turn ages out of the window, it is folded into a running, LLM-generated conversation summary that continues to ride along in every subsequent prompt, keeping long sessions coherent without unbounded prompt growth.
3. **Episodic memory (in-session only)** — a structured list of facts extracted per turn (company, metric, quarter, value) held in the chat app's session state, letting later questions reference specific earlier findings even after compaction has folded the raw turn away. This is explicitly scoped to the current session only — ephemeral, not persisted to disk, and lost when the app closes.

---

## Alternatives Considered

| Option | Pros | Cons |
|--------|------|------|
| Retrieval-naive (embed only the raw latest message; full history feeds generation only) | Simplest, no added complexity | Follow-ups that don't restate context retrieve poorly — directly threatens FR3 grounding and the FR2 multi-turn success criterion |
| Unbounded raw history append, no window, no compaction | Simple, no information loss within a session | Prompt size (and cost/latency) grows without bound over a long session; eventually exceeds context limits |
| **Bounded window + compaction + in-session episodic memory (chosen)** | Retrieval-aware follow-ups work correctly; long sessions stay coherent via the running summary; specific facts remain referenceable via episodic memory even after compaction; prompt size stays bounded | Real added implementation complexity (a compaction LLM call, structured fact extraction, session-state bookkeeping) relative to a single-user local Q&A tool's modest baseline need |
| Cross-session persisted episodic memory | Recalls findings from prior sessions (e.g. "what did I ask about Apple last time") | Not required by any current PRD goal; adds a second persistence mechanism alongside the document vector store; raises unresolved questions (pruning, scoping) — explicitly rejected here as an unstated scope increase |

---

## Consequences

**Positive:**
- Multi-turn follow-ups work correctly at the retrieval level, not just generation — satisfying the FR2 success criterion robustly rather than only superficially.
- Sessions can run long across many companies/quarters without prompt size growing unbounded or losing earlier context entirely.
- Specific facts established earlier in a session remain recoverable mid-session even after their raw turn has been compacted away.

**Negative / Accepted Tradeoffs:**
- This is real, non-trivial complexity for what is otherwise a simple local Q&A tool — the compaction summary call, structured fact extraction, and session-state bookkeeping are new subsystems, not configuration flags.
- Deliberately scoped to in-session only. A future need for cross-session recall of conversation history would require its own follow-up design decision (persistence mechanism, retention/pruning policy) rather than being an extension of this one.

---

## Follow-up Actions

- [ ] Implement the bounded window (e.g. last 6 turns) feeding both retrieval-query construction and the generation prompt.
- [ ] Implement compaction: an LLM call that folds turns aging out of the window into a running conversation summary.
- [ ] Implement in-session episodic memory: structured fact extraction per turn, held in `st.session_state`, explicitly not persisted to disk.
- [ ] If cross-session recall is ever desired, treat it as a new PRD goal requiring its own design decision, not an extension of this ADR.
