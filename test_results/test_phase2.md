# Testing Phase 2 (Core Retrieval + Grounded Generation)

How to verify [`rag_query.py`](../src/rag_query.py) against its spec's acceptance criteria
(`specs/earnings-rag-chat-system/phase2-retrieval-generation.md`).

Split into what you can test now (no API key needed) vs. what needs a real
`ANTHROPIC_API_KEY`.

## 1. Activate the environment and make sure Phase 1's store exists

```bash
cd /Users/srimugunthan/Documents/gitrepos/earnings-rag-system
source .venv/bin/activate
python src/ingest.py   # if data/vector_db isn't already populated
```

## 2. Retrieval + company detection — works without an API key (task 2.1, half of 2.3)

`RAGQueryEngine.__init__` builds a `ChatAnthropic` client, which errors without a key, so for
retrieval-only testing construct the engine without going through `__init__`. The modules live
in `src/`, so either run from there or set `PYTHONPATH=src` (used below):

```bash
PYTHONPATH=src python -c "
from rag_query import RAGQueryEngine
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma

engine = RAGQueryEngine.__new__(RAGQueryEngine)
engine.top_k = 4
engine.max_distance = 1.3
engine.embeddings = HuggingFaceEmbeddings(model_name='sentence-transformers/all-MiniLM-L6-v2', model_kwargs={'device':'cpu'}, encode_kwargs={'normalize_embeddings': True})
engine.vector_store = Chroma(collection_name='earnings_reports', embedding_function=engine.embeddings, persist_directory='data/vector_db')

print('known companies:', engine.known_companies())

# 2.1: company-scoped filter only returns that company's chunks
res = engine.retrieve('revenue growth', company='AMZN')
print('AMZN-scoped companies seen:', {d.metadata['company'] for d, s in res})

# 2.1: unscoped returns chunks across companies
res = engine.retrieve('cloud revenue growth')
print('unscoped companies seen:', {d.metadata['company'] for d, s in res})

# 2.3: a never-ingested company is detected and known to be absent
print('detect_company(...) ->', engine.detect_company('What was Apple iPhone revenue in Q3 2024?'))
print('AAPL known?', 'AAPL' in engine.known_companies())
print('AAPL filter yields:', len(engine.retrieve('Apple revenue', company='AAPL')), 'results')
"
```

Expected: `known companies: {'AMZN', 'GOOG', 'MSFT'}`, the AMZN-scoped query returns only
`{'AMZN'}`, the unscoped query returns multiple companies, `detect_company` returns `AAPL`,
`AAPL known?` is `False`, and the AAPL-filtered retrieval returns 0 results.

## 3. Add a real API key, then test generation + citations (task 2.2) and the LLM-reached not-found path (2.3)

Edit `.env` and replace the placeholder:

```
ANTHROPIC_API_KEY=sk-ant-...your real key...
```

Then run the module's own smoke test:

```bash
python src/rag_query.py
```

This calls `engine.query(...)` on four questions and prints the answer + citations for each.
Check:

- **Point-lookup** ("What was AWS revenue growth in Q2 2026?") — answer should state a growth
  figure matching the AMZN PDF, with a citation naming `AMZN-Q2-2026-Earnings-Release.pdf` and
  a page range (**2.2**).
- **Point-lookup** ("How much did Azure grow?") — should cite the MSFT press release with a
  matching growth number.
- **Summarization** ("Summarize Amazon's Q2 2026 earnings report") — should be a coherent
  multi-point summary grounded in retrieved AMZN chunks, not a single-fact answer (**2.2**,
  FR5).
- **Out-of-corpus** ("What was Apple's iPhone revenue in Q3 2024?") — should print the
  not-found message (`result.not_found == True`, empty citations) rather than a fabricated
  answer (**2.3**).

You can also call it interactively for more targeted checks:

```bash
PYTHONPATH=src python -c "
from rag_query import RAGQueryEngine
engine = RAGQueryEngine()
r = engine.query('What was AWS revenue growth in Q2 2026?')
print(r.answer)
for c in r.citations:
    print(c)
"
```

If steps 2 and 3 both check out, Phase 2 matches its spec.
