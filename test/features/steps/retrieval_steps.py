from behave import given, then, when
from common import FakeLLM, get_shared_test_vector_store
from rag_query import RAGQueryEngine


@given("the sample corpus has been ingested into a test vector store")
def step_shared_corpus(context):
    context.vector_db_dir = get_shared_test_vector_store(context.repo_root)
    # A fresh engine per scenario (not a cached/shared instance) — its .llm
    # attribute gets mutated by later steps (fallback scenarios especially),
    # and reusing one instance across scenarios would leak that state.
    context.engine = RAGQueryEngine(persist_directory=context.vector_db_dir)


@given("the query engine uses a mocked LLM")
def step_mocked_llm(context):
    context.fake_llm = FakeLLM()
    context.engine.llm = context.fake_llm


@when('I retrieve chunks for the question "{question}" scoped to company "{company}"')
def step_retrieve_scoped(context, question, company):
    context.retrieved = context.engine.retrieve(question, company=company)


@when('I retrieve chunks for the question "{question}" with no company filter')
def step_retrieve_unscoped(context, question):
    context.retrieved = context.engine.retrieve(question)


@then('every retrieved chunk belongs to company "{company}"')
def step_every_chunk_belongs_to(context, company):
    companies = {doc.metadata["company"] for doc, _score in context.retrieved}
    assert companies == {company}, f"expected only {company!r}, got {companies}"


@then("chunks from more than one company are returned")
def step_multiple_companies_returned(context):
    companies = {doc.metadata["company"] for doc, _score in context.retrieved}
    assert len(companies) > 1, f"expected multiple companies, got {companies}"


@when('I ask "{question}"')
def step_ask(context, question):
    context.result = context.engine.query(question)


@then("the response is not a refusal")
def step_not_refusal(context):
    assert not context.result.not_found, f"unexpected refusal: {context.result.answer}"


@then("the response is a refusal")
def step_is_refusal(context):
    assert context.result.not_found, f"expected a refusal, got: {context.result.answer}"


@then("the response is not degraded")
def step_not_degraded(context):
    assert not context.result.degraded, f"unexpectedly degraded: {context.result.answer}"


@then("the response is degraded")
def step_is_degraded(context):
    assert context.result.degraded, f"expected degraded response, got: {context.result.answer}"


@then("the response has citations")
def step_has_citations(context):
    assert context.result.citations, "expected at least one citation"


@then("the response has no citations")
def step_has_no_citations(context):
    assert not context.result.citations, f"expected no citations, got {context.result.citations}"


@then('every citation names company "{company}"')
def step_every_citation_names(context, company):
    companies = {c.company for c in context.result.citations}
    assert companies == {company}, f"expected only {company!r}, got {companies}"


@then("the response has excerpts")
def step_has_excerpts(context):
    assert context.result.excerpts, "expected non-empty excerpts"
