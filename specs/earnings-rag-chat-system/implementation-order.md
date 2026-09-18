# Implementation Order

Phases must be implemented in this order. Order is derived from the system
design's technical dependency graph (schema/ingestion before retrieval,
retrieval before its extensions, extensions before the UI that wraps them) —
NOT from PRD feature priority. Each phase is independently testable in
isolation before moving to the next.

| Order | Phase file | Depends on | Design components | Independently testable when |
|-------|-----------|------------|--------------------|------------------------------|
| 1 | `phase1-ingestion-pipeline.md` | None | Ingestion CLI (§2), Chunk data model (§3), Ingestion flow (§5), Storage (§6); ADR-002, ADR-004, ADR-008 | `python ingest.py` run against the sample PDFs produces correct chunks/metadata in Chroma, inspectable directly — no UI or LLM needed |
| 2 | `phase2-retrieval-generation.md` | Phase 1 | RAG Query Engine (§2), Interfaces (§4), Query flow core (§5) | Calling the query function directly (script/REPL) with example questions returns grounded, cited answers, and an explicit "not found" for out-of-corpus questions — no UI needed |
| 3 | `phase3-llm-fallback.md` | Phase 2 | Failure Modes — LLM unavailable (§10); ADR-007 | Simulating a missing API key and a forced LLM call failure both return the same retrieval-only degraded response shape, verifiable via the query function directly |
| 4 | `phase4-conversation-memory.md` | Phase 2 | Conversation Memory (§2, §3), Data Flow (§5); ADR-006 | A scripted multi-turn conversation (including one exceeding the window size) shows correct follow-up retrieval, compaction, and episodic-fact recall — no UI needed |
| 5 | `phase5-chat-ui.md` | Phases 3, 4 (and transitively 1) | Chat UI (§2), startup/render flow (§5); ADR-001; decision-log row 11 | Launching `streamlit run` gives a working chat end-to-end: happy path, degraded mode, multi-turn, and a missing-store error state |

## Dependency notes

- **Phases 3 and 4 can be built in parallel.** Both are independent extensions of Phase 2's core query function — Phase 3 wraps LLM failure handling, Phase 4 wraps conversation state — and neither depends on the other. They're listed sequentially here for review simplicity, but there's no technical reason they couldn't be developed side by side once Phase 2 is done.
- **Phase 5 depends on Phase 1 as well as Phases 3/4**, even though that's not a direct chain: its startup check (task 5.4) reads the Chroma store Phase 1 populates, independent of the query path Phases 2–4 built.
- All other phases are strictly sequential — Phase 2 cannot be meaningfully tested without Phase 1's real ingested data, and Phase 5 needs the fully wrapped (fallback + conversation-aware) query function from Phases 3 and 4.

## Do not reorder

Do not start a phase before its listed dependencies are complete and verified.
If a later phase reveals that an earlier phase's design assumption was wrong,
stop and flag it — don't silently patch it forward.
