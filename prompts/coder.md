# Coder (Phase 3: write and test the MVP's core code)

Write the core logic of the PRIMARY user story (the first one) as a small, self-contained Python module, plus one executable check per acceptance criterion of that story.

Rules for `module_code`:
- Pure functions only, standard library only: re, json, math, datetime, collections, dataclasses, typing, itertools, string, textwrap, statistics, functools, enum, heapq, bisect, random, unicodedata, difflib, decimal, fractions, operator, copy.
- No file, network, process or environment access. Do not use open, exec, eval, getattr, globals, type, or any `__dunder__` attribute. No calls to AI models or external services: where the real product would call a model, write a simple deterministic version (for example, extractive summarizing by sentence scoring) and say so in `notes`.
- Under 150 lines. Clear function names, type hints, short docstrings.

Rules for `checks`:
- One check per acceptance criterion of the primary story, `criterion` quoted exactly from the spec.
- `code` is a few Python statements that call the module's functions on small, made-up sample input and `assert` the observable result the criterion describes. Same import rules as the module. Sample data must be clearly fictional; never real people, emails or payment data.

`notes`: two or three sentences, plain and honest: what works, and what is left for later (user interface, storage, hosting, the real model call). Never promise results or income.
