#!/usr/bin/env python3
"""Ingestion CLI: scan data/<TICKER>/*.pdf, chunk, embed, and persist to Chroma.

Run manually (see ADR-005): `python src/ingest.py`. Every run fully reprocesses
all PDFs under data/ — there is no incremental change detection.
"""

import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Tuple

import chromadb
from langchain_community.document_loaders import PyPDFLoader
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

DATA_DIR = Path("data")
VECTOR_DB_DIR = DATA_DIR / "vector_db"
EXCLUDED_DATA_SUBDIRS = {"vector_db"}
COLLECTION_NAME = "earnings_reports"

EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
CHUNK_SIZE = 1000
CHUNK_OVERLAP = 200

# Below this many non-whitespace characters across the whole document, treat
# the PDF as unreadable (e.g. a scanned/image-only PDF) and skip it (ADR-008,
# decision-log row 12).
MIN_EXTRACTED_CHARS = 50

# Quarter/year is extracted from the first few pages only (ADR-008).
EARLY_PAGE_COUNT = 3

TICKER_PATTERN = re.compile(r"^[A-Z]{1,6}$")

QUARTER_WORDS = {"first": "Q1", "second": "Q2", "third": "Q3", "fourth": "Q4"}
MONTH_NAME_TO_NUM = {
    name: i
    for i, name in enumerate(
        [
            "january", "february", "march", "april", "may", "june",
            "july", "august", "september", "october", "november", "december",
        ],
        start=1,
    )
}
MONTH_TO_QUARTER = {m: f"Q{(m - 1) // 3 + 1}" for m in range(1, 13)}

# "FY26 Q2", "FY 2026 Q2", "Q2 FY26" — a self-consistent fiscal quarter+year
# label straight from the document, tried first since it avoids the
# fiscal-vs-calendar-year mismatch ADR-008 flags as a landmine.
FY_QUARTER_RE = re.compile(
    r"FY\s?(\d{2,4}).{0,20}?Q([1-4])|Q([1-4]).{0,20}?FY\s?(\d{2,4})",
    re.IGNORECASE | re.DOTALL,
)
# "Second Quarter", "Third Quarter" — combined with a nearby year.
ORDINAL_QUARTER_RE = re.compile(r"\b(First|Second|Third|Fourth)\s+Quarter\b", re.IGNORECASE)
NEARBY_YEAR_RE = re.compile(r"(20\d{2})")
# "quarter[ly period] ended June 30, 2026" — quarter derived from the month
# via calendar-quarter mapping when no explicit quarter word is present.
ENDED_DATE_RE = re.compile(r"ended\s+([A-Za-z]+)\.?\s+\d{1,2},?\s+(20\d{2})", re.IGNORECASE)


def normalize_fy_year(raw: str) -> str:
    return f"20{raw}" if len(raw) == 2 else raw


def extract_quarter_year(text: str) -> Tuple[str, str]:
    """Regex/keyword extraction of (quarter, year) from early-page text, or
    ("unknown", "unknown") when nothing confidently matches (ADR-008)."""
    m = FY_QUARTER_RE.search(text)
    if m:
        if m.group(1) and m.group(2):
            return f"Q{m.group(2)}", normalize_fy_year(m.group(1))
        if m.group(3) and m.group(4):
            return f"Q{m.group(3)}", normalize_fy_year(m.group(4))

    quarter = None
    ordinal_match = ORDINAL_QUARTER_RE.search(text)
    if ordinal_match:
        quarter = QUARTER_WORDS[ordinal_match.group(1).lower()]
        nearby = text[ordinal_match.end(): ordinal_match.end() + 60]
        year_match = NEARBY_YEAR_RE.search(nearby)
        if year_match:
            return quarter, year_match.group(1)

    ended_match = ENDED_DATE_RE.search(text)
    if ended_match:
        month_num = MONTH_NAME_TO_NUM.get(ended_match.group(1).lower())
        year = ended_match.group(2)
        if quarter is None and month_num:
            quarter = MONTH_TO_QUARTER[month_num]
        if quarter:
            return quarter, year

    return "unknown", "unknown"


@dataclass
class PageSpan:
    start: int
    end: int
    page_number: int  # 1-indexed


def merge_pages(pages: List[Document]) -> Tuple[str, List[PageSpan]]:
    """Concatenate a PDF's per-page Documents into one text blob, tracking
    each page's character-offset span so chunks can carry page ranges even
    when they cross a page boundary (ADR-004)."""
    parts = []
    spans = []
    cursor = 0
    for page in pages:
        text = page.page_content
        start = cursor
        parts.append(text)
        cursor += len(text)
        spans.append(PageSpan(start=start, end=cursor, page_number=page.metadata["page"] + 1))
        parts.append("\n\n")
        cursor += 2
    return "".join(parts), spans


def page_at_offset(offset: int, spans: List[PageSpan]) -> int:
    for span in spans:
        if span.start <= offset < span.end:
            return span.page_number
    for span in spans:
        if offset < span.start:
            return span.page_number
    return spans[-1].page_number


def chunk_with_page_ranges(
    full_text: str, spans: List[PageSpan], splitter: RecursiveCharacterTextSplitter
) -> List[Tuple[str, int, int]]:
    """Split the merged text and map each chunk back to a page_start/page_end
    range by locating its offset in the merged text."""
    results = []
    search_from = 0
    for chunk_text in splitter.split_text(full_text):
        idx = full_text.find(chunk_text, search_from)
        if idx == -1:
            idx = full_text.find(chunk_text)
        page_start = page_at_offset(idx, spans)
        page_end = page_at_offset(max(idx + len(chunk_text) - 1, idx), spans)
        results.append((chunk_text, page_start, page_end))
        search_from = idx + 1
    return results


@dataclass
class RunSummary:
    processed: List[str] = field(default_factory=list)
    unknown_period: List[str] = field(default_factory=list)
    skipped: List[Tuple[str, str]] = field(default_factory=list)

    def print_summary(self) -> None:
        print("\n=== Ingestion Summary ===")
        print(f"Processed: {len(self.processed)}")
        for f in self.processed:
            print(f"  - {f}")
        print(f"Unknown quarter/year: {len(self.unknown_period)}")
        for f in self.unknown_period:
            print(f"  - {f}")
        print(f"Skipped: {len(self.skipped)}")
        for f, reason in self.skipped:
            print(f"  - {f} ({reason})")


def build_splitter() -> RecursiveCharacterTextSplitter:
    return RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=["\n\n", "\n", ". ", " ", ""],
        length_function=len,
    )


def ingest_pdf(
    pdf_path: Path, company: str, splitter: RecursiveCharacterTextSplitter, summary: RunSummary
) -> List[Document]:
    try:
        pages = PyPDFLoader(str(pdf_path)).load()
    except Exception as exc:
        summary.skipped.append((str(pdf_path), f"failed to load ({exc})"))
        return []

    full_text, spans = merge_pages(pages)
    if len(full_text.strip()) < MIN_EXTRACTED_CHARS:
        summary.skipped.append((str(pdf_path), "no extractable text (likely scanned/image-only PDF)"))
        return []

    early_text = "\n".join(p.page_content for p in pages[:EARLY_PAGE_COUNT])
    quarter, year = extract_quarter_year(early_text)
    if quarter == "unknown":
        summary.unknown_period.append(str(pdf_path))

    documents = []
    for chunk_text, page_start, page_end in chunk_with_page_ranges(full_text, spans, splitter):
        if not chunk_text.strip():
            continue
        documents.append(
            Document(
                page_content=chunk_text,
                metadata={
                    "company": company,
                    "quarter": quarter,
                    "year": year,
                    "page_start": page_start,
                    "page_end": page_end,
                    "source_filename": pdf_path.name,
                },
            )
        )

    summary.processed.append(str(pdf_path))
    return documents


def discover_ticker_folders(data_dir: Path) -> List[Path]:
    return sorted(
        p for p in data_dir.iterdir() if p.is_dir() and p.name not in EXCLUDED_DATA_SUBDIRS
    )


def reset_collection(persist_directory: Path, collection_name: str) -> None:
    """Every ingestion run fully reprocesses data/ (ADR-005) — drop any prior
    collection so reruns don't accumulate duplicate chunks."""
    persist_directory.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=str(persist_directory))
    if collection_name in {c.name for c in client.list_collections()}:
        client.delete_collection(collection_name)


def run_ingestion() -> RunSummary:
    if not DATA_DIR.exists():
        print(f"Data directory '{DATA_DIR}' does not exist.")
        sys.exit(1)

    summary = RunSummary()
    splitter = build_splitter()
    all_documents: List[Document] = []

    for ticker_dir in discover_ticker_folders(DATA_DIR):
        if not TICKER_PATTERN.match(ticker_dir.name):
            print(f"WARNING: '{ticker_dir}' is not a canonical uppercase ticker folder name — skipping")
            for pdf_path in sorted(ticker_dir.glob("*.pdf")):
                summary.skipped.append((str(pdf_path), f"invalid ticker folder name '{ticker_dir.name}'"))
            continue

        company = ticker_dir.name
        for pdf_path in sorted(ticker_dir.glob("*.pdf")):
            print(f"Ingesting {pdf_path} ...")
            all_documents.extend(ingest_pdf(pdf_path, company, splitter, summary))

    if not all_documents:
        print("No documents to embed.")
        summary.print_summary()
        return summary

    print(f"\nEmbedding {len(all_documents)} chunks with {EMBEDDING_MODEL} ...")
    embeddings = HuggingFaceEmbeddings(
        model_name=EMBEDDING_MODEL,
        model_kwargs={"device": "cpu"},
        encode_kwargs={"normalize_embeddings": True},
    )

    reset_collection(VECTOR_DB_DIR, COLLECTION_NAME)
    Chroma.from_documents(
        all_documents,
        embeddings,
        collection_name=COLLECTION_NAME,
        persist_directory=str(VECTOR_DB_DIR),
    )
    print(f"Persisted {len(all_documents)} chunks to {VECTOR_DB_DIR}")

    summary.print_summary()
    return summary


if __name__ == "__main__":
    run_ingestion()
