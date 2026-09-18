Feature: Retrieval and grounded generation
  As a user of the earnings chat
  I want questions answered using only retrieved report content, with citations
  So that I can trust answers are grounded and traceable to a source document/page

  Background:
    Given the sample corpus has been ingested into a test vector store
    And the query engine uses a mocked LLM

  Scenario: A company-scoped query only returns that company's chunks
    When I retrieve chunks for the question "revenue growth" scoped to company "AMZN"
    Then every retrieved chunk belongs to company "AMZN"

  Scenario: An unscoped query can return chunks from multiple companies
    When I retrieve chunks for the question "cloud revenue growth" with no company filter
    Then chunks from more than one company are returned

  Scenario: A point-lookup question returns a grounded answer with citations
    When I ask "What was AWS revenue growth in Q2 2026?"
    Then the response is not a refusal
    And the response is not degraded
    And the response has citations
    And every citation names company "AMZN"

  Scenario: A question about a company never ingested is refused, not fabricated
    When I ask "What was Apple's iPhone revenue in Q3 2024?"
    Then the response is a refusal
    And the response has no citations

  Scenario: A question with genuinely relevant content does not trigger the refusal path
    When I ask "What was Amazon's total net sales in Q2 2026?"
    Then the response is not a refusal
