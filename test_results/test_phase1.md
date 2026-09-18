# Testing Phase 1 (Ingestion Pipeline)

How to verify [`ingest.py`](../src/ingest.py) against its spec's acceptance criteria
(`specs/earnings-rag-chat-system/phase1-ingestion-pipeline.md`).

## 1. Activate the environment

```bash
cd /Users/srimugunthan/Documents/gitrepos/earnings-rag-system
source .venv/bin/activate
```

## 2. Run the ingestion

```bash
python src/ingest.py
```

You should see each PDF being ingested and a final summary. Expected output shape:

```
Ingesting data/AMZN/AMZN-Q2-2026-Earnings-Release.pdf ...
Ingesting data/GOOG/GOOG-10-Q-Q2-2026.pdf ...
Ingesting data/MSFT/FY26 Q2 - Press Releases - Investor Relations - Microsoft.pdf ...
Ingesting data/MSFT/SlidesFY26q2.pdf ...
Embedding 350 chunks with sentence-transformers/all-MiniLM-L6-v2 ...
Persisted 350 chunks to data/vector_db

=== Ingestion Summary ===
Processed: 3
Unknown quarter/year: 0
Skipped: 1
  - data/MSFT/SlidesFY26q2.pdf (no extractable text (likely scanned/image-only PDF))
```

This alone confirms task **1.4**'s image-only-PDF skip (the slides deck genuinely has zero
extractable text on every page) and task **1.5**'s summary (three categories printed).

## 3. Inspect the store directly (the phase's own "independently testable" bar — no UI/LLM needed)

```bash
python -c "
import chromadb
client = chromadb.PersistentClient(path='data/vector_db')
col = client.get_collection('earnings_reports')
print('total chunks:', col.count())
res = col.get(limit=5, include=['metadatas','documents'])
for md, doc in zip(res['metadatas'], res['documents']):
    print(md)
    print(repr(doc[:80]))
"
```

Check that `company`, `quarter`, `year`, `page_start`, `page_end`, `source_filename` are all
populated (**1.1**).

## 4. Check cross-page chunking (task 1.2)

```bash
python -c "
import chromadb
client = chromadb.PersistentClient(path='data/vector_db')
col = client.get_collection('earnings_reports')
res = col.get(limit=col.count(), include=['metadatas'])
spanning = [m for m in res['metadatas'] if m['page_start'] != m['page_end']]
within   = [m for m in res['metadatas'] if m['page_start'] == m['page_end']]
print('spanning chunks:', len(spanning), '| within-page chunks:', len(within))
print(spanning[0] if spanning else 'none found')
"
```

A chunk with `page_start != page_end` confirms cross-page citation tracking works; the rest
should have `page_start == page_end`.

## 5. Check quarter/year extraction (task 1.3)

```bash
python -c "
import chromadb
client = chromadb.PersistentClient(path='data/vector_db')
col = client.get_collection('earnings_reports')
for company in ['AMZN', 'GOOG', 'MSFT']:
    m = col.get(where={'company': company}, limit=1, include=['metadatas'])['metadatas'][0]
    print(company, '->', m['quarter'], m['year'])
"
```

Expect `Q2 2026` for all three (matches the real filenames/labels).

## 6. Check folder-name validation (task 1.4, the other half)

Temporarily drop a PDF into a badly-named folder and confirm it's rejected, not silently
ingested:

```bash
mkdir -p data/Google
cp data/AMZN/AMZN-Q2-2026-Earnings-Release.pdf data/Google/
python src/ingest.py   # should print a WARNING and list it under Skipped
rm data/Google/AMZN-Q2-2026-Earnings-Release.pdf
rmdir data/Google
python src/ingest.py   # restore the clean store (rerun is safe — no duplicate accumulation)
```

## 7. Check retrieval works end-to-end (sanity beyond raw metadata)

```bash
python -c "
from langchain_community.vectorstores import Chroma
from langchain_community.embeddings import HuggingFaceEmbeddings
emb = HuggingFaceEmbeddings(model_name='sentence-transformers/all-MiniLM-L6-v2', model_kwargs={'device':'cpu'}, encode_kwargs={'normalize_embeddings': True})
vs = Chroma(collection_name='earnings_reports', embedding_function=emb, persist_directory='data/vector_db')
for doc in vs.similarity_search('AWS revenue growth', k=1):
    print(doc.metadata['company'], doc.metadata['source_filename'], doc.page_content[:100])
"
```

Should return an AMZN chunk about AWS.

If `python src/ingest.py` completes without errors and steps 3–7 all check out, Phase 1 is
working as specified.
