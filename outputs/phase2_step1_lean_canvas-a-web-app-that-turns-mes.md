# Phase 2, step 1: Lean Canvas for 'Exam‑Ready Summaries & Practice Questions'

| Box | Content |
|---|---|
| Problem | Students have messy lecture notes and slide decks and must spend many hours reorganizing them into concise, exam‑ready summaries and creating practice questions. |
| Customer segments | Undergraduate STEM students at universities<br>First‑year STEM undergraduates developing note‑taking habits<br>Upper‑classmen preparing for midterms or finals in large lecture courses<br>Students who rely on digital PDFs or slide decks rather than handwritten notes |
| Unique value proposition | AI‑powered web app that turns uploaded lecture PDFs/slides into concise, exam‑focused summaries and practice questions while keeping student data private and affordable. |
| Solution | User uploads PDF/PPT/DOCX of lecture material<br>LLM processes content to generate a short summary aligned with exam objectives<br>LLM creates a set of practice questions covering key concepts<br>User downloads or views results instantly<br>Data is deleted after processing to ensure privacy |
| Channels | Reddit communities (r/college, r/EngineeringStudents, etc.)<br>Discord servers for university courses and study groups<br>University online forums/LMS (Canvas, Blackboard)<br>Twitter/X and Instagram posts targeting student hashtags<br>Word‑of‑mouth referrals from tutoring peers |
| Revenue streams | Freemium model: limited free summaries per month, paid premium for unlimited use<br>Subscription tier (monthly/semester) for unlimited summaries and question sets<br>Pay‑per‑summary credits for occasional users<br>Institutional licensing for university study groups |
| Cost structure | LLM API usage (pay‑as‑you‑go)<br>Cloud hosting and storage<br>Domain and SSL certificate<br>Minimal paid ads on Reddit/Discord<br>Founder time for development and maintenance |
| Key metrics | Number of uploaded files per week<br>Average cost per summary generation<br>Conversion rate from free to paid users<br>Retention rate across exam periods<br>User satisfaction (NPS) |
| Unfair advantage | Founder combines Python/LLM development expertise with hands‑on STEM tutoring experience, enabling finely tuned prompts for accurate exam content and a strong focus on student privacy. |

## Riskiest assumptions (tested in Validate)
1. Students are willing to pay for AI‑generated exam‑ready summaries and practice questions
2. LLM can consistently produce accurate, exam‑relevant summaries and questions from diverse lecture materials
3. LLM API costs can stay within the $200 budget before a sustainable revenue stream is established
4. Students trust a web app with their lecture PDFs and expect strong privacy guarantees
5. There is sufficient demand among STEM undergraduates to achieve viable scale

## Claims
- Students spend a lot of time watching lectures and extracting key insights, which they find tedious. [source: https://news.ycombinator.com/item?id=45007478]
- There is demand for tools that automatically transcribe and summarize lecture content. [source: https://news.ycombinator.com/item?id=46025891]
- Existing tools like InfoCaptor AI focus on video summarization and do not produce exam‑ready summaries or practice questions. [source: https://news.ycombinator.com/item?id=45007478]
- Automatic meeting/lecture transcription apps aim to make capture effortless but are not tailored to exam preparation. [source: https://news.ycombinator.com/item?id=46025891]
- **ASSUMPTION:** Undergraduate STEM students constitute a major portion of university enrollment in the United States. _(no source)_
- **ASSUMPTION:** Students frequently use Reddit and Discord to share study resources and discuss exam preparation. _(no source)_
