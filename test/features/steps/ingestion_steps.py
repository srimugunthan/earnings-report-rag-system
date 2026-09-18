import shutil
import tempfile
from pathlib import Path

import chromadb
import ingest
from behave import given, then, when


def _copy_ticker_pdfs(repo_root: Path, data_dir: Path, ticker: str) -> None:
    src_dir = repo_root / "data" / ticker
    dst_dir = data_dir / ticker
    dst_dir.mkdir(parents=True, exist_ok=True)
    for pdf in src_dir.glob("*.pdf"):
        shutil.copy(pdf, dst_dir / pdf.name)


def _run_ingestion(context):
    original_data_dir = ingest.DATA_DIR
    original_vector_db_dir = ingest.VECTOR_DB_DIR
    ingest.DATA_DIR = context.data_dir
    ingest.VECTOR_DB_DIR = context.vector_db_dir
    try:
        context.last_summary = ingest.run_ingestion()
    finally:
        ingest.DATA_DIR = original_data_dir
        ingest.VECTOR_DB_DIR = original_vector_db_dir


def _collection(context):
    client = chromadb.PersistentClient(path=str(context.vector_db_dir))
    return client.get_collection(ingest.COLLECTION_NAME)


def _collection_count(context) -> int:
    try:
        return _collection(context).count()
    except Exception:
        return 0


def _all_metadatas(context):
    try:
        col = _collection(context)
    except Exception:
        return []
    return col.get(limit=col.count(), include=["metadatas"])["metadatas"]


@given("a fresh temporary data directory")
def step_fresh_temp_data_dir(context):
    context.tmp_dir = Path(tempfile.mkdtemp(prefix="bdd_ingest_"))
    context.data_dir = context.tmp_dir / "data"
    context.vector_db_dir = context.tmp_dir / "vector_db"
    context.data_dir.mkdir(parents=True, exist_ok=True)


@given('the sample PDFs for "{ticker}" are placed in their ticker folder')
def step_place_sample_pdfs(context, ticker):
    _copy_ticker_pdfs(context.repo_root, context.data_dir, ticker)


@given('a PDF is placed in a folder named "{folder_name}" instead of a valid ticker')
def step_place_pdf_in_bad_folder(context, folder_name):
    src_pdf = next((context.repo_root / "data" / "AMZN").glob("*.pdf"))
    dst_dir = context.data_dir / folder_name
    dst_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy(src_pdf, dst_dir / src_pdf.name)


@when("I run the ingestion")
def step_run_ingestion(context):
    _run_ingestion(context)
    context.run_summaries.append(_collection_count(context))


@when("I run the ingestion again")
def step_run_ingestion_again(context):
    step_run_ingestion(context)


@then('the vector store contains chunks for "{ticker}"')
def step_store_contains_company(context, ticker):
    present = {m["company"] for m in _all_metadatas(context)}
    assert ticker in present, f"expected company {ticker!r} in store, present: {present}"


@then('every chunk has a "company", "quarter", "year", "page_start", "page_end", and "source_filename"')
def step_every_chunk_has_metadata(context):
    required = {"company", "quarter", "year", "page_start", "page_end", "source_filename"}
    metadatas = _all_metadatas(context)
    assert metadatas, "expected at least one chunk in the store"
    for md in metadatas:
        missing = required - set(md.keys())
        assert not missing, f"chunk metadata missing keys: {missing} in {md}"


@then("at least one chunk has a page_start different from its page_end")
def step_at_least_one_spanning_chunk(context):
    spanning = [m for m in _all_metadatas(context) if m["page_start"] != m["page_end"]]
    assert spanning, "expected at least one cross-page chunk, found none"


@then("every chunk has page_start less than or equal to page_end")
def step_page_start_le_page_end(context):
    metadatas = _all_metadatas(context)
    assert metadatas, "expected at least one chunk in the store"
    for md in metadatas:
        assert md["page_start"] <= md["page_end"], f"page_start > page_end in {md}"


@then('the "{ticker}" chunks are attributed to quarter "{quarter}" and year "{year}"')
def step_quarter_year_attribution(context, ticker, quarter, year):
    matching = [m for m in _all_metadatas(context) if m["company"] == ticker]
    assert matching, f"no chunks found for {ticker}"
    for md in matching:
        assert md["quarter"] == quarter, f"{ticker} chunk quarter {md['quarter']!r} != {quarter!r}"
        assert md["year"] == year, f"{ticker} chunk year {md['year']!r} != {year!r}"


@then("the run summary lists the MSFT slides deck as skipped")
def step_slides_deck_skipped(context):
    assert any(
        "SlidesFY26q2.pdf" in path for path, _reason in context.last_summary.skipped
    ), f"slides deck not found in skipped list: {context.last_summary.skipped}"


@then("the run summary does not list it as processed")
def step_slides_deck_not_processed(context):
    assert not any(
        "SlidesFY26q2.pdf" in path for path in context.last_summary.processed
    ), f"slides deck unexpectedly processed: {context.last_summary.processed}"


@then("the run summary lists that file as skipped")
def step_bad_folder_file_skipped(context):
    assert context.last_summary.skipped, "expected at least one skipped file"


@then('no chunk in the vector store has company "{company}"')
def step_no_chunk_has_company(context, company):
    present = {m["company"] for m in _all_metadatas(context)}
    assert company not in present, f"unexpectedly found company {company!r} in store"


@then("the total chunk count is the same after both runs")
def step_same_chunk_count_after_rerun(context):
    assert len(context.run_summaries) >= 2, f"expected at least two recorded runs, got {context.run_summaries}"
    assert context.run_summaries[0] == context.run_summaries[-1], (
        f"chunk count changed across reruns: {context.run_summaries}"
    )
