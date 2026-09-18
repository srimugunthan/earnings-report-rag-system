#!/usr/bin/env python3
"""Chat UI (Streamlit): wires the fallback-aware, conversation-aware query
function into an interactive chat (system-design.md §2 Chat UI, §5 startup +
render flow; ADR-001; decision-log row 11).

Run with: streamlit run src/app.py
"""

from pathlib import Path

import streamlit as st

from conversation import ConversationMemory, converse
from rag_query import DEGRADED_NOTICE, RAGQueryEngine

VECTOR_DB_DIR = Path("data/vector_db")


def vector_store_ready(persist_directory: Path) -> bool:
    """Task 5.4's guard condition, pulled out as a pure function so it's
    testable without a running Streamlit script context."""
    return persist_directory.exists() and any(persist_directory.iterdir())


@st.cache_resource
def load_engine() -> RAGQueryEngine:
    return RAGQueryEngine()


def citation_to_dict(citation) -> dict:
    return {
        "source_filename": citation.source_filename,
        "company": citation.company,
        "quarter": citation.quarter,
        "year": citation.year,
        "page_start": citation.page_start,
        "page_end": citation.page_end,
    }


def render_citation(c: dict) -> str:
    return f"{c['company']} {c['quarter']} {c['year']} — {c['source_filename']}, p.{c['page_start']}-{c['page_end']}"


def render_assistant_message(msg: dict) -> None:
    if msg["degraded"]:
        st.warning(DEGRADED_NOTICE)
        for excerpt, citation in zip(msg["excerpts"], msg["citations"]):
            st.markdown(f"**{render_citation(citation)}**")
            st.markdown(f"> {excerpt}")
    else:
        st.markdown(msg["answer"])
        if msg["citations"]:
            with st.expander("Sources"):
                for c in msg["citations"]:
                    st.markdown(f"- {render_citation(c)}")


def main() -> None:
    st.set_page_config(page_title="Earnings Report Chat", page_icon="📊")
    st.title("📊 Earnings Report Chat")

    # Task 5.4: startup check. Never auto-rebuild, never silently fall back to
    # an empty chat (decision-log row 11, consistent with ADR-005's
    # manual-only ingestion trigger) — just tell the user what to run.
    if not vector_store_ready(VECTOR_DB_DIR):
        st.error(
            f"No ingested data found at `{VECTOR_DB_DIR}`. Run `python src/ingest.py` first "
            "to build the vector store, then restart this app."
        )
        st.stop()

    try:
        engine = load_engine()
        if not engine.known_companies():
            raise RuntimeError("the vector store has no ingested chunks")
    except Exception as exc:
        st.error(
            f"The vector store could not be read ({exc}) — it may be missing or corrupted. "
            "Run `python src/ingest.py` first, then restart this app."
        )
        st.stop()

    if "memory" not in st.session_state:
        st.session_state.memory = ConversationMemory()
    if "messages" not in st.session_state:
        st.session_state.messages = []

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            if msg["role"] == "user":
                st.markdown(msg["content"])
            else:
                render_assistant_message(msg)

    question = st.chat_input("Ask about a company's earnings report...")
    if question:
        st.session_state.messages.append({"role": "user", "content": question})
        with st.chat_message("user"):
            st.markdown(question)

        with st.chat_message("assistant"):
            result = converse(engine, st.session_state.memory, question)
            assistant_msg = {
                "role": "assistant",
                "answer": result.answer,
                "citations": [citation_to_dict(c) for c in result.citations],
                "excerpts": result.excerpts,
                "degraded": result.degraded,
                "not_found": result.not_found,
            }
            render_assistant_message(assistant_msg)

        st.session_state.messages.append(assistant_msg)


if __name__ == "__main__":
    main()
