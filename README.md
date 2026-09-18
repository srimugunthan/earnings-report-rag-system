# Earnings Report RAG Chat System

A local, single-user chat app for asking natural-language questions about quarterly earnings
report PDFs — "What was AWS revenue growth in Q2 2026?", "Summarize Amazon's earnings report",
"How about Microsoft's cloud revenue?" — and getting answers grounded exclusively in the
ingested reports, with source document and page citations. Retrieval-only degraded mode kicks
in automatically whenever the LLM is unavailable, rather than failing outright.

Built from a PRD, a grilled system design, and a decision log — see **Documentation map**
below for the full paper trail.

## How it works

```
python src/ingest.py          # scan data/<TICKER>/*.pdf, chunk, embed, persist to Chroma
streamlit run src/app.py      # chat with the ingested corpus
```

1. Drop earnings report PDFs into `data/<TICKER>/` (e.g. `data/AMZN/*.pdf`).
2. Run the ingestion CLI. It's a manual, explicit step (never auto-triggered) — see
   [ADR-005](docs/adr/ADR-005-ingestion-trigger.md).
3. Launch the Streamlit chat app and ask questions. Answers are grounded in retrieved excerpts,
   cited by source filename + page range, with graceful degradation if the LLM is unavailable.

## Setup

```bash
git clone <this repo>   # or just cd into it
cd earnings-rag-system
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# edit .env and set ANTHROPIC_API_KEY (optional — the app runs in retrieval-only
# degraded mode without one, per ADR-007)
```

Then ingest and run as shown above.

## Project structure

```
src/                  Application code (see below)
data/<TICKER>/*.pdf   Earnings report PDFs, one folder per ticker (ADR-002)
data/vector_db/       Persisted Chroma vector store (created by ingest.py)
test/                 BDD test suite (behave) — see test/README.md
test_results/         Manual verification write-ups, one per phase
specs/                Phase-by-phase implementation plan (spec-driven development)
docs/adr/             Architecture Decision Records
PRD.md                Product requirements
system-design.md      System design derived from the PRD
decision-log.md       Complete record of every design decision, ADR or not
prototype/            Earlier exploratory scaffold — superseded by src/, kept for reference
```

### `src/`

| File | Role |
|---|---|
| `ingest.py` | Ingestion CLI: discovers PDFs, derives company/quarter/year metadata, chunks across page boundaries with page-range tracking, embeds, and persists to Chroma. |
| `rag_query.py` | RAG Query Engine: single-turn retrieval + grounded generation (Claude Haiku) with citations, explicit "not found" refusal, and LLM-unavailability fallback. |
| `conversation.py` | Conversation Memory: bounded turn window, LLM-driven compaction summary, and in-session episodic fact memory — makes the query engine conversation-aware. |
| `app.py` | Streamlit chat UI wiring it all together, with a startup check that refuses to run against a missing/empty vector store. |

Each file corresponds to one phase of `specs/earnings-rag-chat-system/` and was built and
verified in that order — see `implementation-order.md` there for why.

## Usage

**Ingest** (rerun any time you add/update PDFs under `data/<TICKER>/`; every run fully
reprocesses the corpus, there's no incremental change detection — ADR-005):

```bash
python src/ingest.py
```

**Chat**:

```bash
streamlit run src/app.py
```

Opens at `http://localhost:8501`. If you haven't ingested anything yet, it'll tell you to run
`ingest.py` first rather than crash or silently start an empty chat.

## Testing

Two complementary layers:

- **Automated BDD suite** (`behave`, mocked LLM, no API key needed):
  ```bash
  behave test/features
  ```
  See [test/README.md](test/README.md) for scope and design notes.

- **Manual verification write-ups**, one per phase, with exact reproduction steps — including
  what was actually run and observed during development:
  [test_results/test_phase1.md](test_results/test_phase1.md) ·
  [test_phase2.md](test_results/test_phase2.md) ·
  [test_phase3.md](test_results/test_phase3.md) ·
  [test_phase4.md](test_results/test_phase4.md) ·
  [test_phase5.md](test_results/test_phase5.md) (the Streamlit UI itself needs a browser, so
  most of that one is a manual checklist rather than something scripted).

## Documentation map

| Document | What it's for |
|---|---|
| [PRD.md](PRD.md) | Requirements, goals, non-goals, example queries |
| [system-design.md](system-design.md) | Component boundaries, data model, data flow, failure modes |
| [decision-log.md](decision-log.md) | Every design decision made, with alternatives considered |
| [docs/adr/](docs/adr/) | Standalone ADRs for decisions that cleared the "hard to reverse" bar |
| [specs/earnings-rag-chat-system/](specs/earnings-rag-chat-system/) | Phase-by-phase task breakdown with acceptance criteria |

## Key design choices (see decision-log.md for the full reasoning)

- **Vector store**: Chroma, local persistent client — no server process ([ADR-003](docs/adr/ADR-003-vector-store-chroma.md)).
- **Embeddings**: HuggingFace `sentence-transformers/all-MiniLM-L6-v2`, local and free.
- **LLM**: Anthropic Claude Haiku via `langchain-anthropic`.
- **Chat UI**: Streamlit, calling the RAG pipeline in-process — no REST API layer ([ADR-001](docs/adr/ADR-001-chat-interface-streamlit.md)).
- **Company attribution**: derived deterministically from the ticker folder name, not parsed from filenames or content ([ADR-002](docs/adr/ADR-002-data-folder-organization.md)).
- **Chunking**: PDF pages are merged before splitting, so a chunk can span a page boundary and still carry an accurate page-range citation ([ADR-004](docs/adr/ADR-004-cross-page-chunking.md)).
- **LLM fallback**: one unified retrieval-only degraded mode for both a missing API key and a runtime call failure ([ADR-007](docs/adr/ADR-007-llm-fallback.md)).
- **Conversation memory**: bounded window + LLM-generated compaction summary + in-session episodic facts, so follow-ups and long conversations stay coherent without unbounded prompt growth ([ADR-006](docs/adr/ADR-006-conversation-memory.md)).

## Non-goals (v1)

No automated SEC EDGAR/web fetching (PDFs are added manually), no multi-user auth or hosted
deployment, no forecasting/predictive analytics, no external links substantiating answers. See
[PRD.md §3](PRD.md) for the full list.
