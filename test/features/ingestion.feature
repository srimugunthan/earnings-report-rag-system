Feature: Ingestion pipeline
  As the operator of the earnings RAG system
  I want ingest.py to correctly process, validate, and summarize earnings PDFs
  So that the vector store only ever contains well-attributed, well-cited chunks

  Background:
    Given a fresh temporary data directory

  Scenario: Ingesting a well-formed corpus produces correctly attributed chunks
    Given the sample PDFs for "AMZN" are placed in their ticker folder
    And the sample PDFs for "GOOG" are placed in their ticker folder
    And the sample PDFs for "MSFT" are placed in their ticker folder
    When I run the ingestion
    Then the vector store contains chunks for "AMZN"
    And the vector store contains chunks for "GOOG"
    And the vector store contains chunks for "MSFT"
    And every chunk has a "company", "quarter", "year", "page_start", "page_end", and "source_filename"

  Scenario: A chunk that spans a page boundary carries an accurate page range
    Given the sample PDFs for "GOOG" are placed in their ticker folder
    When I run the ingestion
    Then at least one chunk has a page_start different from its page_end
    And every chunk has page_start less than or equal to page_end

  Scenario: Quarter and year are extracted from the report content
    Given the sample PDFs for "AMZN" are placed in their ticker folder
    And the sample PDFs for "GOOG" are placed in their ticker folder
    And the sample PDFs for "MSFT" are placed in their ticker folder
    When I run the ingestion
    Then the "AMZN" chunks are attributed to quarter "Q2" and year "2026"
    And the "GOOG" chunks are attributed to quarter "Q2" and year "2026"
    And the "MSFT" chunks are attributed to quarter "Q2" and year "2026"

  Scenario: An image-only PDF with no extractable text is skipped, not ingested as noise
    Given the sample PDFs for "MSFT" are placed in their ticker folder
    When I run the ingestion
    Then the run summary lists the MSFT slides deck as skipped
    And the run summary does not list it as processed

  Scenario: A non-canonical ticker folder name is rejected, not silently ingested
    Given a PDF is placed in a folder named "Google" instead of a valid ticker
    When I run the ingestion
    Then the run summary lists that file as skipped
    And no chunk in the vector store has company "Google"

  Scenario: Rerunning ingestion on unchanged data does not duplicate chunks
    Given the sample PDFs for "AMZN" are placed in their ticker folder
    When I run the ingestion
    And I run the ingestion again
    Then the total chunk count is the same after both runs
