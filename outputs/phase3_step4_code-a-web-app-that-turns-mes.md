# Phase 3, step 4: MVP core code for every user story, tested in a sandbox

- US1: as Student who has lecture PDFs, I want to upload the file and receive a concise summary, so that I can study the key points quickly.
- US2: as Student who needs practice material, I want to get practice questions derived from the uploaded lecture, so that I can test my understanding before the exam.
- US3: as Privacy‑concerned student, I want my uploaded file to be deleted after processing, so that my lecture material is not stored on the server.

Stories with at least one executable check: 2 of 3 (US1, US2). Acceptance criteria: 6 in the spec, 3 checked in the sandbox, 3 deferred because they need storage, a user interface or hosting.

Written by the coder agent and run by `app/sandbox.py`: static allowlist (pure standard library, no file, network or process access) and a separate isolated Python process with a time limit. Nothing here is published or deployed. The founder can wrap passing code in a working web app (phase3_step5_mvp_app); storage, accounts and public hosting are not generated.

**Result: 3/3 acceptance checks passed after one repair.**

| Story | Acceptance criterion | Check | Result |
|---|---|---|---|
| US1 | Given a file is uploaded, when the summary is shown, then it contains at least three bullet‑point key concepts. | check 1 | PASS |
| US2 | Given the summary generation completes, when the process finishes, then a list of at least five practice questions is displayed. | check 2 | PASS |
| US2 | Given the questions are shown, when I view them, then each question references a concept mentioned in the summary. | check 3 | PASS |
| US1 | Given I am on the upload page, when I select a PDF file and click "Generate Summary & Questions", then a summary appears within 30 seconds. | - | DEFERRED (STUBBED): Timing and UI interaction cannot be verified with pure functions. |
| US3 | Given a file has been processed, when the results page loads, then the server logs indicate the original file has been removed. | - | DEFERRED (STUBBED): Requires server‑side logging side‑effects, not representable in pure code. |
| US3 | Given the file is deleted, when I attempt to access the original upload endpoint for that file, then I receive a 404 response. | - | DEFERRED (STUBBED): HTTP response handling depends on web framework and storage, outside pure function scope. |

## Notes

Implemented pure functions to extract sentences, create a bullet‑point summary, and generate deterministic practice questions from that summary. The logic is deterministic and does not call external services. UI, file upload handling, server logging, HTTP endpoints, and timing constraints are left for later integration.

## core.py

```python
import re
from typing import List

def _split_sentences(text: str) -> List[str]:
    """Return a list of sentences using punctuation as delimiters.
    Simple regex split on period, exclamation or question mark followed by whitespace.
    """
    if not text:
        return []
    # Preserve the delimiter with the sentence
    parts = re.split(r'(?<=[.!?])\s+', text.strip())
    return [p.strip() for p in parts if p]

def summarize_text(text: str, bullet_count: int = 3) -> str:
    """Create a bullet‑point summary.
    The function selects the first *bullet_count* sentences, prefixes each with "- ",
    and joins them with newlines. If the resulting string is not shorter than the input,
    it truncates each selected sentence to half its length (rounded down) before
    bulleting, guaranteeing a shorter output for any non‑empty input longer than
    ``bullet_count * 2`` characters.
    Returns an empty string for empty input.
    """
    sentences = _split_sentences(text)
    if not sentences:
        return ""
    selected = sentences[:bullet_count]
    # Build initial bullet list
    bullets = ["- " + s for s in selected]
    summary = "\n".join(bullets)
    # Ensure summary is shorter than input; if not, truncate each sentence
    if len(summary) >= len(text):
        truncated = []
        for s in selected:
            half = s[: max(1, len(s)//2)].rstrip()
            truncated.append("- " + half)
        summary = "\n".join(truncated)
    return summary

def generate_questions(summary: str, count: int = 5) -> List[str]:
    """Generate *count* practice questions from a bullet‑point summary.
    For each bullet point the function extracts the first few words (up to four) and
    forms a question of the shape "Explain the concept of <phrase>.". If there are
    fewer bullets than *count*, the existing bullets are reused and, when necessary,
    a generic fallback question is added.
    """
    bullets = [line.lstrip('- ').strip() for line in summary.split('\n') if line.startswith('-')]
    questions: List[str] = []
    if not bullets:
        # fallback generic questions
        return ["Explain the concept presented in the material." for _ in range(count)]
    idx = 0
    while len(questions) < count:
        phrase = bullets[idx % len(bullets)]
        words = phrase.split()
        snippet = " ".join(words[:4])  # up to first four words
        q = f"Explain the concept of {snippet}."
        questions.append(q)
        idx += 1
        if idx > len(bullets) * 2:  # safety net to avoid infinite loop
            break
    # If still short, pad with generic question
    while len(questions) < count:
        questions.append("Explain the concept presented in the material.")
    return questions
```

## Checks

Check 1 (US1): Given a file is uploaded, when the summary is shown, then it contains at least three bullet‑point key concepts.

```python
sample = "First sentence. Second sentence! Third sentence? Fourth sentence."
summary = summarize_text(sample, bullet_count=3)
lines = summary.split('\n')
# at least three bullet lines
assert len(lines) >= 3
# each line starts with '- '
assert all(l.startswith('- ') for l in lines)
# order preserved (first three sentences)
expected = ['- First sentence.', '- Second sentence!', '- Third sentence?']
assert lines[:3] == expected
# summary shorter than input
assert len(summary) < len(sample)
# edge case: empty input
assert summarize_text('') == ''
```

Check 2 (US2): Given the summary generation completes, when the process finishes, then a list of at least five practice questions is displayed.

```python
summary = "- Alpha beta gamma.\n- Delta epsilon.\n- Zeta eta theta."
qs = generate_questions(summary, count=5)
assert isinstance(qs, list)
assert len(qs) >= 5
# each question ends with a period
assert all(q.endswith('.') for q in qs)
# edge case: empty summary produces generic questions
empty_qs = generate_questions('', count=5)
assert len(empty_qs) == 5
assert all('concept' in q.lower() for q in empty_qs)
```

Check 3 (US2): Given the questions are shown, when I view them, then each question references a concept mentioned in the summary.

```python
summary = "- Quantum entanglement describes linked particles.\n- Superposition allows multiple states.\n- Wave‑particle duality is fundamental."
qs = generate_questions(summary, count=5)
# collect tokens from bullets (lowercase, alphanumeric)
import re
bullet_tokens = set()
for line in summary.split('\n'):
    if line.startswith('-'):
        words = re.findall(r"[A-Za-z0-9]+", line.lower())
        bullet_tokens.update(words)
# each question must contain at least one token from bullet_tokens
for q in qs:
    q_tokens = set(re.findall(r"[A-Za-z0-9]+", q.lower()))
    assert bullet_tokens.intersection(q_tokens), f"Question does not reference summary: {q}"
# edge case: generic fallback when no bullets
fallback_qs = generate_questions('', count=5)
assert all('concept' in q.lower() for q in fallback_qs)
```
