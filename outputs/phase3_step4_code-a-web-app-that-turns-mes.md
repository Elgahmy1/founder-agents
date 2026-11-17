# Phase 3, step 4: MVP core code, tested in a sandbox

Primary user story US1: as Student who has lecture PDFs, I want to upload the file and receive a concise summary, so that I can study the key points quickly.

Written by the coder agent and run by `app/sandbox.py`: static allowlist (pure standard library, no file, network or process access) and a separate isolated Python process with a time limit. Nothing here is published or deployed. User interface, storage, hosting and the real model call are not generated (STUBBED for this step).

**Result: 2/2 acceptance checks passed after one repair.**

| Acceptance criterion | Check | Result |
|---|---|---|
| Given I am on the upload page, when I select a PDF file and click "Generate Summary & Questions", then a summary appears within 30 seconds. | check 1 | PASS |
| Given a file is uploaded, when the summary is shown, then it contains at least three bullet‑point key concepts. | check 2 | PASS |

## Notes

Implemented deterministic extractive summarization that returns up to three bullet‑point sentences from the provided text, and a placeholder question generator. All functions are pure and use only the Python standard library. UI handling, PDF extraction, storage, and real LLM calls are out of scope for this MVP.

## core.py

```python
import re
import datetime
from typing import List

def _split_into_sentences(text: str) -> List[str]:
    """Return a list of sentences extracted from *text*.
    Sentences are split on punctuation followed by whitespace.
    Empty strings are filtered out.
    """
    # Simple regex split; keeps the punctuation with the sentence.
    raw = re.split(r'(?<=[.!?])\s+', text.strip())
    return [s for s in raw if s]

def generate_summary(text: str, max_sentences: int = 3) -> str:
    """Create a bullet‑point summary from *text*.
    The function extracts up to *max_sentences* sentences in their original order
    and prefixes each with "- ". If *text* contains fewer sentences, all are used.
    Returns an empty string when *text* has no sentences.
    """
    sentences = _split_into_sentences(text)
    if not sentences:
        return ""
    selected = sentences[:max_sentences]
    bullet_lines = [f"- {s}" for s in selected]
    return "\n".join(bullet_lines)

def generate_questions(text: str, num_questions: int = 2) -> List[str]:
    """Deterministic placeholder that returns *num_questions* simple questions.
    For each of the first *num_questions* sentences, a generic question is formed.
    This mimics a model call and will be replaced by a real LLM later.
    """
    sentences = _split_into_sentences(text)
    questions = []
    for s in sentences[:num_questions]:
        # Very naive question generation: turn the sentence into a yes/no question.
        q = f"Is it true that {s.rstrip('.!?').lower()}?"
        questions.append(q)
    return questions
```

## Checks

Check 1 (US1): Given I am on the upload page, when I select a PDF file and click "Generate Summary & Questions", then a summary appears within 30 seconds.

```python
sample_text = (
    "First concept explained. "
    "Second idea follows. "
    "Third point is important. "
    "Additional details are given."
)
start = datetime.datetime.now()
summary = generate_summary(sample_text)
elapsed = (datetime.datetime.now() - start).total_seconds()
assert isinstance(summary, str), "Summary should be a string"
assert len(summary) < len(sample_text), "Summary should be shorter than input"
assert elapsed < 0.5, f"Function took too long: {elapsed}s"
assert summary.count('\n') == 2, "Summary should contain exactly three bullet lines"
```

Check 2 (US1): Given a file is uploaded, when the summary is shown, then it contains at least three bullet‑point key concepts.

```python
sample_text = "Alpha. Beta. Gamma. Delta."
summary = generate_summary(sample_text, max_sentences=3)
lines = summary.split('\n')
# At least three bullet points
assert len(lines) >= 3, "Summary must have at least three bullet lines"
# Each line must start with '- '
for line in lines:
    assert line.startswith('- '), f"Line does not start with bullet: {line}"
    content = line[2:]
    assert content in sample_text, "Bullet content must appear in original text"
# Edge case: very short input
short_text = "Only one sentence."
short_summary = generate_summary(short_text)
assert short_summary.startswith('- '), "Even short summary should be bullet formatted"
assert short_summary.strip('- ') == short_text.strip(), "Bullet should contain the original sentence"
```
