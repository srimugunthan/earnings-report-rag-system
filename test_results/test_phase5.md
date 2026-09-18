# Testing Phase 5 (Chat UI)

How to verify [`app.py`](../src/app.py) against its spec's acceptance criteria
(`specs/earnings-rag-chat-system/phase5-chat-ui.md`). Every task in this phase is explicitly
listed in the spec itself as a **manual check** ("launch and ask a question", "run with no API
key", "hold a multi-turn conversation in the browser") — a real Streamlit chat only works over
a browser + websocket, so this is the one phase I could not fully verify myself. What follows
is (a) what I already confirmed programmatically, and (b) what you need to click through.

## 1. Setup

```bash
cd /Users/srimugunthan/Documents/gitrepos/earnings-rag-system
source .venv/bin/activate
python src/ingest.py           # if data/vector_db isn't already populated
streamlit run src/app.py
```

This opens the app at `http://localhost:8501`.

## 2. Already verified (no browser needed)

- `app.py`, `conversation.py`, `rag_query.py`, `ingest.py` all compile cleanly (`python -m
  py_compile`).
- `streamlit run src/app.py` boots without an unhandled exception against the real, populated
  `data/vector_db` (checked via a headless launch + `curl` returning `HTTP 200`, and no
  tracebacks in the server log).
- **Task 5.4's guard condition**, run from a directory with no `data/` folder at all:
  `not VECTOR_DB_DIR.exists() or not any(VECTOR_DB_DIR.iterdir())` evaluates to `True`, and a
  headless launch from that directory produced no traceback in the log — meaning the app took
  the `st.error(...) / st.stop()` branch rather than crashing or falling through to
  `load_engine()`. I could not confirm the *rendered text* in a browser, only that the code
  path that shows it was reached cleanly.

## 3. Task 5.1 — basic chat shell (manual)

1. With a real ingested corpus and `ANTHROPIC_API_KEY` set, launch the app and ask:
   `What was AWS revenue growth in Q2 2026?`
2. Check: a grounded answer renders in the chat, with a "Sources" expander listing the
   source PDF filename(s) and page range(s) (FR2, FR4).
3. Check: no network tab / REST call is involved — the app calls `RAGQueryEngine`/`converse`
   directly in-process (ADR-001). (Nothing to click for this one — it's true by construction,
   since `app.py` imports and calls the Python functions directly.)

## 4. Task 5.2 — degraded-mode rendering (manual)

1. Temporarily comment out or remove the `ANTHROPIC_API_KEY` line from `.env`, restart the
   app (`Ctrl+C` then `streamlit run src/app.py` again — env vars are only read at process
   start).
2. Ask any question with a real answer in the corpus.
3. Check: instead of a normal answer, you see a visibly distinct `st.warning` box reading
   *"LLM unavailable — showing matching excerpts only."*, followed by the raw retrieved
   excerpts with their citations — not rendered as if they were a generated answer (ADR-007).
4. Restore the real key, restart, and confirm a normal question now renders the plain
   markdown answer + Sources expander again — visibly different from the warning box.

## 5. Task 5.3 — multi-turn wiring (manual)

1. In one browser session, ask: `What was Amazon's AWS revenue growth in Q2 2026?`
2. Follow up with: `How about Microsoft's cloud revenue?`
3. Check: the second answer is genuinely about Microsoft, not Amazon — this is the same
   company-detection behavior already verified by Phase 4's scripted test
   (`test_phase4.md`), now wired through real Streamlit `session_state`
   (`st.session_state.memory`, a `ConversationMemory` instance created once per browser
   session).
4. Continue for 8+ turns across companies, then ask a question referring back to the first
   fact discussed. Check it's still answered correctly (compaction + episodic memory carrying
   forward, per Phase 4).

## 6. Task 5.4 — missing-store error (manual, to see the actual rendered text)

```bash
cd /tmp   # or any directory with no data/ subfolder
streamlit run /Users/srimugunthan/Documents/gitrepos/earnings-rag-system/src/app.py
```

Check: the page shows a red `st.error` box saying no ingested data was found and to run
`python src/ingest.py`, with no chat input box below it (i.e. `st.stop()` actually halted
rendering) — not a crash/traceback page, and not a chat box that just returns empty results.

## Notes on what's out of scope for this doc

- Citations can repeat when multiple retrieved chunks share the same source/page (a Phase 2
  behavior, unchanged here) — cosmetic, not a functional bug worth fixing without being asked.
- `st.cache_resource` on `load_engine()` means the embedding model and Chroma connection are
  built once per server process, not once per browser tab — this is intentional (rebuilding
  `HuggingFaceEmbeddings` on every rerun would make every single keystroke-triggered rerun
  slow).

If steps 3–6 all check out in the browser, Phase 5 — and the full v1 system — matches spec.
