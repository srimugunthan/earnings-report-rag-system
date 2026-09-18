# ADR-007: Unified retrieval-only fallback when the LLM is unavailable

**Status:** Accepted
**Date:** 2026-09-17
**Deciders:** Project owner

---

## Context

The chat app must remain usable when the LLM is unavailable, which can happen for two distinct reasons: no API key is configured at startup, or an LLM call fails at runtime after the key is present (transient network error, rate limiting, provider outage, quota exhaustion). Retrieval (embedding + Chroma similarity search, ADR-003) is architecturally independent of the LLM call, so it can succeed even when the LLM cannot. FR3 already requires that the system say so explicitly rather than guess when no grounding is found; the same honesty principle extends naturally to LLM unavailability — the user should get a useful, clearly-labeled degraded response rather than either a hard failure or a silent/broken one.

---

## Decision

We will implement one unified fallback mechanism covering both triggers: whenever the LLM is unavailable — no API key configured at startup, or a runtime call failure (exception, timeout, rate-limit, non-success response) — the app falls back to a retrieval-only response for that query, showing the raw matching excerpts and their citations without an LLM-generated answer, plus a clear on-screen notice explaining why (e.g. "LLM unavailable — showing matching excerpts only"). The app never refuses to start over a missing key, and never surfaces an unhandled exception to the user over a failed LLM call. This is distinct from, and does not change, FR3's existing "say so" behavior for retrieval finding no relevant grounding.

---

## Alternatives Considered

| Option | Pros | Cons |
|--------|------|------|
| Fail hard (refuse to start without a key; propagate/crash on runtime LLM errors) | Simple; failure is obvious and unambiguous | App becomes unusable during setup or during a transient provider issue, even though retrieval still works fine |
| **Unified retrieval-only fallback for both triggers (chosen)** | App stays usable across both missing-key and runtime-failure cases with one consistent mechanism; retrieval path is already independent of the LLM call, so this is nearly free to implement; the degraded response is still useful (raw excerpts + citations) | Two response shapes to render in the UI (full answer vs degraded excerpts-only); risk of a user mistaking excerpts-only output for a synthesized answer if the on-screen notice isn't prominent |
| Separate, inconsistent handling per trigger (e.g. refuse to start on missing key, but silently retry/backoff on runtime failure) | Could feel "tailored" per failure type | Two different code paths and behaviors for what is, from the user's perspective, the same underlying problem (LLM unavailable) — more code, more inconsistency, no real benefit |

---

## Consequences

**Positive:**
- The app remains usable in more situations: mid-setup (no key yet), and during transient provider issues.
- Reuses the already-decided retrieval-only mode (Q9) as the single fallback path for both triggers, minimizing new code.
- Consistent, predictable behavior regardless of why the LLM happens to be unavailable.

**Negative / Accepted Tradeoffs:**
- The chat UI must render two distinct response types (full LLM answer vs degraded excerpts+notice), adding UI branching.
- The on-screen notice is the only safeguard against a user missing that a response is degraded — this is a UX mitigation, not full observability/logging, which is out of scope for v1 per the PRD.

---

## Follow-up Actions

- [ ] Wrap the LLM call in the RAG pipeline with error handling (timeout, exception, non-success response) that falls back to returning retrieved chunks + citations without a generated answer.
- [ ] Chat UI renders a clear, visible notice whenever a response is degraded (excerpts-only) rather than a full LLM-generated answer.
- [ ] Confirm this fallback is scoped to LLM unavailability only and does not change FR3's existing "say so" behavior when retrieval itself finds nothing relevant.
