# BDD tests

Behavior-driven tests for the `src/` implementation, using
[`behave`](https://behave.readthedocs.io/) (Gherkin `.feature` files + Python step
definitions). Covers Phases 1–4 in full and Phase 5's non-UI startup guard; see
**Scope** below for why the rest of Phase 5 isn't covered here.

## Running

```bash
cd /Users/srimugunthan/Documents/gitrepos/earnings-rag-system
source .venv/bin/activate
behave test/features
```

First run takes 2–3 minutes — most of that is the HuggingFace embedding model loading and
embedding the real sample corpus a handful of times (once for the shared retrieval/fallback/
conversation fixture, plus once per ingestion scenario, each with its own isolated temp
directory). No `ANTHROPIC_API_KEY` is required to run the suite (see **LLM mocking** below),
and nothing here touches the project's real `data/vector_db`.

## Layout

```
test/
  features/
    environment.py          # behave hooks: sys.path setup, per-scenario state reset
    ingestion.feature
    retrieval_generation.feature
    llm_fallback.feature
    conversation_memory.feature
    chat_ui_startup.feature
    steps/
      common.py              # FakeLLM + shared test-corpus builder (not a step file itself)
      ingestion_steps.py
      retrieval_steps.py
      fallback_steps.py
      conversation_steps.py
      chat_ui_steps.py
```

behave's convention is `features/*.feature` + `features/steps/*.py` + `features/environment.py`
— everything lives under `test/` per that convention, rather than at the repo root.

## Design decisions worth knowing

**LLM mocking.** Every scenario that needs an LLM call uses `FakeLLM` (`steps/common.py`)
instead of a real `ChatAnthropic` call — deterministic, free, and runs without a network
connection or API key. By default `FakeLLM` echoes the human prompt back (prefixed) rather
than returning a fixed canned string, so the *real* retrieved excerpt text (with real figures
from the sample PDFs) still flows through `result.answer` — that's what lets the episodic-fact
scenarios in `conversation_memory.feature` assert on real extracted values without needing
actual LLM comprehension. What these tests verify is **our** code's behavior (retrieval
scoping, citation construction, refusal/degradation triggering, conversation state) — not
Claude's answer quality, which was already spot-verified manually and is documented in
`../test_results/test_phase2.md`.

**Shared test corpus.** `get_shared_test_vector_store()` builds one isolated Chroma store
(copied from the real `data/<TICKER>/` PDFs into a temp dir, cached at module level) and reuses
it across `retrieval_generation.feature`, `llm_fallback.feature`, and `conversation_memory.feature`
— rebuilding it per scenario would dominate the suite's runtime for no benefit, since those
features don't mutate the store. `ingestion.feature` is the exception: each of its scenarios
builds its own fresh temp corpus, since it's testing `ingest.py`'s ingestion behavior itself
(folder validation, per-run isolation, rerun-doesn't-duplicate) and needs full control over
which files are present.

**A fresh `RAGQueryEngine` per scenario.** Even though the vector store path is shared/cached,
each scenario constructs its own `RAGQueryEngine` instance. Its `.llm` attribute gets mutated
by fallback scenarios (swapped for `None` or a failing `FakeLLM`); reusing one shared engine
instance across scenarios would leak that mutated state into unrelated scenarios depending on
run order.

**Small production-code changes made to support testing:**
- `ingest.run_ingestion()` now returns its `RunSummary` (previously it only printed it) — needed
  so scenarios can assert on what was processed/skipped/unknown.
- `app.py`'s Phase 5.4 guard condition was extracted into a standalone `vector_store_ready(path)`
  function, and the rest of the script's top-level Streamlit calls were moved into `main()`
  under `if __name__ == "__main__":`. This makes `app.py` importable (and its guard logic
  testable) without triggering `st.set_page_config`/`st.stop()`/etc., while `streamlit run
  src/app.py` behaves identically to before (confirmed by relaunching it after the change).
  Neither change altered any existing behavior.

## Scope

Phase 5's actual chat UI (rendering, multi-turn browser interaction, degraded-mode display) is
**not** covered here — true BDD browser testing would need Selenium/Playwright, a much heavier
addition than this suite's scope, and the spec's own acceptance criteria for those tasks are
explicitly listed as manual checks. `chat_ui_startup.feature` covers only the part of Phase 5
that's pure logic (`vector_store_ready`), extracted specifically so it *could* be tested this
way. For everything else Phase 5, see `../test_results/test_phase5.md`.
