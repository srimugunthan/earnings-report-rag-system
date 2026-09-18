import tempfile
from pathlib import Path

import app
from behave import given, then


@given("a data directory path that does not exist")
def step_nonexistent_path(context):
    context.candidate_path = Path(tempfile.mkdtemp(prefix="bdd_missing_")) / "does_not_exist"


@given("an existing but empty vector store directory")
def step_existing_empty_dir(context):
    context.candidate_path = Path(tempfile.mkdtemp(prefix="bdd_empty_"))


@then("the app considers the vector store not ready")
def step_not_ready(context):
    assert app.vector_store_ready(context.candidate_path) is False


@then("the app considers the vector store ready")
def step_ready(context):
    assert app.vector_store_ready(context.vector_db_dir) is True
