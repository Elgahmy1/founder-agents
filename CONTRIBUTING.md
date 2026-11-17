# Contributing

Founder Agents is MIT licensed and runs on free, open-weight models. Contributions of every size are welcome.

## Set up

```bash
docker compose up            # app on http://localhost:8000 with a local model
# or, without Docker
pip install -r requirements.txt
python -m pytest -q tests    # no model or network needed
```

## Good first contributions

- **Guard rules:** add a phrasing the guard misses to `evals/red_team_prompts.json` (`must_refuse` or `must_allow`), then a rule in `app/guard.py`. `tests/test_red_team.py` picks it up automatically.
- **Research tools:** a free, key-less source in `app/research.py` returning `Doc` objects. Text from it is sanitized and treated as evidence only.
- **Agents for phases 4-6 and phase 3 code generation:** one file in `app/agents/`, one prompt in `prompts/`, schema-checked output, and a step in `app/orchestrator.py`. See the Roadmap in [ARCHITECTURE.md](ARCHITECTURE.md#roadmap).
- **Translations:** UI strings and guard rules (Arabic rules exist in `app/guard.py`).

## Rules every change keeps

- Nothing is published, sent, spent or signed without an approval item the founder approved (`app/approval.py`).
- Claims without a retrieved source are labelled ASSUMPTION; gates use thresholds fixed before results.
- No paid service may be required; mocked or stubbed parts are labelled MOCKED or STUBBED.
- Never commit keys; use `.env` (untracked) and keep `.env.example` to placeholders.
- No fake reviews, sign-ups, urgency, income promises or impersonation, in code, prompts or tests outside `tests/` and `evals/`.

## Pull requests

Keep them small, add or update a test, and run `python -m pytest -q tests` before opening one. Live red-team check with a model: `python evals/run_red_team.py`.
