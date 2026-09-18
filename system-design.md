# System Design: Earnings Report RAG Chat System

> Derived from PRD: `PRD.md`. Every decision below was either stated by the
> PRD or settled through a grilling session with the project owner — none
> were assumed. The complete decision record lives in `decision-log.md`.

## 1. Overview

A local, single-user RAG chat application for quarterly earnings report PDFs. A user drops PDFs into per-company folders under `data/`, runs an explicit ingestion command to index them, then chats with the corpus through a Streamlit interface. Answers are grounded exclusively in retrieved report excerpts, cited by source document and page range, and the app degrades gracefully to a retrieval-only mode whenever the LLM is unavailable rather than failing outright. This satisfies PRD FR1–FR8 (ingestion, persistent multi-turn chat, grounded answers, citations, summarization/point-lookup queries, company-scoped filtering, cross-session index persistence, new-PDF pickup), while PRD §3/§11 explicitly defer external-link substantiation to a future iteration.

## 2. Component Boundaries

```
                     (run manually, e.g. quarterly)
        +--------------------+
        |     ingest.py      |
        |  (Ingestion CLI)   |
        +----------+---------+
                    |
                    | load -> derive metadata -> chunk -> embed
                    v
        +--------------------+
        |    Vector Store     |
        |  (Chroma, local     |
        |   persistent)       |
        +----------+---------+
                    ^
                    | similarity search (company-filtered)
                    |
        +-----------+--------+        +------------------------+
        |  RAG Query Engine  | <----> |  Conversation Memory    |
        |  (retrieval + LLM   |        |  (session_state: window,|
        |   generation)       |        |   compaction summary,   |
        +-----------+--------+        |   episodic facts)       |
                    |                  +------------------------+
                    | answer + citations (or degraded fallback)
                    v
        +--------------------+
        |      Chat UI         |
        |    (Streamlit)        |
        +--------------------+
                    ^
                    |
                User (browser, local)
```

- **Ingestion CLI (`ingest.py`)** — standalone script, run manually by the user (`docs/adr/ADR-005-ingestion-trigger.md`). Owns discovery, loading, metadata derivation, chunking, embedding, and writing to the vector store. Also owns two validation checks: rejecting/warning on non-canonical ticker folder names (decision-log row 13) and skipping files with no usable extracted text (row 12). Never invoked by the chat app.
- **Vector Store (Chroma)** — owns persisted chunk text, embeddings, and metadata. The only component both Ingestion and the RAG Query Engine touch (`docs/adr/ADR-003-vector-store-chroma.md`).
- **RAG Query Engine** — the retrieval + generation core, called in-process by the Chat UI (no REST API layer — `docs/adr/ADR-001-chat-interface-streamlit.md`). Owns conversation-aware retrieval, prompt assembly, the LLM call, and the fallback to retrieval-only mode.
- **Conversation Memory** — session-scoped bounded window, compaction summary, and episodic fact list (`docs/adr/ADR-006-conversation-memory.md`), held in Streamlit `session_state`. Read and written by the RAG Query Engine each turn; never persisted to disk.
- **Chat UI (Streamlit)** — renders the conversation, accepts input, displays citations and the "LLM unavailable" notice when degraded. Calls the RAG Query Engine directly as a Python function.

## 3. Data Model

- **Chunk** — `{text, embedding, metadata: {company, quarter, year (or "unknown"), page_start, page_end, source_filename}}`. Owned by the Vector Store; written by the Ingestion CLI. `company` comes from the parent folder name (ADR-002); `quarter`/`year` from regex extraction, defaulting to `"unknown"` (ADR-008); `page_start`/`page_end` from character-offset-to-page tracking across merged pages (ADR-004).
- **Conversation turn** — `{role, content}`. Owned by Conversation Memory, part of the bounded window.
- **Compaction summary** — a single running string representing turns that aged out of the window. Owned by Conversation Memory (ADR-006).
- **Episodic fact** — `{turn, company, metric, quarter, value}`. Owned by Conversation Memory, session-scoped list, survives compaction within a session but never across sessions (ADR-006).

## 4. Interfaces / APIs

| Caller → Callee | Contract |
|---|---|
| Ingestion CLI → Vector Store | In-process Chroma client write (add chunks + metadata). No network hop. |
| RAG Query Engine → Vector Store | In-process Chroma client read: `similarity_search(query, filter={"company": ...})` for FR6/FR7 company-scoped filtering. |
| RAG Query Engine → LLM (Anthropic Claude Haiku) | Request/response over Anthropic's API via `langchain-anthropic`'s `ChatAnthropic`, wrapped in error handling that triggers the retrieval-only fallback on failure (ADR-007). |
| Chat UI → RAG Query Engine | Direct in-process function call, e.g. `query(question, session_state) -> {answer, citations, degraded: bool}`. No REST/HTTP layer (ADR-001). |
| RAG Query Engine ↔ Conversation Memory | In-process read/write of Streamlit `session_state`. |

## 5. Data Flow

**Ingestion (manual, periodic — typically per quarterly earnings release):**
```
User runs `python ingest.py`
  -> scan data/<TICKER>/*.pdf                                   (ADR-002)
  -> for each TICKER folder:
       validate folder name is a clean uppercase ticker,
       warn/reject otherwise                                    (row 13)
  -> for each PDF:
       load pages (PyPDFLoader)
       if extracted text is near-empty (e.g. scanned/
       image-only PDF): skip file, warn in run summary          (row 12)
       company = parent folder name                             (ADR-002)
       quarter/year = regex-extract from page-1 text,
                       else "unknown"                            (ADR-008)
       merge pages, chunk across page boundaries,
       track page ranges                                        (ADR-004)
       embed each chunk
       write chunk + metadata to Chroma                         (ADR-003)
  -> print run summary, flagging files that landed in
     quarter/year = "unknown" and files skipped as unreadable    (ADR-008, row 12)
```
Every PDF under `data/` is fully reprocessed on each run — there is no change-detection manifest (ADR-005).

**Chat app startup:**
```
Streamlit app launches
  -> open the persisted Chroma store
  -> if missing/corrupted: show a clear error directing the
     user to run `python ingest.py` first; do not attempt to
     auto-rebuild or fall back to an empty-chat state          (row 11)
```

**Query (interactive, every chat turn):**
```
User types a question in the Streamlit chat
  -> Conversation Memory: build retrieval query from
     (bounded raw window + compaction summary + current question) (ADR-006)
  -> RAG Query Engine: similarity search in Chroma,
     filtered by company if one is named in the question           (FR6)
  -> assemble prompt: retrieved chunks + citations
     + bounded window + compaction summary
  -> call Claude Haiku
       success -> generated answer + citations
       failure/no key -> fall back to retrieval-only: raw
                          excerpts + citations + on-screen notice  (ADR-007)
  -> Conversation Memory: append turn to window, extract facts
     into episodic memory, compact any turn aging out of
     the window into the running summary                          (ADR-006)
  -> Chat UI renders the answer (or degraded response) with citations
```

## 6. Storage & Persistence

| Data | Store | Persistence |
|---|---|---|
| Chunk text, embeddings, metadata | Chroma, local persistent client | Persists across sessions on local disk (FR7, ADR-003) |
| Conversation window, compaction summary, episodic facts | Streamlit `session_state` | In-memory only; lost when the app closes (ADR-006, deliberately not cross-session) |
| Ingestion state | None (no manifest) | Every explicit `ingest.py` run fully reprocesses `data/` (ADR-005) |
| API keys | `.env` | Local file, never committed (PRD §6) |

## 7. Non-Functional Requirements

- Runs entirely locally; no hosted deployment (PRD §3, §6).
- Interactive query latency target: a few seconds (PRD §6) — retrieval is local (Chroma), and generation uses Claude Haiku, a fast/cheap model (decision-log row 3).
- Ingestion latency is not interactively constrained, since it's a deliberate, infrequent, manual action (ADR-005); a full reprocess of the small corpus is acceptable even if slower than an incremental approach would be.
- These targets are based on the corpus staying small (a handful of companies/quarters), consistent with PRD §3's Non-Goals; they are not validated against any larger load.

## 8. Security & Compliance

- Single local user; no authentication, authorization, or multi-tenancy (PRD §3 Non-Goals).
- API key(s) supplied via `.env`, never committed to version control (PRD §6).
- Earnings reports are public company disclosures; no PII or other regulated data identified in scope.

## 9. Deployment & Operability

- Ships as a local Python application: install `requirements.txt`, configure `.env`, run `python ingest.py` after adding/updating PDFs, then `streamlit run <app>.py` to chat.
- No CI/CD or hosted rollout — there is no deployment target beyond the user's own machine.
- Observability is limited to the `ingest.py` run summary (which files were processed, which landed in `quarter/year = unknown`, per ADR-008's follow-up). No further logging/monitoring infrastructure is in scope for v1.
- No formal rollback strategy is needed beyond normal local version control, since there's no shared/hosted deployment to roll back.

## 10. Failure Modes

| Failure | Behavior | Severity |
|---|---|---|
| LLM unavailable (no API key, or a runtime call failure) | Falls back to retrieval-only response (raw excerpts + citations) with an on-screen notice | Soft — app stays usable (ADR-007) |
| No relevant retrieval result for a question | Explicit "not found in the ingested reports" answer, not a fabricated one | Soft — by design (FR3) |
| PDF's quarter/year unparseable at ingestion | Ingested anyway with `quarter/year = unknown`; excluded from period-scoped/YoY queries, still retrievable generally; flagged in the ingest run summary | Soft — by design (ADR-008) |
| Vector store missing or corrupted at chat-app startup | Clear error directing the user to run `python ingest.py` first; no auto-rebuild, no degraded empty-chat fallback | Hard dependency — app cannot function until ingestion is run (decision-log row 11) |
| Malformed or unreadable PDF (e.g. scanned/image-only, no extractable text) at ingestion | File is skipped with a warning in the `ingest.py` run summary; ingestion of the rest of the batch continues | Soft — one bad file never blocks the rest of the batch (decision-log row 12) |
| Non-canonical ticker folder name (e.g. "Google" instead of "GOOGL") | Warned/rejected at ingestion time | Soft — caught before it can silently reintroduce company-attribution ambiguity (decision-log row 13) |

## 11. Open Risks / Deferred Decisions

- **External links to substantiate answers** — explicitly deferred to a future iteration (PRD §3, §11). Two mechanism options are preserved there for when it's revisited.

All other gaps flagged in an earlier draft of this document (vector store missing/corrupted, malformed PDF handling, ticker folder canonicalization, embeddings provider) have since been grilled and settled — see decision-log rows 11–14, reflected in §5 and §10 above.

## 12. Decisions & ADRs

The complete decision record lives in `decision-log.md`. Decisions that cleared the three-part ADR bar:

| ADR | Title |
|-----|-------|
| `docs/adr/ADR-001-chat-interface-streamlit.md` | Use Streamlit for the chat interface (not a React frontend) |
| `docs/adr/ADR-002-data-folder-organization.md` | Organize earnings PDFs into per-company subfolders under `data/` |
| `docs/adr/ADR-003-vector-store-chroma.md` | Use Chroma as the vector store backend |
| `docs/adr/ADR-004-cross-page-chunking.md` | Merge PDF pages before chunking, allowing chunks to span page boundaries |
| `docs/adr/ADR-005-ingestion-trigger.md` | Ingestion is a separate, manually-triggered command, not startup-triggered |
| `docs/adr/ADR-006-conversation-memory.md` | Conversation memory — retrieval-aware bounded window with compaction and in-session episodic memory |
| `docs/adr/ADR-007-llm-fallback.md` | Unified retrieval-only fallback when the LLM is unavailable |
| `docs/adr/ADR-008-quarter-year-extraction.md` | Derive quarter/year metadata via regex extraction, defaulting to "unknown" on failure |

Several logged decisions did not clear the bar and have no ADR (see `decision-log.md` for the full list and reasoning per row) — mostly low-switching-cost choices or direct applications of an already-recorded ADR's reasoning, rather than independent architectural forks.
