from behave import step

# @step (not @given/@when) throughout this file: behave buckets step
# definitions by their resolved Given/When/Then type, and an "And" inherits
# the type of the PRECEDING step keyword — so "the mocked LLM recovers"
# (which follows a "When" in llm_fallback.feature) would never match a
# @given-registered step. @step registers into the type-agnostic bucket that
# every resolved type falls back to, regardless of where it's used.


@step("the query engine has no LLM configured")
def step_no_llm(context):
    # Exercises the same degradation logic RAGQueryEngine.query() hits when
    # ANTHROPIC_API_KEY is unset (self.llm is None) — set directly here so
    # the scenario is deterministic regardless of this machine's real .env.
    context.engine.llm = None


@step("the mocked LLM is set to fail")
def step_llm_set_to_fail(context):
    context.fake_llm.should_fail = True


@step("the mocked LLM recovers")
def step_llm_recovers(context):
    context.fake_llm.should_fail = False
