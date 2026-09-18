# ADR-002: Organize earnings PDFs into per-company subfolders under data/

**Status:** Accepted
**Date:** 2026-09-17
**Deciders:** Project owner

---

## Context

The Earnings Report RAG Chat System (PRD.md) ingests a local folder of quarterly earnings-report PDFs and must support company-scoped queries (FR6) as well as anticipated future queries that compare periods within a single company (e.g., "how is Apple's earnings different from last year"). Correct `company` metadata is required for citation accuracy (FR4) and for filtering (FR6); getting it wrong on a cross-period comparison query would silently produce an incorrect answer rather than an explicit "not found."

The PDFs currently live in a single flat folder, `data/sample_earnings/`, with inconsistent filenames that don't reliably encode company via parsing: `AMZN-Q2-2026-Earnings-Release.pdf`, `FY26 Q2 - Press Releases - Investor Relations - Microsoft.pdf`, `GOOG-10-Q-Q2-2026.pdf`, and an unlabeled slides deck. A filename- or content-parsing approach to deriving company metadata carries real misattribution risk given this inconsistency.

---

## Decision

We will reorganize ingested earnings PDFs into per-company subfolders under `data/`, i.e. `data/<TICKER>/*.pdf` (e.g. `data/AAPL/*.pdf`, `data/MSFT/*.pdf`), and derive the `company` metadata field deterministically from the immediate parent folder name at ingestion time, instead of parsing it from the filename or PDF content.

This decision resolves **company** attribution only. Quarter/year metadata derivation — needed for period-scoped and year-over-year queries — is a separate, still-open decision (PRD §9 item 4), and its correctness now matters more given the anticipated year-over-year query pattern.

---

## Alternatives Considered

| Option | Pros | Cons |
|--------|------|------|
| Flat/recursive scan of `data/` as-is | Zero migration cost; fully flexible drop-in, no folder convention to follow | Company metadata must be parsed from inconsistent filenames or PDF content — real risk of misattribution given current naming |
| **`data/<TICKER>/*.pdf` subfolders (chosen)** | Company metadata is free and 100% reliable (folder name); self-documenting (`ls data/` shows exactly what's covered); structurally prevents cross-company misattribution | Requires a one-time migration of existing files and an enforced naming convention for every future drop-in; the folder name itself still needs a canonicalization rule (e.g. "Google" vs "GOOGL") |
| Flat `data/` + manifest file mapping filename → `{company, quarter}` | Same reliability as the folder approach without forcing a folder convention; keeps drop-anywhere flexibility | Introduces an additional artifact that must be kept in sync manually; less self-documenting than browsing folders directly |

---

## Consequences

**Positive:**
- Company attribution becomes structurally guaranteed rather than probabilistic, eliminating a class of silent misattribution bugs in citations (FR4) and company-scoped filtering (FR6).
- `ls data/` gives an accurate, at-a-glance inventory of which companies are covered.
- The existing sample corpus is small (4 files), so the one-time migration cost is negligible.

**Negative / Accepted Tradeoffs:**
- Every future PDF must be placed in the correct ticker subfolder — an enforced convention rather than "drop it anywhere in `data/`."
- Folder naming needs a canonicalization rule (always the ticker symbol, not a display name) to avoid the same ambiguity resurfacing one level up.
- This decision does not solve quarter/year metadata reliability — that remains dependent on whatever PRD §9 item 4 settles on, and that decision now carries more weight given year-over-year query support.

---

## Follow-up Actions

- [ ] Physically move the 4 existing sample PDFs into `data/<TICKER>/` subfolders during the ingestion implementation milestone (not performed as part of this design decision).
- [ ] Settle quarter/year metadata derivation (PRD §9 item 4), weighting reliability given year-over-year query support.
- [ ] Document a canonicalization rule for folder names (ticker symbol, uppercase) so company attribution stays unambiguous as more companies are added.
