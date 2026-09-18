"""Shared test helpers used across step files. Not a step-definition module
itself (no @given/@when/@then here) — behave imports every .py file under
steps/, and a plain helper module is fine alongside the decorated ones.
"""

import shutil
import tempfile
from pathlib import Path
from types import SimpleNamespace


class FakeLLM:
    """Deterministic stand-in for ChatAnthropic so scenarios run without a
    real API key, network call, or Claude's non-deterministic phrasing.

    By default it echoes the human prompt back (prefixed) rather than
    returning a fixed string, so the real retrieved-excerpt text (with real
    figures from the sample PDFs) still flows through `result.answer` —
    letting scenarios that check citations/grounding/episodic-fact
    extraction exercise real data, without depending on the LLM's actual
    reasoning quality.
    """

    def __init__(self, fixed_response=None):
        self.fixed_response = fixed_response
        self.should_fail = False
        self.calls = []

    def invoke(self, messages):
        self.calls.append(messages)
        if self.should_fail:
            raise RuntimeError("simulated provider failure")
        if self.fixed_response is not None:
            content = self.fixed_response
        else:
            human = next((m.content for m in messages if getattr(m, "type", "") == "human"), "")
            content = f"[MOCK ANSWER]\n{human}"
        return SimpleNamespace(content=content)


_SHARED_STORE_CACHE = {}


def get_shared_test_vector_store(repo_root: Path) -> Path:
    """Build (once per test process) an isolated Chroma store from the real
    sample corpus under data/<TICKER>/, so retrieval/fallback/conversation
    scenarios query real, already-verified data without ever touching the
    project's actual data/vector_db. Cached because re-embedding ~350 chunks
    is the slow part of this suite — no need to repeat it per scenario."""
    if "path" in _SHARED_STORE_CACHE:
        return _SHARED_STORE_CACHE["path"]

    import ingest

    tmp_dir = Path(tempfile.mkdtemp(prefix="bdd_shared_corpus_"))
    data_dir = tmp_dir / "data"
    for ticker in ("AMZN", "GOOG", "MSFT"):
        src_dir = repo_root / "data" / ticker
        dst_dir = data_dir / ticker
        dst_dir.mkdir(parents=True, exist_ok=True)
        for pdf in src_dir.glob("*.pdf"):
            shutil.copy(pdf, dst_dir / pdf.name)

    vector_db_dir = tmp_dir / "vector_db"

    original_data_dir = ingest.DATA_DIR
    original_vector_db_dir = ingest.VECTOR_DB_DIR
    ingest.DATA_DIR = data_dir
    ingest.VECTOR_DB_DIR = vector_db_dir
    try:
        ingest.run_ingestion()
    finally:
        ingest.DATA_DIR = original_data_dir
        ingest.VECTOR_DB_DIR = original_vector_db_dir

    _SHARED_STORE_CACHE["path"] = vector_db_dir
    return vector_db_dir
