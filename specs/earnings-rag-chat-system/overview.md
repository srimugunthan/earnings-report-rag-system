# Earnings RAG Chat System — Overview

## Source documents

- **PRD:** `PRD.md`
- **System design:** `system-design.md`

## Goal

Build a local, single-user chat interface for asking natural-language questions about quarterly earnings report PDFs (e.g. "What was Apple's total revenue in Q3 2024?", "How much did Microsoft's Azure grow?", "Summarize the earnings report of Apple") and getting answers grounded exclusively in the ingested reports, with source and page citations. The system ingests PDFs from a local folder, retrieves relevant excerpts via a vector store, and generates answers with an LLM — degrading gracefully to a retrieval-only mode whenever the LLM is unavailable rather than failing outright.

## Scope

- Ingesting earnings report PDFs from `data/<TICKER>/*.pdf` into a persisted vector store (FR1).
- A multi-turn Streamlit chat interface (FR2).
- Answers grounded only in retrieved report content, with an explicit "not found" response when nothing relevant exists in the corpus (FR3).
- Source document + page-range citations on every answer (FR4).
- Both summarization-style and point-lookup queries (FR5).
- Company-scoped filtering so answers aren't mixed across companies (FR6).
- A vector index that persists across sessions (FR7) and picks up newly added PDFs on the next explicit ingestion run (FR8/FR9).

## Non-goals

- Automated fetching of filings from SEC EDGAR or the web — PDFs are added manually.
- Multi-user auth, accounts, or hosted deployment.
- Forecasting/predictive analytics.
- External links (IR pages, SEC EDGAR, analyst commentary) substantiating answers — explicitly deferred to a future iteration (PRD §11).

## Phases

| Phase | File | Summary | Depends on |
|-------|------|---------|------------|
| 1 | `phase1-ingestion-pipeline.md` | Ingest PDFs from `data/<TICKER>/` into Chroma with company/quarter/page-range metadata, validation, and a run summary | None |
| 2 | `phase2-retrieval-generation.md` | Company-scoped retrieval + grounded, cited answer generation, with explicit "not found" when ungrounded | Phase 1 |
| 3 | `phase3-llm-fallback.md` | Retrieval-only degraded mode when the LLM is unavailable (missing key or runtime failure) | Phase 2 |
| 4 | `phase4-conversation-memory.md` | Multi-turn conversation memory: bounded window, compaction, in-session episodic memory | Phase 2 |
| 5 | `phase5-chat-ui.md` | Streamlit chat shell wiring everything together, including degraded-mode and missing-store UI states | Phases 3, 4 |

See `implementation-order.md` for the full dependency detail and
`README.md` for how to work through this folder.
