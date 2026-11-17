# Phase 3, step 4: MVP core code for every user story, tested in a sandbox

- US1: as Student who has lecture PDFs, I want to upload the file and receive a concise summary, so that I can study the key points quickly.
- US2: as Student who needs practice material, I want to get practice questions derived from the uploaded lecture, so that I can test my understanding before the exam.
- US3: as Privacy‑concerned student, I want my uploaded file to be deleted after processing, so that my lecture material is not stored on the server.

Stories with at least one executable check: 2 of 3 (US1, US2). Acceptance criteria: 6 in the spec, 3 checked in the sandbox, 3 deferred because they need storage, a user interface or hosting.

Written by the coder agent and run by `app/sandbox.py`: static allowlist (pure standard library, no file, network or process access) and a separate isolated Python process with a time limit. Nothing here is published or deployed. The founder can wrap passing code in a working web app (phase3_step5_mvp_app); storage, accounts and public hosting are not generated.

**Result: 3/3 acceptance checks passed.**

| Story | Acceptance criterion | Check | Result |
|---|---|---|---|
| US1 | Given a file is uploaded, when the summary is shown, then it contains at least three bullet‑point key concepts. | check 1 | PASS |
| US2 | Given the summary generation completes, when the process finishes, then a list of at least five practice questions is displayed. | check 2 | PASS |
| US2 | Given the questions are shown, when I view them, then each question references a concept mentioned in the summary. | check 3 | PASS |
| US1 | Given I am on the upload page, when I select a PDF file and click "Generate Summary & Questions", then a summary appears within 30 seconds. | - | DEFERRED (STUBBED): no executable check was written for it (needs a user interface, storage, hosting or a real model call); listed by the orchestrator, not by the coder |
| US3 | Given a file has been processed, when the results page loads, then the server logs indicate the original file has been removed. | - | DEFERRED (STUBBED): no executable check was written for it (needs a user interface, storage, hosting or a real model call); listed by the orchestrator, not by the coder |
| US3 | Given the file is deleted, when I attempt to access the original upload endpoint for that file, then I receive a 404 response. | - | DEFERRED (STUBBED): no executable check was written for it (needs a user interface, storage, hosting or a real model call); listed by the orchestrator, not by the coder |

## Notes

Implemented deterministic summary and question generation using sentence scoring and term extraction. UI, file handling, storage, and real model calls are out of scope.

## core.py

```python
import re
from collections import Counter
from typing import List

_STOPWORDS = {
    "the", "and", "to", "of", "a", "in", "that", "is", "it", "for",
    "on", "with", "as", "was", "but", "be", "by", "or", "not", "are",
    "at", "from", "this", "have", "has", "had", "they", "you", "we",
    "their", "which", "will", "can", "all", "one", "about", "more", "so",
    "if", "when", "who", "what", "there", "been", "into", "out", "up",
    "down", "over", "under", "again", "than", "then", "them", "its", "my"
}

def _split_sentences(text: str) -> List[str]:
    """Split *text* into sentences using punctuation heuristics."""
    sentences = re.split(r"(?<=[.!?])\s+", text.strip())
    return [s.strip() for s in sentences if s]

def _term_frequencies(text: str) -> Counter:
    """Return a Counter of non‑stopword alphabetic terms in *text* (case‑insensitive)."""
    words = re.findall(r"[A-Za-z]+", text.lower())
    terms = [w for w in words if w not in _STOPWORDS]
    return Counter(terms)

def generate_summary(text: str, max_sentences: int = 5) -> List[str]:
    """Return up to *max_sentences* bullet‑point sentences that best represent *text*.
    Sentences are scored by the sum of frequencies of their non‑stopword terms.
    The original order of the selected sentences is preserved.
    """
    if not text:
        return []
    sentences = _split_sentences(text)
    if not sentences:
        return []
    freqs = _term_frequencies(text)
    scored = []
    for idx, s in enumerate(sentences):
        terms = [w for w in re.findall(r"[A-Za-z]+", s.lower()) if w not in _STOPWORDS]
        score = sum(freqs[t] for t in terms)
        scored.append((score, idx, s))
    scored.sort(key=lambda x: (-x[0], x[1]))
    top_idxs = sorted(idx for _, idx, _ in scored[:max_sentences])
    selected = [sentences[i] for i in top_idxs]
    return ["- " + s for s in selected]

def generate_questions(text: str, num: int = 5) -> List[str]:
    """Create *num* fill‑in‑the‑blank style questions from *text*.
    Each question is of the form:
    "What does <term> refer to in the sentence: \"<sentence>\"?"
    """
    if not text:
        return []
    summary = generate_summary(text, max_sentences=5)
    freqs = _term_frequencies(text)
    candidates = [t for t, _ in freqs.most_common() if t not in _STOPWORDS]
    used = set()
    questions = []
    for term in candidates:
        if term in used:
            continue
        sentence = next((s for s in summary if term in re.findall(r"[A-Za-z]+", s.lower())), None)
        if not sentence:
            continue
        clean_sentence = sentence.lstrip("- ")
        q = f"What does {term} refer to in the sentence: \"{clean_sentence}\"?"
        questions.append(q)
        used.add(term)
        if len(questions) >= num:
            break
    return questions
```

## Checks

Check 1 (US1): Given a file is uploaded, when the summary is shown, then it contains at least three bullet‑point key concepts.

```python
sample = "Artificial intelligence is a field of computer science. It studies how to make machines think. AI uses algorithms and data. Applications include vision, language, and robotics. The future of AI is promising."
summary = generate_summary(sample, max_sentences=5)
assert isinstance(summary, list)
assert len(summary) >= 3
assert all(s.startswith('- ') for s in summary)
assert any('intelligence' in s.lower() for s in summary)
```

Check 2 (US2): Given the summary generation completes, when the process finishes, then a list of at least five practice questions is displayed.

```python
sample = "Artificial intelligence is a field of computer science. It studies how to make machines think. AI uses algorithms and data. Applications include vision, language, and robotics. The future of AI is promising."
questions = generate_questions(sample, num=5)
assert isinstance(questions, list)
assert len(questions) >= 5
assert all('?' in q for q in questions)
```

Check 3 (US2): Given the questions are shown, when I view them, then each question references a concept mentioned in the summary.

```python
sample = "Artificial intelligence is a field of computer science. It studies how to make machines think. AI uses algorithms and data. Applications include vision, language, and robotics. The future of AI is promising."
summary = generate_summary(sample, max_sentences=5)
questions = generate_questions(sample, num=5)
terms_seen = set()
for q in questions:
    m = re.search(r"What does (\w+) refer", q)
    assert m
    term = m.group(1).lower()
    assert term not in _STOPWORDS
    assert term not in terms_seen
    terms_seen.add(term)
    assert any(term in re.findall(r"[A-Za-z]+", s.lower()) for s in summary)
assert len(terms_seen) == len(questions)
```
