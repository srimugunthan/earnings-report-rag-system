# Testing Phase 3 (LLM-Unavailability Fallback)

How to verify [`rag_query.py`](../src/rag_query.py)'s fallback behavior against its spec's
acceptance criteria (`specs/earnings-rag-chat-system/phase3-llm-fallback.md`). Both cases
are verifiable without the Chat UI.

## 1. Activate the environment and make sure the store exists

```bash
cd /Users/srimugunthan/Documents/gitrepos/earnings-rag-system
source .venv/bin/activate
python src/ingest.py   # if data/vector_db isn't already populated
```

The modules live in `src/` — the snippets below use `PYTHONPATH=src` so plain `import
rag_query` resolves.

## 2. Task 3.1 — missing API key returns a degraded response, not an exception

`load_dotenv()` runs at import time, so to simulate a genuinely missing key you need to stop
it from repopulating `ANTHROPIC_API_KEY` from `.env` before `rag_query` is imported:

```bash
PYTHONPATH=src python -c "
import os
os.environ.pop('ANTHROPIC_API_KEY', None)
import dotenv
dotenv.load_dotenv = lambda *a, **k: None  # block rag_query's module-level load_dotenv()

from rag_query import RAGQueryEngine
engine = RAGQueryEngine()
print('llm is None:', engine.llm is None)

r = engine.query('What was AWS revenue growth in Q2 2026?')
print('degraded:', r.degraded, '| not_found:', r.not_found)
print('answer:', r.answer)
print('citations:', len(r.citations), '| excerpts:', len(r.excerpts))
"
```

Expected: `engine.llm is None` is `True`, the call does not raise, `degraded` is `True`,
`answer` is the fixed notice ("LLM unavailable — showing matching excerpts only."), and both
`citations` and `excerpts` are populated with the real retrieved chunks — this confirms the
app never refuses to run over a missing key (ADR-007).

## 3. Task 3.2 — a runtime LLM failure degrades gracefully, then recovers

`ChatAnthropic` is a pydantic model so you can't monkeypatch `.invoke` on the instance
directly — swap `engine.llm` for a stub object instead, then swap the real one back:

```bash
PYTHONPATH=src python -c "
from rag_query import RAGQueryEngine
engine = RAGQueryEngine()
real_llm = engine.llm

class BrokenLLM:
    def invoke(self, *a, **k):
        raise RuntimeError('simulated provider outage')

engine.llm = BrokenLLM()
r1 = engine.query('What was AWS revenue growth in Q2 2026?')
print('call 1 -> degraded:', r1.degraded, '| answer:', r1.answer, '| excerpts:', len(r1.excerpts))

engine.llm = real_llm
r2 = engine.query('What was AWS revenue growth in Q2 2026?')
print('call 2 -> degraded:', r2.degraded, '| answer:', r2.answer[:100])
"
```

Expected: call 1 returns the same degraded shape as task 3.1 (no unhandled exception), and
call 2 — once the LLM works again — returns a normal, non-degraded answer. This confirms the
fallback is scoped to the failing call only, not a persistent state change (ADR-007).

## 4. Sanity check: normal path is unaffected

```bash
python src/rag_query.py
```

With a real key in `.env`, none of the printed answers should show `[degraded]`, and the
out-of-corpus Apple question should still hit the *not-found* path (FR3) rather than the
*degraded* path — these are deliberately distinct: not-found means retrieval found nothing
relevant, degraded means the LLM itself was unavailable.

If steps 2–4 all check out, Phase 3 matches its spec.
