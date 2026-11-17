# Coder (Phase 3: write and test the MVP's core code)

Write the core logic of EVERY user story in the spec as one small, self-contained Python module (one public function per story, each taking one text argument where the story allows it), plus one executable check per acceptance criterion of every story.

Rules for `module_code`:
- Pure functions only, standard library only: re, json, math, datetime, collections, dataclasses, typing, itertools, string, textwrap, statistics, functools, enum, heapq, bisect, random, unicodedata, difflib, decimal, fractions, operator, copy.
- No file, network, process or environment access. Do not use open, exec, eval, getattr, globals, type, or any `__dunder__` attribute. No calls to AI models or external services: where the real product would call a model, write a simple deterministic version (for example, extractive summarizing by sentence scoring) and say so in `notes`.
- Under 220 lines. Clear function names, type hints, short docstrings.
- The output must be useful on real input, not a template. Build every result from the user's own content: for example, score sentences by how often their key terms (words that are not stopwords) appear in the whole text and keep the most informative ones in their original order; build each practice question from a real key term and the sentence it appears in (a fill-in-the-blank with the term removed, or "What does <term> mean in: <sentence>?"). Never return the same generic line for different items, and never cut a sentence at an arbitrary word count.

Rules for `checks`:
- One check per acceptance criterion of every story, `criterion` quoted exactly from the spec and `story_id` set.
- If a criterion can only be observed with storage, a user interface, hosting, timing or a real model call (for example "the server returns 404" or "appears within 30 seconds"), do not fake it: put it in `deferred` with a one-line reason. Test the pure logic behind it instead when there is some (for example, that processing keeps no copy of the input).
- `code` is a few Python statements that call the module's functions on small, made-up sample input and `assert` the observable result the criterion describes. Same import rules as the module. The checks run in the module's own namespace: call its functions directly and never import the module (there is no module file to import). Sample data must be clearly fictional; never real people, emails or payment data.
- For each function that produces content, one check must show the result depends on the input: two different sample texts give different results, and the result contains key terms from its own input.
- Make each check strict enough that a wrong implementation would fail it: at least three asserts, including one edge case (empty or very short input, or input already under the limit). For anything that shortens or transforms text, also assert that the result is shorter than the input, keeps the original order of what it keeps, and contains only text that was in the input.
- Before answering, re-read the module against every check and fix any mismatch (wrong comparison, off-by-one, `max` where `min` is meant).

`notes`: two or three sentences, plain and factual: what the functions do, and what is left for later (user interface, storage, hosting, the real model call). Describe the code only; do not mention grades, exams passed, results or income.
