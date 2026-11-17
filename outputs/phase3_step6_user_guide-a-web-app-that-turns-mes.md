# ExamReady AI: user guide (MVP)

Written by the pipeline when the MVP app was built (run `48fc7649`), from the MVP spec, the tested core code (3/3 acceptance checks passed) and a real run of that code in the sandbox. No model wrote this guide.

## What it does today

- **summarize_text** (input: `text`): Create a bullet‑point summary.
- **generate_questions** (input: `summary`): Generate *count* practice questions from a bullet‑point summary.

Product vision (not built yet): Upload lecture PDFs/slides and instantly get concise exam‑ready summaries and practice questions.

## How to use it

1. Open the MVP app at `/mvp/48fc7649` (on this computer; public hosting is MOCKED).
2. Paste your text into the box (up to 20,000 characters).
3. Press **Run**. The result shows one section per step, in this order: `summarize_text`, `generate_questions`.
4. `generate_questions` works on the result of the step before it, not on your raw text.

## Example (real output of this MVP)

Input: the product's own description and user stories, used as sample text.

```text
Upload lecture PDFs/slides and instantly get concise exam‑ready summaries and practice questions. As Student who has lecture PDFs, I want to upload the file and receive a concise summary, so that I can study the key points quickly. As Student who needs practice material, I want to get practice questions derived from the uploaded lecture, so that I can test my understanding before the exam. As Privacy‑concerned student, I want my uploaded file to be deleted after processing, so that my lecture material is not stored on the server.
```

`summarize_text`:

```text
  - Upload lecture PDFs/slides and instantly get concise exam‑ready summaries and practice questions.
  - As Student who has lecture PDFs, I want to upload the file and receive a concise summary, so that I can study the key points quickly.
  - As Student who needs practice material, I want to get practice questions derived from the uploaded lecture, so that I can test my understanding before the exam.
```

`generate_questions`:

```text
  - Explain the concept of Upload lecture PDFs/slides and.
  - Explain the concept of As Student who has.
  - Explain the concept of As Student who needs.
  - Explain the concept of Upload lecture PDFs/slides and.
  - Explain the concept of As Student who has.
```

## What was tested

| Story | Acceptance criterion | Result |
|---|---|---|
| US1 | Given a file is uploaded, when the summary is shown, then it contains at least three bullet‑point key concepts. | PASS |
| US2 | Given the summary generation completes, when the process finishes, then a list of at least five practice questions is displayed. | PASS |
| US2 | Given the questions are shown, when I view them, then each question references a concept mentioned in the summary. | PASS |
| US1 | Given I am on the upload page, when I select a PDF file and click "Generate Summary & Questions", then a summary appears within 30 seconds. | DEFERRED (STUBBED): Timing and UI interaction cannot be verified with pure functions. |
| US3 | Given a file has been processed, when the results page loads, then the server logs indicate the original file has been removed. | DEFERRED (STUBBED): Requires server‑side logging side‑effects, not representable in pure code. |
| US3 | Given the file is deleted, when I attempt to access the original upload endpoint for that file, then I receive a 404 response. | DEFERRED (STUBBED): HTTP response handling depends on web framework and storage, outside pure function scope. |

## What it does not do yet

- Given I am on the upload page, when I select a PDF file and click "Generate Summary & Questions", then a summary appears within 30 seconds. (US1): not built yet, so it is listed as DEFERRED, not claimed.
- Given a file has been processed, when the results page loads, then the server logs indicate the original file has been removed. (US3): not built yet, so it is listed as DEFERRED, not claimed.
- Given the file is deleted, when I attempt to access the original upload endpoint for that file, then I receive a 404 response. (US3): not built yet, so it is listed as DEFERRED, not claimed.
- Out of scope for this MVP: User authentication or account system
- Out of scope for this MVP: Payment processing or subscription management
- Out of scope for this MVP: Analytics dashboard and usage tracking
- Out of scope for this MVP: Bulk or batch uploads
- Out of scope for this MVP: Custom prompt editing by users
- Out of scope for this MVP: Multi‑language support
- Uploading files (PDF, slides), accounts, saving results and public hosting are STUBBED: paste plain text instead.
- The steps are plain, deterministic code, not an AI model: results can be simple, and they are not checked for accuracy.

## Your data

Nothing you paste is stored. Each request runs the code in an isolated sandbox with no file, network or process access, and the page has no accounts, cookies, password or payment fields.

## Who it is for

- US1: as Student who has lecture PDFs, I want to upload the file and receive a concise summary, so that I can study the key points quickly.
- US2: as Student who needs practice material, I want to get practice questions derived from the uploaded lecture, so that I can test my understanding before the exam.
- US3: as Privacy‑concerned student, I want my uploaded file to be deleted after processing, so that my lecture material is not stored on the server.

Tested stories: 2 of 3; acceptance criteria checked: 3, deferred: 3.
