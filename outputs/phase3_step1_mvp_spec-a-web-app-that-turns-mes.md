# Phase 3, step 1: MVP spec for 'ExamReady AI'

Upload lecture PDFs/slides and instantly get concise exam‑ready summaries and practice questions.

Build budget: 10 h/week x 4 weeks = 40 h. Estimated: 40 h (model estimate).

## User stories
- **US1** As Student who has lecture PDFs, I want to upload the file and receive a concise summary, so that I can study the key points quickly.
  - [ ] Given I am on the upload page, when I select a PDF file and click "Generate Summary & Questions", then a summary appears within 30 seconds.
  - [ ] Given a file is uploaded, when the summary is shown, then it contains at least three bullet‑point key concepts.
- **US2** As Student who needs practice material, I want to get practice questions derived from the uploaded lecture, so that I can test my understanding before the exam.
  - [ ] Given the summary generation completes, when the process finishes, then a list of at least five practice questions is displayed.
  - [ ] Given the questions are shown, when I view them, then each question references a concept mentioned in the summary.
- **US3** As Privacy‑concerned student, I want my uploaded file to be deleted after processing, so that my lecture material is not stored on the server.
  - [ ] Given a file has been processed, when the results page loads, then the server logs indicate the original file has been removed.
  - [ ] Given the file is deleted, when I attempt to access the original upload endpoint for that file, then I receive a 404 response.

## Must-have features
| Feature | Stories | Hours | Description |
|---|---|---|---|
| File Upload & Processing | US1, US2, US3 | 12 | Frontend upload component and backend endpoint that accept PDF/PPT/DOCX, extract text, and trigger LLM pipelines. |
| Summary Generation | US1 | 8 | LLM prompt chain that produces a concise, exam‑focused summary from extracted lecture text. |
| Practice Question Generation | US2 | 8 | LLM prompt chain that creates at least five relevant practice questions based on the same lecture content. |
| Automatic Data Deletion | US3 | 6 | After processing, the original uploaded file is securely removed and a deletion log is recorded. |
| Result Display & Download | US1, US2 | 6 | Simple results page showing the summary and questions with a button to download them as a PDF. |

## Out of scope for the MVP
- User authentication or account system
- Payment processing or subscription management
- Analytics dashboard and usage tracking
- Bulk or batch uploads
- Custom prompt editing by users
- Multi‑language support

## Tech stack (free, open source)
- Python
- FastAPI
- Streamlit
- HuggingFace Transformers (open‑source LLM)
- GitHub (code repository)
- Render (free tier hosting)

## Risks
- LLM may produce inaccurate or irrelevant summaries/questions from diverse lecture formats.
- Processing large PDFs could exceed free hosting compute limits.
- Student privacy concerns if deletion fails or logs are exposed.
- Open‑source LLM inference cost may still approach the $200 budget if usage spikes.
- Limited adoption without marketing or referral channels.

Code generation in a sandbox is STUBBED: this phase produces the spec, a clickable prototype and acceptance tests.
