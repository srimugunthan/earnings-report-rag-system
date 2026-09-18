Feature: LLM-unavailability fallback
  As a user of the earnings chat
  I want the app to keep working when the LLM is unavailable
  So that a missing key or a transient provider failure never breaks the chat

  Background:
    Given the sample corpus has been ingested into a test vector store

  Scenario: No LLM configured returns a degraded response, not an exception
    Given the query engine has no LLM configured
    When I ask "What was AWS revenue growth in Q2 2026?"
    Then the response is degraded
    And the response has excerpts
    And the response has citations

  Scenario: A runtime LLM failure degrades gracefully for that call only
    Given the query engine uses a mocked LLM
    And the mocked LLM is set to fail
    When I ask "What was AWS revenue growth in Q2 2026?"
    Then the response is degraded

  Scenario: The LLM recovering produces a normal answer on the next call
    Given the query engine uses a mocked LLM
    And the mocked LLM is set to fail
    When I ask "What was AWS revenue growth in Q2 2026?"
    And the mocked LLM recovers
    And I ask "What was AWS revenue growth in Q2 2026?"
    Then the response is not degraded
