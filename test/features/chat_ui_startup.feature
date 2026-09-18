Feature: Chat UI startup guard
  As a user launching the chat app
  I want a clear error if the vector store is missing, not a crash or an unusable empty chat
  So that I always know to run ingestion first

  Scenario: A missing vector store directory is not considered ready
    Given a data directory path that does not exist
    Then the app considers the vector store not ready

  Scenario: An empty vector store directory is not considered ready
    Given an existing but empty vector store directory
    Then the app considers the vector store not ready

  Scenario: A populated vector store directory is considered ready
    Given the sample corpus has been ingested into a test vector store
    Then the app considers the vector store ready
