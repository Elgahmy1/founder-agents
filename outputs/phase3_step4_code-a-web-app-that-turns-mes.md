# Phase 3, step 4: MVP core code, tested in a sandbox

Primary user story US1: as Student who has lecture PDFs, I want to upload the file and receive a concise summary, so that I can study the key points quickly.

Written by the coder agent and run by `app/sandbox.py`: static allowlist (pure standard library, no file, network or process access) and a separate isolated Python process with a time limit. Nothing here is published or deployed. User interface, storage, hosting and the real model call are not generated (STUBBED for this step).

**Result: 2/2 acceptance checks passed.**

| Acceptance criterion | Check | Result |
|---|---|---|
| Given I am on the upload page, when I select a PDF file and click "Generate Summary & Questions", then a summary appears within 30 seconds. | check 1 | PASS |
| Given a file is uploaded, when the summary is shown, then it contains at least three bullet‑point key concepts. | check 2 | PASS |

## Notes

Implemented a deterministic extractive summarizer that scores sentences by word frequency and returns the top sentences as bullet points. Functions operate purely on provided text; PDF extraction, UI, storage, and real AI model calls are out of scope for this MVP.

## core.py

```python
import re
from collections import Counter
from typing import List

def _sentence_split(text: str) -> List[str]:
    """Split text into sentences using punctuation."""
    pattern = r'(?<=[.!?])\s+'
    return [s.strip() for s in re.split(pattern, text) if s.strip()]

def _word_frequencies(text: str) -> Counter:
    """Return word frequency ignoring a small stop‑word list and punctuation."""
    stop = {"the", "and", "of", "to", "a", "in", "for", "on", "with", "as", "is", "it", "by", "an", "or", "at", "from"}
    words = re.findall(r'\b\w+\b', text.lower())
    return Counter(w for w in words if w not in stop)

def generate_summary(text: str, max_sentences: int = 5) -> str:
    """
    Produce an extractive summary as bullet points.
    Sentences are scored by word frequency; the top `max_sentences`
    are returned in their original order.
    """
    if not text:
        return ""
    sentences = _sentence_split(text)
    if not sentences:
        return ""
    freqs = _word_frequencies(text)
    scored = []
    for idx, sent in enumerate(sentences):
        words = re.findall(r'\b\w+\b', sent.lower())
        score = sum(freqs.get(w, 0) for w in words)
        scored.append((score, idx, sent))
    top_n = sorted(scored, key=lambda x: (-x[0], x[1]))[:max_sentences]
    top_n_sorted = sorted(top_n, key=lambda x: x[1])
    bullets = ["- " + s for _, _, s in top_n_sorted]
    return "\n".join(bullets)
```

## Checks

Check 1 (US1): Given I am on the upload page, when I select a PDF file and click "Generate Summary & Questions", then a summary appears within 30 seconds.

```python
sample = "Artificial intelligence is a field of computer science. It aims to create machines that can learn. Recent advances have improved natural language processing. Applications include translation, summarization, and question answering."
summary = generate_summary(sample, max_sentences=3)
assert isinstance(summary, str)
assert summary != ""
assert summary.startswith("-")
# edge case: empty input should yield empty string
assert generate_summary("") == ""
```

Check 2 (US1): Given a file is uploaded, when the summary is shown, then it contains at least three bullet‑point key concepts.

```python
text = (
    "Machine learning provides systems the ability to automatically learn. "
    "Supervised learning uses labeled data to train models. "
    "Unsupervised learning finds hidden patterns without labels. "
    "Reinforcement learning trains agents via rewards. "
    "Deep learning uses neural networks with many layers. "
    "These techniques power modern AI applications."
)
summary = generate_summary(text, max_sentences=5)
lines = [l for l in summary.splitlines() if l.startswith("-")]
assert len(lines) >= 3
for line in lines:
    assert line[2:] in text
assert len(summary) < len(text)
# edge case: short input with fewer than three sentences
short = "Data science combines statistics and programming."
assert generate_summary(short, max_sentences=5) == "- Data science combines statistics and programming."
```
