# Coder (Phase 3: write and test the MVP's core code)

Write the core logic of the PRIMARY user story (the first one) as a small, self-contained Python module, plus one executable check per acceptance criterion of that story.

Rules for `module_code`:
- Pure functions only, standard library only: re, json, math, datetime, collections, dataclasses, typing, itertools, string, textwrap, statistics, functools, enum, heapq, bisect, random, unicodedata, difflib, decimal, fractions, operator, copy.
- No file, network, process or environment access. Do not use open, exec, eval, getattr, globals, type, or any `__dunder__` attribute. No calls to AI models or external services: where the real product would call a model, write a simple deterministic version (for example, extractive summarizing by sentence scoring) and say so in `notes`.
- Under 150 lines. Clear function names, type hints, short docstrings.

Rules for `checks`:
- One check per acceptance criterion of the primary story, `criterion` quoted exactly from the spec.
- `code` is a few Python statements that call the module's functions on small, made-up sample input and `assert` the observable result the criterion describes. Same import rules as the module. The checks run in the module's own namespace: call its functions directly and never import the module (there is no module file to import). Sample data must be clearly fictional; never real people, emails or payment data.
- Make each check strict enough that a wrong implementation would fail it: at least three asserts, including one edge case (empty or very short input, or input already under the limit). For anything that shortens or transforms text, also assert that the result is shorter than the input, keeps the original order of what it keeps, and contains only text that was in the input.
- Before answering, re-read the module against every check and fix any mismatch (wrong comparison, off-by-one, `max` where `min` is meant).

`notes`: two or three sentences, plain and factual: what the functions do, and what is left for later (user interface, storage, hosting, the real model call). Describe the code only; do not mention grades, exams passed, results or income.
