# Phase 3, step 3: Acceptance tests and QA checks

Each criterion below becomes a test the founder (or a later automated build) runs against the MVP.

| Story | Acceptance criterion | Check |
|---|---|---|
| US1 | Given I am on the upload page, when I select a PDF file and click "Generate Summary & Questions", then a summary appears within 30 seconds. | testable |
| US1 | Given a file is uploaded, when the summary is shown, then it contains at least three bullet‑point key concepts. | testable |
| US2 | Given the summary generation completes, when the process finishes, then a list of at least five practice questions is displayed. | testable |
| US2 | Given the questions are shown, when I view them, then each question references a concept mentioned in the summary. | testable |
| US3 | Given a file has been processed, when the results page loads, then the server logs indicate the original file has been removed. | testable |
| US3 | Given the file is deleted, when I attempt to access the original upload endpoint for that file, then I receive a 404 response. | testable |

## QA results (computed in code)
- Stories without a testable criterion: none
- Features not traced to a story: none
- Prototype safety problems: none
