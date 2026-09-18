#!/usr/bin/env python3
"""RAG Query Engine: single-turn retrieval + grounded generation over the
Phase 1 Chroma store (system-design.md §2 RAG Query Engine, §5 Query flow).
"""

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from dotenv import load_dotenv
from langchain_anthropic import ChatAnthropic
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma
from langchain_core.documents import Document
from langchain_core.messages import HumanMessage, SystemMessage

load_dotenv()

VECTOR_DB_DIR = Path("data/vector_db")
COLLECTION_NAME = "earnings_reports"
EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
LLM_MODEL = "claude-haiku-4-5-20251001"
TOP_K = 4

# Chroma's default metric is squared L2 distance (lower = more similar); since
# ingest.py normalizes embeddings, this stays a well-behaved 0-4 range.
# Calibrated against the sample corpus: genuinely relevant chunks scored
# ~0.55-1.03, clearly irrelevant questions scored ~1.55-1.72. 1.3 sits
# comfortably between the two.
MAX_DISTANCE = 1.3

# Minimal alias map so a company named in plain English resolves to its
# ticker folder name. "AAPL" is included deliberately even though it's never
# ingested in the sample corpus, so a PRD-style Apple question exercises the
# not-found path (FR3) rather than silently going unmatched.
COMPANY_ALIASES: Dict[str, List[str]] = {
    "AMZN": ["amzn", "amazon"],
    "GOOG": ["goog", "googl", "google", "alphabet"],
    "MSFT": ["msft", "microsoft"],
    "AAPL": ["aapl", "apple"],
}

NOT_FOUND_MESSAGE = "I couldn't find anything about that in the ingested earnings reports."
DEGRADED_NOTICE = "LLM unavailable — showing matching excerpts only."

SYSTEM_PROMPT = (
    "You are a financial analyst assistant answering questions about quarterly earnings "
    "reports. Answer ONLY using the excerpts provided below — never use outside knowledge. "
    "If the excerpts don't contain the answer, say so plainly instead of guessing. When you "
    "state a figure or fact, mention which company and period it's from."
)


@dataclass
class Citation:
    source_filename: str
    company: str
    quarter: str
    year: str
    page_start: int
    page_end: int


@dataclass
class QueryResult:
    question: str
    answer: str
    citations: List[Citation]
    excerpts: List[str] = field(default_factory=list)
    not_found: bool = False
    degraded: bool = False


class RAGQueryEngine:
    def __init__(
        self,
        persist_directory: Path = VECTOR_DB_DIR,
        collection_name: str = COLLECTION_NAME,
        top_k: int = TOP_K,
        max_distance: float = MAX_DISTANCE,
    ):
        if not persist_directory.exists():
            raise FileNotFoundError(
                f"Vector store not found at '{persist_directory}'. Run `python src/ingest.py` first."
            )
        self.top_k = top_k
        self.max_distance = max_distance
        self.embeddings = HuggingFaceEmbeddings(
            model_name=EMBEDDING_MODEL,
            model_kwargs={"device": "cpu"},
            encode_kwargs={"normalize_embeddings": True},
        )
        self.vector_store = Chroma(
            collection_name=collection_name,
            embedding_function=self.embeddings,
            persist_directory=str(persist_directory),
        )
        # No API key -> no LLM call attempted at all (ADR-007); the app never
        # refuses to start over this, it just runs in degraded mode.
        self.llm: Optional[ChatAnthropic] = None
        if os.environ.get("ANTHROPIC_API_KEY", "").strip():
            try:
                self.llm = ChatAnthropic(model=LLM_MODEL, temperature=0)
            except Exception:
                self.llm = None

    def known_companies(self) -> Set[str]:
        data = self.vector_store.get(include=["metadatas"])
        return {m["company"] for m in data["metadatas"]}

    def detect_company(self, question: str) -> Optional[str]:
        q_lower = question.lower()
        for ticker, aliases in COMPANY_ALIASES.items():
            if any(alias in q_lower for alias in aliases):
                return ticker
        return None

    def retrieve(
        self, question: str, company: Optional[str] = None
    ) -> List[Tuple[Document, float]]:
        filter_ = {"company": company} if company else None
        return self.vector_store.similarity_search_with_score(question, k=self.top_k, filter=filter_)

    def query(
        self,
        question: str,
        company: Optional[str] = None,
        retrieval_query: Optional[str] = None,
        extra_context: Optional[str] = None,
    ) -> QueryResult:
        """`retrieval_query` and `extra_context` let a conversation-aware caller
        (Phase 4) drive retrieval with more than the bare latest message and add
        summary/episodic context to the prompt, without changing single-turn
        (Phase 2/3) behavior when they're omitted."""
        retrieval_text = retrieval_query if retrieval_query is not None else question
        company = (company or self.detect_company(retrieval_text)) or None
        if company:
            company = company.upper()
            if company not in self.known_companies():
                return QueryResult(question, NOT_FOUND_MESSAGE, [], not_found=True)

        results = self.retrieve(retrieval_text, company=company)
        if not results or results[0][1] > self.max_distance:
            return QueryResult(question, NOT_FOUND_MESSAGE, [], not_found=True)

        chunks = [doc for doc, _score in results]
        context = "\n\n".join(
            f"[{doc.metadata['company']} {doc.metadata['quarter']} {doc.metadata['year']} — "
            f"{doc.metadata['source_filename']}, p.{doc.metadata['page_start']}-{doc.metadata['page_end']}]\n"
            f"{doc.page_content}"
            for doc in chunks
        )
        citations = [
            Citation(
                source_filename=doc.metadata["source_filename"],
                company=doc.metadata["company"],
                quarter=doc.metadata["quarter"],
                year=doc.metadata["year"],
                page_start=doc.metadata["page_start"],
                page_end=doc.metadata["page_end"],
            )
            for doc in chunks
        ]

        # No key configured -> degrade without attempting a call (task 3.1).
        if self.llm is None:
            excerpts = [doc.page_content for doc in chunks]
            return QueryResult(question, DEGRADED_NOTICE, citations, excerpts, degraded=True)

        user_prompt = f"Excerpts:\n{context}\n\nQuestion: {question}"
        if extra_context:
            user_prompt = f"{extra_context}\n\n{user_prompt}"
        try:
            response = self.llm.invoke(
                [SystemMessage(content=SYSTEM_PROMPT), HumanMessage(content=user_prompt)]
            )
        except Exception:
            # Runtime failure (timeout/rate-limit/provider error/bad key) ->
            # same degraded shape, scoped to this call only (task 3.2).
            excerpts = [doc.page_content for doc in chunks]
            return QueryResult(question, DEGRADED_NOTICE, citations, excerpts, degraded=True)

        return QueryResult(question, response.content, citations, not_found=False)


if __name__ == "__main__":
    engine = RAGQueryEngine()
    questions = [
        "What was AWS revenue growth in Q2 2026?",
        "How much did Azure grow?",
        "Summarize Amazon's Q2 2026 earnings report",
        "What was Apple's iPhone revenue in Q3 2024?",
    ]
    for q in questions:
        result = engine.query(q)
        print(f"Q: {q}")
        print(f"A: {result.answer}" + (" [degraded]" if result.degraded else ""))
        if result.citations:
            print("Citations:")
            for c in result.citations:
                print(f"  - {c.company} {c.quarter} {c.year} — {c.source_filename}, p.{c.page_start}-{c.page_end}")
        print()
