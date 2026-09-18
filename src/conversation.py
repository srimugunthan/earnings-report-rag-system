#!/usr/bin/env python3
"""Conversation Memory: bounded window + compaction + in-session episodic
memory, wrapping the Phase 2/3 RAGQueryEngine to make it conversation-aware
(system-design.md §2 Conversation Memory, §3 Data Model, §5 Data Flow;
ADR-006). Explicitly in-memory only per ADR-006 — nothing here is persisted
to disk; a real session stores a ConversationMemory instance in Streamlit's
`session_state` (Phase 5), but this module has no Streamlit dependency.
"""

import re
from dataclasses import dataclass, field
from typing import List, Optional

from langchain_core.messages import HumanMessage, SystemMessage

from rag_query import QueryResult, RAGQueryEngine

WINDOW_SIZE = 6  # last N raw turns (individual messages) kept verbatim (ADR-006)

COMPACTION_SYSTEM_PROMPT = (
    "You maintain a running summary of an ongoing conversation between a user and a "
    "financial-analyst assistant about quarterly earnings reports. Given the existing "
    "summary and one new message aging out of the raw conversation window, produce an "
    "updated, concise summary (a few sentences) that preserves the companies, quarters, "
    "and figures discussed so far. Do not drop information already in the existing summary."
)

# A small, fixed metric vocabulary matched by keyword — consistent with the
# regex/keyword extraction already used for quarter/year at ingestion time
# (ADR-008) rather than adding a second per-turn LLM call just for this.
METRIC_KEYWORDS = [
    "aws", "azure", "google cloud", "revenue", "net sales", "net income",
    "operating income", "operating margin", "gross margin", "eps",
    "earnings per share", "free cash flow", "capital expenditures",
]
# Requires either a leading $ or a trailing unit/percent word, so a bare
# number like the "2" in "Q2 2026" is never mistaken for an extracted figure.
VALUE_RE = re.compile(
    r"\$\s?\d[\d,]*\.?\d*\s?(?:billion|million|thousand)?"
    r"|\d[\d,]*\.?\d*\s?(?:%|percent|billion|million|thousand)",
    re.IGNORECASE,
)

# The LLM's own wording when it couldn't ground an answer (e.g. the company
# filter matched, but no retrieved chunk actually answers this question) —
# skip fact extraction rather than lifting an incidental number from a
# non-answer.
REFUSAL_MARKERS = ["i don't have", "not available", "not included", "no excerpts", "couldn't find"]


@dataclass
class Turn:
    role: str
    content: str


@dataclass
class EpisodicFact:
    turn: int
    company: str
    metric: str
    quarter: str
    value: str


class ConversationMemory:
    """Session-scoped state: bounded window, compaction summary, episodic
    facts. Construct a fresh instance per session — nothing here loads from
    or saves to disk (ADR-006)."""

    def __init__(self, window_size: int = WINDOW_SIZE):
        self.window_size = window_size
        self.window: List[Turn] = []
        self.summary: str = ""
        self.episodic_facts: List[EpisodicFact] = []
        self.turn_count = 0

    def retrieval_context(self, question: str) -> str:
        """Full window (not just the bare latest message) drives retrieval,
        so an elliptical follow-up like "how about Microsoft?" still embeds
        enough signal to retrieve the right chunks (task 4.1)."""
        parts = []
        if self.summary:
            parts.append(self.summary)
        parts.extend(t.content for t in self.window)
        parts.append(question)
        return "\n".join(parts)

    def generation_context(self) -> Optional[str]:
        """Summary + episodic facts + recent raw window, formatted for the
        generation prompt (system-design.md §5: "assemble prompt: retrieved
        chunks + citations + bounded window + compaction summary")."""
        parts = []
        if self.summary:
            parts.append(f"Conversation summary so far:\n{self.summary}")
        if self.episodic_facts:
            facts = "\n".join(
                f"- Turn {f.turn}: {f.company} {f.metric} ({f.quarter}) = {f.value}"
                for f in self.episodic_facts
            )
            parts.append(f"Facts established earlier in this conversation:\n{facts}")
        if self.window:
            recent = "\n".join(f"{t.role}: {t.content}" for t in self.window)
            parts.append(f"Recent conversation:\n{recent}")
        return "\n\n".join(parts) if parts else None

    def record_exchange(self, llm, question: str, result: QueryResult) -> None:
        self.turn_count += 1
        self._add_turn(llm, Turn("user", question))
        self._add_turn(llm, Turn("assistant", result.answer))
        self._extract_facts(self.turn_count, question, result)

    def _add_turn(self, llm, turn: Turn) -> None:
        self.window.append(turn)
        if len(self.window) > self.window_size:
            self._compact(llm, self.window.pop(0))

    def _compact(self, llm, aged_out: Turn) -> None:
        if llm is None:
            # LLM unavailable (Phase 3 degraded mode) -> fold in verbatim
            # rather than silently dropping the aged-out turn.
            addition = f"{aged_out.role}: {aged_out.content}"
            self.summary = f"{self.summary}\n{addition}".strip() if self.summary else addition
            return
        prompt = (
            f"Existing summary:\n{self.summary or '(none yet)'}\n\n"
            f"New message aging out of the window:\n{aged_out.role}: {aged_out.content}\n\n"
            "Updated summary:"
        )
        try:
            response = llm.invoke(
                [SystemMessage(content=COMPACTION_SYSTEM_PROMPT), HumanMessage(content=prompt)]
            )
            self.summary = response.content
        except Exception:
            addition = f"{aged_out.role}: {aged_out.content}"
            self.summary = f"{self.summary}\n{addition}".strip() if self.summary else addition

    def _extract_facts(self, turn_number: int, question: str, result: QueryResult) -> None:
        if result.not_found or not result.citations:
            return
        answer_lower = result.answer.lower()
        if any(marker in answer_lower for marker in REFUSAL_MARKERS):
            return
        combined = f"{question} {result.answer}".lower()
        metric = next((kw for kw in METRIC_KEYWORDS if kw in combined), None)
        if not metric:
            return
        value_match = VALUE_RE.search(result.answer)
        if not value_match:
            return
        citation = result.citations[0]
        self.episodic_facts.append(
            EpisodicFact(
                turn=turn_number,
                company=citation.company,
                metric=metric,
                quarter=f"{citation.quarter} {citation.year}",
                value=value_match.group(0),
            )
        )


def converse(
    engine: RAGQueryEngine,
    memory: ConversationMemory,
    question: str,
    company: Optional[str] = None,
) -> QueryResult:
    """Conversation-aware equivalent of `engine.query(question)` (system-design.md
    §4: `query(question, session_state) -> {answer, citations, degraded}`)."""
    # Company is detected from the CURRENT question only, not the whole window
    # blob — otherwise an earlier company mentioned in prior turns (still
    # present in retrieval_context for embedding purposes) could win over a
    # company actually named in this question. When this question doesn't
    # name a company, retrieval stays unscoped rather than guessing from
    # conversation history — a question can validly refer back to any earlier
    # company, not just the most recent one (see e.g. task 4.3's test, which
    # deliberately references the *first* company discussed after several
    # others have since been named).
    company = company or engine.detect_company(question)

    retrieval_query = memory.retrieval_context(question)
    result = engine.query(
        question,
        company=company,
        retrieval_query=retrieval_query,
        extra_context=memory.generation_context(),
    )
    memory.record_exchange(engine.llm, question, result)
    return result


if __name__ == "__main__":
    engine = RAGQueryEngine()
    memory = ConversationMemory()

    script = [
        "What was Amazon's AWS revenue growth in Q2 2026?",
        "How about Microsoft's cloud revenue?",
        "And Google's?",
        "What was Amazon's total net sales?",
        "What was Amazon's operating income?",
        "How did Microsoft's operating margin look?",
        "What about Google's operating income?",
        "Summarize Amazon's guidance for next quarter.",
        "What was Microsoft's EPS?",
        "Going back to the very first thing we discussed — what was that AWS growth figure again?",
    ]

    for i, question in enumerate(script, start=1):
        result = converse(engine, memory, question)
        print(f"[{i}] Q: {question}")
        print(f"    A: {result.answer}")
        print()

    print("=== Final conversation memory state ===")
    print(f"Window size: {len(memory.window)} raw turns")
    print(f"Summary: {memory.summary}")
    print("Episodic facts:")
    for f in memory.episodic_facts:
        print(f"  - {f}")
