from behave import given, then, when
from conversation import ConversationMemory, converse

SCRIPT = [
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


@given("a fresh conversation memory with window size {size:d}")
def step_fresh_memory(context, size):
    context.memory = ConversationMemory(window_size=size)


@when('I continue the conversation by asking "{question}"')
def step_continue_conversation(context, question):
    context.result = converse(context.engine, context.memory, question)


@when("I hold a scripted 10-turn conversation")
def step_scripted_conversation(context):
    for question in SCRIPT:
        context.result = converse(context.engine, context.memory, question)


@then('the last response\'s citations all name company "{company}"')
def step_last_response_citations_company(context, company):
    companies = {c.company for c in context.result.citations}
    assert companies == {company}, f"expected only {company!r}, got {companies}"


@then("the conversation window has at most {size:d} raw turns")
def step_window_at_most(context, size):
    assert len(context.memory.window) <= size, (
        f"window has {len(context.memory.window)} turns, expected <= {size}"
    )


@then("the conversation summary is not empty")
def step_summary_not_empty(context):
    assert context.memory.summary.strip(), "expected a non-empty compaction summary"


@then('an episodic fact from turn {turn:d} is recorded for company "{company}"')
def step_episodic_fact_recorded(context, turn, company):
    matching = [f for f in context.memory.episodic_facts if f.turn == turn and f.company == company]
    assert matching, (
        f"no episodic fact found for turn {turn} / company {company!r}; "
        f"facts recorded: {context.memory.episodic_facts}"
    )


@then("the conversation memory has an empty window, empty summary, and no episodic facts")
def step_memory_is_empty(context):
    assert context.memory.window == [], context.memory.window
    assert context.memory.summary == "", context.memory.summary
    assert context.memory.episodic_facts == [], context.memory.episodic_facts
