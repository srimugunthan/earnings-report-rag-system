# Testing Phase 4 (Conversation Memory)

How to verify [`conversation.py`](../src/conversation.py) against its spec's acceptance
criteria (`specs/earnings-rag-chat-system/phase4-conversation-memory.md`). All three tasks
are demoable with one scripted, no-UI conversation.

## 1. Activate the environment, make sure the store exists and a real API key is set

```bash
cd /Users/srimugunthan/Documents/gitrepos/earnings-rag-system
source .venv/bin/activate
python src/ingest.py   # if data/vector_db isn't already populated
```

`conversation.py` needs a real `ANTHROPIC_API_KEY` in `.env` — compaction (4.2) and
generation both call Claude.

## 2. Run the scripted 10-turn conversation

```bash
python src/conversation.py
```

This asks a 10-question script that deliberately exercises all three tasks: an early
Amazon question, several elliptical company follow-ups ("How about Microsoft's cloud
revenue?", "And Google's?"), enough turns to overflow the 6-message window multiple times,
and a final question that refers back to the very first fact discussed.

Check the per-turn output:

- **Task 4.1**: turns 2 ("How about Microsoft's cloud revenue?"), 3 ("And Google's?"), 6, 7,
  and 9 should each return an answer grounded in *that* company's own filing — not Amazon's
  (the company named in turn 1). This confirms company detection runs per-turn on the current
  question, not on the whole conversation blob.
- **Task 4.2**: by turn 10, turn 1's raw exchange has long aged out of the 6-message window
  (each exchange adds 2 messages, so it ages out by exchange 4). Turn 10 should still answer
  the AWS-growth follow-up correctly — that's the compaction summary carrying the fact
  forward, not the raw window.
- **Task 4.3**: turn 10 explicitly asks about "the very first thing we discussed," and should
  correctly answer "37%" even though nothing in the current 6-message window mentions AWS.

## 3. Inspect the final memory state

The script prints this at the end:

```
=== Final conversation memory state ===
Window size: 6 raw turns
Summary: ...
Episodic facts:
  - EpisodicFact(turn=1, company='AMZN', metric='aws', quarter='Q2 2026', value='37%')
  - EpisodicFact(turn=2, company='MSFT', metric='azure', ...)
  ...
```

Check:
- `Window size` never exceeds 6, regardless of how many turns ran (task 4.1's cap).
- `Summary` is non-empty and mentions all three companies discussed, not just the most
  recent one (task 4.2).
- `Episodic facts` has one entry per grounded turn, each with the **correct** company —
  in particular, turn 10's fact should say `company='AMZN'`, not `'MSFT'` (the most
  recently-discussed company at that point) — this is the regression this design
  specifically guards against.

## 4. Confirm no cross-session persistence (task 4.3's second criterion)

```bash
PYTHONPATH=src python -c "
from conversation import ConversationMemory
m = ConversationMemory()
print(m.window, m.summary, m.episodic_facts)
"
```

Expected: `[] '' []` — a fresh `ConversationMemory` always starts empty; nothing is loaded
from disk (ADR-006 explicitly scopes this to in-session only).

## Design note worth knowing before you re-test

An earlier version of this code made company detection "sticky" — if a follow-up question
didn't name a company, it fell back to whichever company was named most recently. That
seemed reasonable but actually broke turn 10 in the script above: since turn 10 doesn't name
a company, it fell back to Microsoft (the last one named, in turn 9) instead of Amazon, and
mis-scoped the retrieval. It was removed — a question that doesn't name a company now
searches unscoped across all companies, relying on the embedded conversation context
(summary + window) to disambiguate. If you see a future task-4 follow-up misfire that seems
to want "sticky" company memory, that's the tradeoff to reconsider, not a bug.

If steps 2–4 all check out, Phase 4 matches its spec.
