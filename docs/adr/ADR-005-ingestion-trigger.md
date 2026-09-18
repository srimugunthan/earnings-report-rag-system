# ADR-005: Ingestion is a separate, manually-triggered command, not startup-triggered

**Status:** Accepted
**Date:** 2026-09-17
**Deciders:** Project owner

---

## Context

FR8 requires that re-running the app doesn't require re-ingesting unchanged PDFs across sessions — satisfied by persisting the Chroma vector store itself (ADR-003), independent of *when* ingestion happens. FR9 requires that dropping a new PDF into `data/` and re-running ingestion makes it queryable without code changes.

Earlier in this design process, auto-ingest-on-chat-app-startup with a hash/mtime manifest (to skip unchanged files) was proposed as a way to satisfy both FR8 and FR9 without requiring a manual step. On review, this coupled a data-management concern (ingestion) to the chat UI's lifecycle for a workload that doesn't actually change on that cadence: earnings reports are released quarterly, not continuously, so scanning `data/` on every chat session launch adds overhead and a manifest artifact to maintain for a corpus that, in practice, only changes a few times a year.

---

## Decision

Ingestion will be implemented as a separate, explicitly-invoked command (e.g. `python ingest.py`), run manually by the user whenever they choose — typically aligned with each quarter's earnings releases — and never automatically triggered by the Streamlit chat app at startup or during a session. Each explicit ingest run fully re-processes all PDFs found under `data/<TICKER>/` (load → chunk → embed → store) rather than tracking a hash/mtime manifest to skip unchanged files. The chat app only reads from the already-persisted Chroma store; it never performs ingestion itself.

---

## Alternatives Considered

| Option | Pros | Cons |
|--------|------|------|
| Auto-ingest on chat-app startup + hash/mtime manifest (originally proposed) | Zero manual step — FR9's "new PDF becomes queryable" happens automatically; manifest keeps repeated startups cheap by skipping unchanged files | Adds a filesystem scan and manifest-diff to every chat session startup for a workload that only actually changes a few times a year; introduces a manifest file as an extra artifact that can drift out of sync; couples ingestion to the UI's lifecycle |
| **Explicit separate command, full re-process each run (chosen)** | Decouples ingestion from the chat app's lifecycle — matches the natural cadence of earnings releases; no manifest file to maintain or drift; simple mental model ("run ingest when you have new reports") | Requires the user to remember to run ingestion after adding new PDFs — FR9 is satisfied only if they do; re-embeds unchanged PDFs on every run, wasting some compute (accepted as negligible at this corpus size) |
| Explicit separate command + hash/mtime manifest (hybrid) | Keeps ingestion decoupled from the chat app while still skipping unchanged files for efficiency | The manifest's main value — avoiding repeated work on frequent/automatic triggers — mostly evaporates once ingestion is already infrequent and manual; adds a moving part for a now-marginal benefit at this corpus size |

---

## Consequences

**Positive:**
- Chat app startup stays fast and simple — it just loads an already-persisted Chroma store.
- Ingestion behavior is predictable and fully under the user's control, run only when they choose.
- No manifest file to keep in sync or debug.

**Negative / Accepted Tradeoffs:**
- FR9 ("dropping a new PDF makes it queryable without code changes") now depends on the user remembering to run `ingest.py` — it's a manual step, not automatic.
- Every ingest run re-embeds the entire corpus even if only one file changed. Fine at today's scale (a handful of PDFs); would need revisiting (e.g. reintroducing a manifest) if the corpus grows substantially.

---

## Follow-up Actions

- [ ] Implement `ingest.py` as a standalone entrypoint that scans `data/<TICKER>/*.pdf` and runs load → chunk → embed → store, independent of the Streamlit app.
- [ ] Document in the README/quick-start that ingestion must be run manually after adding new PDFs, since FR9 depends on the user doing so.
- [ ] Revisit full-reprocess-every-run (e.g. reintroduce a manifest) if the corpus grows large enough that re-embedding cost becomes noticeable.
