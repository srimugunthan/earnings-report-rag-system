# Phase 1: Data Model & Ingestion Pipeline

**Depends on:** None — can start immediately
**Status:** Not started

## Design components touched

Ingestion CLI (`system-design.md` §2), Chunk data model (§3), Ingestion data flow (§5), Storage & Persistence (§6); `docs/adr/ADR-002-data-folder-organization.md`, `docs/adr/ADR-003-vector-store-chroma.md`, `docs/adr/ADR-004-cross-page-chunking.md`, `docs/adr/ADR-008-quarter-year-extraction.md`; decision-log rows 12–14.

## Objective

A standalone `ingest.py` command that, when run manually, discovers all PDFs under `data/<TICKER>/`, loads and chunks them (allowing chunks to span page boundaries, with accurate page-range citations), derives company and quarter/year metadata, validates folder naming and skips unreadable files, embeds each chunk, and writes everything to a persisted local Chroma vector store. Running it twice on unchanged data fully reprocesses everything (no incremental change detection — ADR-005).

## Independently testable when

`python ingest.py` run against the existing sample PDFs (`data/AMZN/...`, `data/MSFT/...`, `data/GOOG/...`, plus the slides deck) completes and the resulting Chroma store, inspected directly (e.g. via a small script calling `collection.get()` or a similarity query), contains chunks with correct `company`, `quarter`/`year` (or `"unknown"`), `page_start`/`page_end`, and `source_filename` metadata. No chat UI or LLM call is needed to verify this phase.

## Tasks

### 1.1 Minimal end-to-end ingest for one PDF

- **Type:** AFK
- **Blocked by:** None
- **PRD reference:** FR1
- **System design reference:** §2 Ingestion CLI, §5 Ingestion flow, §6 Storage

**Scope:** Discover PDFs under `data/<TICKER>/*.pdf`, load each with `PyPDFLoader`, derive `company` from the parent folder name, chunk with the existing (single-page) `RecursiveCharacterTextSplitter` behavior as a placeholder, embed with the existing HuggingFace default, and write to a local persistent Chroma collection. Does **not** yet cover cross-page chunking, quarter/year extraction, validation, or the run summary — those are separate slices below.

**Acceptance criteria:**
- [ ] Running `ingest.py` against one sample PDF produces chunks in Chroma with correct `company` metadata (FR1)
- [ ] Chunk text and embeddings are present and queryable via a direct Chroma similarity search (§6 Storage)
- [ ] Demoable or verifiable in isolation (inspect the Chroma store directly)

### 1.2 Cross-page chunking + page-range citation tracking

- **Type:** AFK
- **Blocked by:** 1.1
- **PRD reference:** FR4
- **System design reference:** `docs/adr/ADR-004-cross-page-chunking.md`, §3 Data Model

**Scope:** Merge each PDF's pages into one text stream per document before chunking, allowing chunks to span page boundaries. Track character-offset-to-page mapping through the merge so each resulting chunk carries accurate `page_start`/`page_end` metadata (a range when a chunk spans pages).

**Acceptance criteria:**
- [ ] A chunk that spans two pages carries the correct `page_start`/`page_end` range, not a single arbitrary page (FR4)
- [ ] A chunk fully within one page carries `page_start == page_end` (ADR-004)
- [ ] Demoable or verifiable in isolation (ingest a multi-page sample PDF, inspect chunk metadata)

### 1.3 Quarter/year regex extraction with `unknown` fallback

- **Type:** AFK
- **Blocked by:** 1.1
- **PRD reference:** PRD §9 item 4
- **System design reference:** `docs/adr/ADR-008-quarter-year-extraction.md`

**Scope:** Extract `quarter`/`year` from each PDF's page-1 (with early-page fallback) text via regex/keyword search for common reporting-period patterns (e.g. "Quarter Ended", "QX FY/CY YYYY", "Third Quarter YYYY"). When no pattern confidently matches, set `quarter`/`year` to the literal string `"unknown"` rather than guessing or blocking ingestion.

**Acceptance criteria:**
- [ ] A PDF with an unambiguous period statement (e.g. the AMZN or GOOG sample files) gets correct `quarter`/`year` metadata (ADR-008)
- [ ] A PDF with no matching pattern is still ingested, with `quarter`/`year = "unknown"` (ADR-008)
- [ ] Demoable or verifiable in isolation (ingest both a clearly-labeled and an ambiguous sample PDF, inspect metadata)

### 1.4 Ticker folder validation + malformed/unreadable-PDF skip

- **Type:** AFK
- **Blocked by:** 1.1
- **PRD reference:** FR1
- **System design reference:** decision-log rows 12 and 13

**Scope:** At ingestion time, warn/reject folder names under `data/` that aren't a clean uppercase ticker symbol (e.g. flag `data/Google/` or `data/google/`). Separately, detect PDFs whose extracted text is near-empty (e.g. scanned/image-only PDFs) and skip ingesting them, rather than writing near-empty or noise chunks.

**Acceptance criteria:**
- [ ] A non-canonical folder name (e.g. `data/Google/`) produces a warning/rejection rather than being silently ingested as company `"Google"` (row 13)
- [ ] A PDF with no extractable text is skipped, not ingested as an empty/noise chunk (row 12)
- [ ] Demoable or verifiable in isolation (test against a deliberately misnamed folder and a dummy image-only PDF)

### 1.5 Ingest run summary

- **Type:** AFK
- **Blocked by:** 1.2, 1.3, 1.4
- **PRD reference:** FR9
- **System design reference:** `docs/adr/ADR-008-quarter-year-extraction.md` (follow-up), decision-log row 12

**Scope:** Print a summary at the end of each `ingest.py` run: files successfully processed, files that landed in `quarter/year = "unknown"`, and files skipped as unreadable/malformed. No structured/persisted log is required — console output is sufficient (no ingestion-state persistence, per ADR-005).

**Acceptance criteria:**
- [ ] Running `ingest.py` against the full sample corpus prints a summary covering all three categories (processed / unknown-period / skipped) (FR9)
- [ ] The summary correctly reflects the outcomes of tasks 1.2–1.4 for each file
- [ ] Demoable or verifiable in isolation (run against the full sample set, read the printed summary)
