# Phase 2: Core Retrieval + Grounded Generation

**Depends on:** `phase1-ingestion-pipeline.md`
**Status:** Not started

## Design components touched

RAG Query Engine (`system-design.md` §2), Interfaces (§4: Query Engine → Vector Store, Query Engine → LLM), Query data flow core (§5).

## Objective

A single-turn query function that, given a question (and optionally a company name), retrieves relevant chunks from the Phase 1 Chroma store — filtered by company when one is named — assembles them into a prompt with citations, calls the LLM (Anthropic Claude Haiku), and returns a grounded answer with source + page-range citations. When nothing relevant is found, it returns an explicit "not found" response instead of guessing.

## Independently testable when

Calling the query function directly (a script or REPL, no UI) with example questions from the PRD (e.g. "What was Apple's total revenue in Q3 2024?", "How much did Microsoft's Azure grow?") against the Phase 1 ingested corpus returns answers that match the source PDFs, with correct company/page citations, and a question about a company never ingested returns an explicit refusal rather than a fabricated answer.

## Tasks

### 2.1 Company-scoped retrieval

- **Type:** AFK
- **Blocked by:** Phase 1 (task 1.5)
- **PRD reference:** FR6
- **System design reference:** §2 RAG Query Engine, §4 Interfaces

**Scope:** Embed the input question and run a Chroma similarity search against the Phase 1 store, returning the top-k chunks. When a company is identified in the question (or passed explicitly), apply Chroma's native metadata filter so results are scoped to that company only.

**Acceptance criteria:**
- [ ] A company-scoped query (e.g. "AAPL revenue") only returns chunks with `company == "AAPL"` (FR6)
- [ ] An unscoped query returns relevant chunks across companies
- [ ] Demoable or verifiable in isolation (call the retrieval function directly with and without a company filter)

### 2.2 Grounded answer generation with page-range citations

- **Type:** AFK
- **Blocked by:** 2.1
- **PRD reference:** FR4, FR5
- **System design reference:** §5 Query flow

**Scope:** Assemble retrieved chunks (with their company/page-range metadata) into a prompt, call Claude Haiku, and return the generated answer alongside a citations list (source document + page range per cited chunk). Covers both summarization-style and point-lookup questions (FR5) — no special-casing required, since both go through the same retrieval + generation path.

**Acceptance criteria:**
- [ ] A point-lookup question (e.g. "What was Apple's Q3 2024 revenue?") returns an answer matching the source PDF's figure, with a citation naming the document and page range (FR4)
- [ ] A summarization question (e.g. "Summarize Apple's earnings report") returns a coherent multi-point summary grounded in retrieved chunks (FR5)
- [ ] Demoable or verifiable in isolation (call the query function directly with both question types)

### 2.3 Explicit "not found" refusal

- **Type:** AFK
- **Blocked by:** 2.2
- **PRD reference:** FR3
- **System design reference:** §5 Query flow

**Scope:** When retrieval returns no sufficiently relevant chunks (e.g. below a similarity-score threshold, or asking about a company/topic not present in the corpus), return an explicit "not found in the ingested reports" response instead of passing weak/irrelevant context to the LLM and risking a fabricated answer.

**Acceptance criteria:**
- [ ] A question about a company never ingested returns an explicit refusal, not a fabricated or hallucinated answer (FR3)
- [ ] A question with genuinely relevant retrieved content does not trigger the refusal path
- [ ] Demoable or verifiable in isolation (query for an out-of-corpus company)
