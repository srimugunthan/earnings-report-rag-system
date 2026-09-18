# PRD: Earnings Report RAG Chat System

Status: Draft — open decisions in §9 need answers before/while building.

## 1. Problem

Reading quarterly earnings PDFs to answer specific questions ("what was Azure growth?", "summarize Apple's quarter") is slow and manual. We want a chat interface backed by retrieval-augmented generation (RAG) over a local folder of earnings report PDFs, so answers are fast, grounded in the actual filings, and easy to verify.

## 2. Goals

- Chat with a corpus of quarterly earnings report PDFs in natural language.
- Every answer is grounded in the ingested reports — no fabricated numbers.
- Every answer cites where it came from (source document and page).
- Usable as an interactive chat session, not just a library call.

## 3. Non-Goals (v1)

- No automated fetching of filings from SEC EDGAR or the web — PDFs are placed into the data folder manually.
- No multi-user auth, accounts, or hosted deployment.
- No forecasting/predictive analytics.
- No editing/annotation of source PDFs.
- No external links (IR pages, SEC EDGAR, analyst commentary, etc.) attached to answers — deferred to a future iteration (see §11); v1 grounds answers with internal PDF/page citations only.

## 4. Users & Example Queries

Primary user: a single analyst/researcher (you), running this locally.

Representative queries the system must handle:
- "Summarize the earnings report of Apple."
- "What was Apple's total revenue in Q3 2024?"
- "How much did Microsoft's Azure grow?"
- "What is Google Cloud's operating margin?"
- Comparison-style: "Which company had better cloud growth, Azure or Google Cloud?"

## 5. Functional Requirements

| # | Requirement |
|---|---|
| FR1 | Ingest all PDFs placed in the data folder, extract text, chunk, embed, and store in a vector index. |
| FR2 | Provide a chat interface that accepts free-text questions and returns an answer in the same session (multi-turn). |
| FR3 | Answers are generated only from retrieved chunks of ingested reports. If no relevant chunk is found, the system says so explicitly instead of guessing. |
| FR4 | Each answer names the specific source document (and page, where available) the answer was drawn from. |
| FR5 | Support both summarization queries ("summarize X's earnings") and point-lookup queries ("what was metric Y"). |
| FR6 | Support filtering/scoping by company when the question names one, so answers aren't mixed across companies. |
| FR7 | Re-running the app does not require re-ingesting unchanged PDFs — the vector index persists across sessions. |
| FR8 | Dropping a new PDF into the data folder and re-running ingestion makes it queryable without code changes. |

## 6. Non-Functional Requirements

- Runs entirely locally (Python); the only external dependency is an LLM API for answer generation.
- Interactive latency: a query should return an answer within a few seconds for a corpus of this size (single digits of companies/quarters).
- No secrets committed to the repo; API keys come from `.env` (already scaffolded via `.env.example`).

## 7. Success Criteria

- For each PDF currently in `data/sample_earnings/` (AMZN, MSFT, GOOG, plus the slides deck), the system correctly answers at least one factual question about it, with a citation pointing to that document.
- A question with no support in the corpus (e.g., asking about a company never ingested) produces an explicit "not found in the ingested reports" response, not a fabricated number.
- A user can hold a multi-turn conversation (ask a follow-up question referring to the previous answer) without re-starting.

## 8. Constraints & Assumptions

- This repo already has a working prototype (`prototype/core/document_loader.py`, `text_chunker.py`, `embeddings.py`, `vector_store.py`, `prototype/rag/pipeline.py`, `prototype/earnings/analyzer.py`). The PRD assumes we build on top of this rather than rewriting it, unless a requirement conflicts with how it currently works.
- PDFs currently live in `data/sample_earnings/`, not directly in `data/`. Filenames are inconsistent (e.g. `AMZN-Q2-2026-Earnings-Release.pdf` vs `FY26 Q2 - Press Releases - Investor Relations - Microsoft.pdf` vs `GOOG-10-Q-Q2-2026.pdf`), so company/quarter metadata can't be assumed to be reliably parseable from filenames alone.
- No `.env` file exists yet and no LLM/search API keys are currently set in the environment — these will need to be supplied before the system can generate answers.

## 9. Open Decisions

These are choices that change the implementation and were deliberately left unresolved rather than assumed:

1. **Chat interface medium** — terminal CLI chat loop, a Streamlit web app (already installed in this env), or both sharing one query function underneath. *(Settled: Streamlit — see `docs/adr/ADR-001-chat-interface-streamlit.md`.)*
2. **LLM provider for answer generation** — OpenAI (what the current prototype hardcodes) vs Anthropic (also slotted in `.env.example` but not wired up in code). *(Settled: Anthropic, Claude Haiku — cheap/fast model for answer generation; requires wiring `langchain-anthropic` in place of the hardcoded `ChatOpenAI`.)*
3. **Data folder layout** — ingest recursively from `data/` (covering the existing `data/sample_earnings/` subfolder) vs requiring a flat `data/*.pdf` layout as literally described in the request. *(Settled: reorganize into per-company subfolders, `data/<TICKER>/*.pdf` — see `docs/adr/ADR-002-data-folder-organization.md`. Note: this settles company attribution only; quarter/year metadata is still item 4 below, and now carries more weight given anticipated year-over-year queries.)*
4. **How company/quarter metadata is derived**, given inconsistent filenames — options: parse from filename with a best-effort heuristic, extract from the PDF's own text (e.g. first page), or require a small manifest/sidecar file mapping filename → company/quarter. *(Settled: company via folder name, ADR-002. Quarter/year via regex/keyword extraction from page-1 text, falling back to `unknown` (excluded from period-scoped/YoY filtering, not blocked from ingestion) when no pattern matches — see `docs/adr/ADR-008-quarter-year-extraction.md`.)*

## 10. Milestones (tentative, pending §9)

1. Ingestion: point loader at the real `data/` PDFs, resolve metadata extraction (§9.4), persist vector index.
2. Grounded Q&A: retrieval + LLM answer generation with mandatory source citation, refuses when ungrounded.
3. Chat interface: build per §9.1 (Streamlit).
4. Verify against Success Criteria (§7) using the existing sample PDFs.

## 11. Future Enhancements (Post-v1)

- **External links to substantiate answers.** Deferred out of v1 scope (§3). When this is revisited, the options considered were:
  - (a) Curated static links per company (investor relations page, SEC EDGAR filing page, stock/finance page) attached deterministically from the company ticker — no extra API, no extra cost.
  - (b) Live web search (e.g. via a search API) for news/analyst commentary relevant to the specific question — requires a new API key, adds latency and cost, but is query-specific and current.
  - No decision was made between these; re-grill when this feature is prioritized.
