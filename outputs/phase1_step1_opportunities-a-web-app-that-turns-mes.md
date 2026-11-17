# Phase 1, step 1: Find opportunities

Founder brief:

```
Idea: A web app that turns messy university lecture notes and slides into exam-ready summaries and practice questions
Founder skills: Python, AI/LLM apps, web development, tutoring STEM students
Budget: $200
Time available: 10 hours/week
Target market: Students
Values: honesty, accessible education, student privacy
```

## 1. Exam‑Ready Summaries & Practice Questions (score 3.6/5)

- Problem: Students have messy lecture notes and slide decks and must spend many hours reorganizing them into concise summaries and creating practice questions for exams.
- Customer: Undergraduate STEM students at universities
- Digital product: Web app where users upload PDFs or slide files; an LLM generates an exam‑focused summary and a set of practice questions aligned to the material.
- Alternatives today: Manual rewriting of notes, General video/lecture summarizers (e.g., InfoCaptor AI), Automatic transcription apps (e.g., Whisperer AI), Flashcard apps like Anki
- Scores: pain 4, founder fit 5, feasibility 3, reach 3, differentiation 3 (model judgement)
- Biggest risk: LLM API costs could exceed the $200 budget if usage scales before a sustainable revenue model is found.

Claims:
- Students spend a lot of time watching lectures and extracting key insights, which they find tedious. [source: https://news.ycombinator.com/item?id=45007478]
- There is demand for tools that automatically transcribe and summarize lecture content. [source: https://news.ycombinator.com/item?id=46025891]
- Existing tools like InfoCaptor AI focus on video summarization and do not produce exam‑ready summaries or practice questions. [source: https://news.ycombinator.com/item?id=45007478]
- Automatic meeting/lecture transcription apps aim to make capture effortless but are not tailored to exam preparation. [source: https://news.ycombinator.com/item?id=46025891]

## 2. Slide‑to‑Flashcard Generator (score 3.6/5)

- Problem: Turning slide bullet points into active‑recall flashcards is time‑consuming for students preparing for exams.
- Customer: University students who receive slide decks for courses
- Digital product: Web app that extracts text from uploaded slide decks and uses an LLM to create Q/A flashcards ready for import into spaced‑repetition tools.
- Alternatives today: Manual flashcard creation, Anki (manual entry), General summarizer tools (InfoCaptor AI), Lecture transcription apps (Whisperer AI)
- Scores: pain 3, founder fit 5, feasibility 4, reach 3, differentiation 3 (model judgement)
- Biggest risk: Accurately generating high‑quality, curriculum‑aligned flashcards may require prompt engineering and iterative testing, increasing development time.

Claims:
- **ASSUMPTION:** Students often receive slide decks that are not directly usable for flashcard study. _(no source)_
- Existing AI note‑taking tools focus on transcription rather than flashcard generation. [source: https://news.ycombinator.com/item?id=46025891]

## 3. AI‑Powered Study Planner with Adaptive Quizzes (score 2.6/5)

- Problem: Students struggle to create effective study schedules and lack personalized practice quizzes that target weak topics.
- Customer: College students seeking structured exam preparation
- Digital product: Web platform that analyses uploaded lecture notes/slides, builds a weekly study plan, and generates adaptive quizzes that focus on identified gaps.
- Alternatives today: Manual study planning (calendars, to‑do lists), Generic study planner apps, Quizlet and similar quiz generators, Lecture summarizers (InfoCaptor AI, Whisperer AI)
- Scores: pain 2, founder fit 5, feasibility 2, reach 2, differentiation 2 (model judgement)
- Biggest risk: Building reliable adaptive quiz logic adds complexity and may exceed the limited budget and weekly time allocation.

Claims:
- **ASSUMPTION:** Students want tools that make exam preparation more efficient, but existing solutions are fragmented. _(no source)_

## Sources retrieved
- [S1] https://news.ycombinator.com/item?id=45007478
- [S2] https://news.ycombinator.com/item?id=46025891
- [S3] https://news.ycombinator.com/item?id=43184362
- [S4] https://news.ycombinator.com/item?id=47759621

Research tools that failed (results may be thinner): reddit_search('how to summarize lecture notes automatically'): HTTPStatusError; reddit_search('best tools for converting slides to study guide'): HTTPStatusError; reddit_search('struggling with messy notes exam preparation'): HTTPStatusError
