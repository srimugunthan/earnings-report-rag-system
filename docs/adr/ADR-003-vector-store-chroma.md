# ADR-003: Use Chroma as the vector store backend

**Status:** Accepted
**Date:** 2026-09-17
**Deciders:** Project owner

---

## Context

The Earnings Report RAG Chat System (PRD.md) must support company-scoped retrieval filtering (FR7) over a small, purely local corpus of earnings-report PDF chunks. The system runs entirely locally (§6 Non-Functional Requirements) and explicitly excludes hosted/cloud deployment (§3 Non-Goals). The existing prototype's `VectorStoreManager` (`prototype/core/vector_store.py`) already supports both FAISS and Chroma interchangeably behind one interface, with FAISS as today's default.

FAISS's LangChain wrapper lacks robust native metadata-filter pushdown, which FR7's company-scoped filtering needs. Cloud-managed options (Pinecone) were also evaluated but are disqualified outright: Pinecone has no local/self-hosted mode, so choosing it would mean walking back the PRD's own "runs entirely locally" requirement, not just trading off a preference. Qdrant was evaluated as a self-hostable alternative with best-in-class filtered search and production-grade distributed scaling, but it requires running a persistent server process (even locally), which neither FAISS nor Chroma need, and its distributed-scale strengths aren't needed at this project's current scale (a handful of PDFs, single local user, explicitly no multi-tenant/production deployment per §3 Non-Goals).

---

## Decision

We will use Chroma, in local persistent-client mode (no server process), as the vector store backend for this system, retiring FAISS as the default. The existing `VectorStoreManager` abstraction keeps FAISS available as an alternate backend if ever needed later.

---

## Alternatives Considered

| Option | Pros | Cons |
|--------|------|------|
| FAISS (prior default) | Extremely fast, in-process, zero operational overhead, already the default in the existing code | LangChain's FAISS wrapper has no real native metadata-filter pushdown — the exact capability FR7 needs |
| **Chroma (chosen)** | Native, first-class metadata filtering (directly satisfies FR7); comparable query speed to FAISS at this scale; no server process; free; already a supported backend in the existing code | Local persistence layer (SQLite/DuckDB+Parquet-backed) has marginally more overhead than FAISS's raw in-memory index — negligible at this project's scale; lower scaling ceiling than Qdrant/Pinecone for distributed/production use |
| Qdrant | Best-in-class native filtered search; built for production-scale distributed serving | Requires running a persistent server process (Docker/binary) even for local use — an extra always-on component neither FAISS nor Chroma need; its distributed-scale strengths are unneeded at this project's current scale |
| Pinecone | Native metadata filtering; fully managed, scales to production automatically | Cloud-only by design, no self-hosted/local mode — directly conflicts with §6 ("runs entirely locally") and §3 Non-Goals ("no hosted deployment"); adds network round-trip latency per query, which at this small corpus size is slower in absolute terms than local in-memory search; introduces ongoing usage-based cost |

---

## Consequences

**Positive:**
- FR7's company-scoped filtering is satisfied natively, with no workaround/post-filter code needed.
- No new server process or infrastructure to operate — stays consistent with the "runs entirely locally" requirement.
- Reuses an already-supported backend in the existing codebase, minimizing new implementation work.
- No hosting cost.

**Negative / Accepted Tradeoffs:**
- Marginally more storage/query overhead than FAISS's raw in-memory index, accepted as negligible at this project's scale.
- Lower ceiling for distributed/production-scale deployment than Qdrant or Pinecone — accepted because production/multi-tenant scale is explicitly out of scope (§3 Non-Goals).

---

## Follow-up Actions

- [ ] If this project ever needs production or multi-tenant scale (explicitly out of scope today), revisit with Qdrant (self-hosted) or a managed service as the upgrade path.
- [ ] Ensure chunk-level metadata (company from ADR-002's folder convention, quarter/year once PRD §9 item 4 is settled) is passed into Chroma's metadata fields at ingestion time so FR7 filtering works end-to-end.
