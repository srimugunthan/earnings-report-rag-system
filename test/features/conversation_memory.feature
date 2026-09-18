Feature: Conversation memory
  As a user having a multi-turn conversation
  I want follow-up questions, long conversations, and earlier facts to work correctly
  So that the chat feels coherent across turns, not just within one question

  Background:
    Given the sample corpus has been ingested into a test vector store
    And the query engine uses a mocked LLM
    And a fresh conversation memory with window size 6

  Scenario: A follow-up question that only names a new company retrieves that company's chunks
    When I continue the conversation by asking "What was Amazon's AWS revenue growth in Q2 2026?"
    And I continue the conversation by asking "How about Microsoft's cloud revenue?"
    Then the last response's citations all name company "MSFT"

  Scenario: The conversation window never grows past its configured size
    When I hold a scripted 10-turn conversation
    Then the conversation window has at most 6 raw turns

  Scenario: A turn aging out of the window is folded into the running summary
    When I hold a scripted 10-turn conversation
    Then the conversation summary is not empty

  Scenario: An early fact is recoverable after compaction via episodic memory
    When I hold a scripted 10-turn conversation
    Then an episodic fact from turn 1 is recorded for company "AMZN"

  Scenario: A fresh conversation memory starts empty every session
    Then the conversation memory has an empty window, empty summary, and no episodic facts
