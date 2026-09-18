# ADR-004: Merge PDF pages before chunking, allowing chunks to span page boundaries

**Status:** Accepted
**Date:** 2026-09-17
**Deciders:** Project owner

---

## Context

FR4 requires each answer to name the specific source document and page it was drawn from. The existing ingestion path loads each PDF with `PyPDFLoader`, which produces one `Document` per page, and then chunks with `EarningsChunker` (`RecursiveCharacterTextSplitter`) via `split_documents()`.

Testing confirmed a structural property of LangChain's `split_documents()`: it splits each input `Document` independently and copies that `Document`'s own metadata onto every resulting chunk — it never merges content across separate input `Document`s. Because `PyPDFLoader` already hands the chunker one `Document` per page, this means chunks never span page boundaries today, and each chunk already carries an exact, single page number for free. This is a true zero-effort default, not a configuration choice.

Earnings reports commonly contain sections and financial tables that continue across a page break (e.g. a segment revenue breakdown). Strict within-page chunking splits these at the page boundary, which can produce a less representative chunk/embedding for content near that break. The alternative — merging a document's pages into one text stream before chunking so a chunk can span pages — was evaluated against this zero-effort default, with the understanding (confirmed only after an earlier mis-statement in the design discussion was corrected) that it requires real new implementation, not a flag flip, and that page citations must shift from a single exact page number to a page range.

---

## Decision

We will concatenate each PDF's pages into a single text blob per document before chunking, allowing chunks to span page boundaries. Each chunk's page citation will be computed as a range (e.g. "pp. 11-12") by tracking the character-offset boundaries between pages through the concatenation and mapping each chunk's start/end offset back to the page(s) it falls within.

---

## Alternatives Considered

| Option | Pros | Cons |
|--------|------|------|
| Strict within-page chunking (structural default — chunk each page's `Document` independently, as `split_documents()` already does today) | Exact, single-page citation for every chunk, for free; zero implementation effort | Can split a sentence, paragraph, or multi-page table right at the page break, producing a less representative chunk near boundaries |
| **Merge pages before chunking, cross-page chunks allowed (chosen)** | Better semantic continuity — a section or table spanning a page break stays in one chunk, giving a more representative embedding and a more complete context for retrieval | Requires new implementation (concatenation + character-offset-to-page mapping); citations become page ranges instead of exact single pages — a softer form of FR4 compliance; every downstream consumer of page metadata (prompt template, chat UI) must be updated to render a range |

---

## Consequences

**Positive:**
- Multi-page sections/tables common in earnings releases stay in a single chunk, improving retrieval quality and context completeness near page boundaries.

**Negative / Accepted Tradeoffs:**
- New implementation work is required in `text_chunker.py`/ingestion to concatenate per-document pages and track offset-to-page-range mapping — this was not previously present and is not a LangChain configuration option.
- Page citations become ranges (e.g. "pp. 11-12") rather than an exact single page, a deliberately accepted softening of FR4's page-citation precision in exchange for chunk quality.
- The prompt template's context formatting and the chat UI's citation rendering both need to handle a page-range value instead of a single page number.

---

## Follow-up Actions

- [ ] Implement per-document page concatenation and character-offset-to-page-range tracking in the chunking step (replacing reliance on `PyPDFLoader`'s automatic per-page `Document` split for page metadata).
- [ ] Update the RAG prompt template's context formatting to carry/display page ranges.
- [ ] Update the Streamlit chat UI's citation rendering to display page ranges (e.g. "AAPL Q3 2024, pp. 11-12").
