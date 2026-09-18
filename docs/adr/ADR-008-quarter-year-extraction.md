# ADR-008: Derive quarter/year metadata via regex extraction, defaulting to "unknown" on failure

**Status:** Accepted
**Date:** 2026-09-17
**Deciders:** Project owner

---

## Context

With company metadata now derived deterministically from folder structure (ADR-002), quarter/year metadata still needs a source. Filenames are inconsistent and were already rejected as unreliable for the same reasons company-via-filename was rejected (see ADR-002), compounded here by a fiscal-year-vs-calendar-year landmine (e.g. a filename like "FY26 Q2" needs correct fiscal→calendar mapping to compare correctly against a competitor labeled by calendar quarter). Extracting the period from each PDF's own content was chosen instead. The existing sample corpus spans real format variety — a formal earnings release, a 10-Q, a press release, and a slides deck — meaning extraction reliability is not uniform across document types; a slides deck in particular may only carry a compact watermark like "FY26 Q2" rather than an explicit sentence stating the reporting period.

Two follow-on choices were required to make this decision concrete: which extraction mechanism to use, and what happens when extraction doesn't confidently match. Getting the wrong period silently matters more than usual here because it directly risks an incorrect year-over-year comparison (an anticipated query pattern) rather than just a missing citation.

---

## Decision

Quarter/year metadata will be extracted from each PDF's page-1 (with early-page fallback) text using regex/keyword search for common reporting-period patterns (e.g. "Quarter Ended", "QX FY/CY YYYY", "Third Quarter YYYY") — not an LLM call, and not a manifest file.

When no pattern confidently matches, the file is still ingested and made queryable by content, but its `quarter`/`year` metadata fields are set to the literal value `unknown`. Chunks with `unknown` period are excluded from period-scoped filtering and year-over-year comparison queries, while remaining retrievable for general and company-scoped questions.

---

## Alternatives Considered

**Extraction mechanism:**

| Option | Pros | Cons |
|--------|------|------|
| **Regex/keyword search (chosen)** | No new dependency; fast, free, deterministic; easy to inspect and extend with more patterns | Brittle across the real format variance in the sample corpus — likely to miss the period on less-structured documents such as a slides deck |
| LLM extraction call | More robust to varied phrasing/formatting; Haiku is already wired in for answer generation | Adds an LLM call (cost, latency, a new failure mode) to ingestion, which previously had no LLM dependency at all |
| Manifest/sidecar file | Fully deterministic regardless of document format | Manual maintenance burden; superseded once content extraction was chosen over this approach for item 4 |

**Failure handling:**

| Option | Pros | Cons |
|--------|------|------|
| Skip and report unparseable files | Never silently produces a wrong period; user is explicitly prompted to resolve it | File is unusable (even for non-period questions like summarization) until manually fixed; ingestion effectively gates on every file parsing cleanly |
| **Ingest anyway with `quarter/year = unknown` (chosen)** | File stays immediately queryable for general/company-scoped and summarization questions; a single problematic file never blocks ingestion of the rest of the corpus | Every period-scoped or year-over-year code path must correctly exclude `unknown`-period chunks, or risk silently reintroducing the wrong-comparison problem this whole line of decisions (ADR-002 and this ADR) exists to prevent |

---

## Consequences

**Positive:**
- Ingestion stays simple and dependency-free (no LLM call added to the ingestion path) and never blocks entirely on one problematic file.
- Documents with unparseable periods (e.g. a slides deck) remain useful for non-period-scoped queries such as summarization, instead of being locked out of the system entirely.

**Negative / Accepted Tradeoffs:**
- Regex/keyword matching will predictably miss period info on less-structured documents, given the confirmed format variety in the sample corpus — some files will land in `unknown` and lose year-over-year/period-filtering capability.
- Correctness of period-scoped and year-over-year queries now depends on every retrieval/filtering code path explicitly excluding `unknown`-period chunks. A missed exclusion silently reintroduces exactly the wrong-comparison risk that motivated moving company metadata to a reliable folder-based source in ADR-002.

---

## Follow-up Actions

- [ ] Implement regex/keyword extraction of quarter/year from page-1 (and early-page fallback) text, covering patterns observed in the sample corpus (e.g. "QX 20YY", "FYYY QX", "Quarter Ended <date>").
- [ ] Set `quarter`/`year` metadata to the literal value `unknown` when no pattern confidently matches.
- [ ] Ensure period-scoped filtering and year-over-year comparison logic explicitly excludes `unknown`-period chunks, and cover this with a test (a miss here silently reintroduces wrong-comparison risk).
- [ ] Surface which files landed in `unknown` in the `ingest.py` run summary, so the user is aware even though ingestion doesn't block on it.
