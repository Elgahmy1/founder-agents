# Founder Agents

An open-source team of AI agents that takes a founder's brief (idea, skills, budget, time, target market, values) toward a validated digital product. It gathers real sources, labels everything else as an ASSUMPTION, sets evidence targets before testing, and recommends **stop** when the evidence is weak. The founder approves everything that is published, sent, spent or signed, and that rule lives in code (`app/approval.py`).

In the committed demo run (`48fc7649`, an exam-summary app), the agents took one idea through all six phases at $0.00: sourced research, a demand test (0 of 120 sign-ups: PIVOT recommended, overruled to GO by the founder with both logged), a tested MVP with a user guide, signed pricing and policy drafts, a store page, and a learn gate that recommended **stop** on real numbers. Run `a8d5c936` shows the co-founder layer; three others stopped on weak evidence, a crypto idea was refused. Replay any run without a model at `/replay/<run>` ([demo-run map](docs/demo-run.md)).

CI recomputes these on every push: run metrics from `decision_log.json` ([run_metrics.md](evals/run_metrics.md)), cited URLs must have been retrieved ([claims_audit.md](evals/claims_audit.md)), outputs must agree across phases ([consistency_audit.md](evals/consistency_audit.md)), and the guard must refuse 102 trick requests (English, Egyptian Arabic, Arabizi) and allow 27 normal ones ([red_team_report.md](evals/red_team_report.md)).

## Quickstart

```bash
docker compose up
```

Open http://localhost:8000, fill in a founder brief and press **Start Discover**. The run stops at every gate for your decision. The app opens at once while the open-weight model (`qwen3:8b`, ~5 GB) downloads; meanwhile replay a recorded run: http://localhost:8000/replay/48fc7649.

Without Docker: install [Ollama](https://ollama.com), `ollama pull qwen3:8b`, then `pip install -r requirements.txt && uvicorn app.main:app`. Terminal version: `python -m app.cli run briefs/study-notes.json`. Tests: `python -m pytest -q` (no keys).

## What works and what is mocked

Rows marked **Working** with no note have real output in the committed demo runs ([map](docs/demo-run.md), [full table](docs/status.md)).

| Step | Status |
|---|---|
| Brief intake + policy screen (excluded products, unsafe requests) | **Working** |
| 1 Discover: research from free sources (Hacker News, Stack Exchange, Wikipedia, DuckDuckGo) and scored opportunities | **Working** |
| 1 Discover: market definition and Mom Test interview plan with outreach draft | **Working** |
| 1 Discover: co-founder layer: area check (local fit, resources, competitors; UNKNOWN in code without a source about the place), an honest verdict capped by the gate with the killer risk, fixes, cheapest tests and a launch window, and a funding scout (grants, accelerators, sponsors; fit % computed in code, unverified names flagged, no loans) | **Working** (run `a8d5c936`) |
| Evidence ledger: every claim SOURCED (a retrieved URL) or labelled ASSUMPTION, enforced in code and audited in CI | **Working** |
| 2 Validate: Lean Canvas, landing page with real sign-up form, targets locked by the founder before the test | **Working** |
| 2 Validate: real interviews (notes, or an Arabic/English recording via open-weight Whisper) analysed by a Mom Test agent; quotes checked against the transcript in code; counts feed the demand gate | **Working** (added after the demo run; audio STUBBED with local Ollama) |
| 3 Build: MVP spec (user stories, acceptance criteria, hours vs budget), clickable prototype, build gate | **Working** |
| 3 Build: core code for every user story, tested against its acceptance criteria in a sandbox (CI re-runs the checks) | **Working** |
| 3 Build: MVP app at `/mvp/<run>` (each request runs the tested code in the sandbox) and its user guide at `/mvp/<run>/guide` | **Working** |
| 4 Commercial setup: pricing with the core feature always free, terms / privacy / refund DRAFTS signed by the founder | **Working** |
| 5 Launch: store page from the signed prices, launch posts, launch targets locked before launch | **Working** |
| 5 Launch: payment → automatic delivery, refund revokes access, idempotency, reconciliation | **MOCKED** (real logic on mock events; no provider, no money) |
| 6 Operate and learn: results vs locked targets (counted by the app), support reply drafts, learn gate, learning memo | **Working** |
| Gates after every phase (go / repeat / pivot / stop), recommending STOP on weak evidence; overruling a recommendation needs a written reason, logged | **Working** |
| Founder-specific advice: a critic in code sends back stock advice, money-taking suggestions and drafts that ignore the budget, hours, skills or market; the killer risk, suggested changes and interview objections are carried into the Lean Canvas and MVP spec, which must answer each one (checked in code) | **Working** |
| Founder approval queue for everything published, sent, spent or signed, enforced in code | **Working** |
| Decision log (`decision_log.json`): every agent action, required keys, tamper-evident hash chain | **Working** |
| Red-team guard (fake reviews, urgency, income promises, impersonation, money, credentials, prompt injection; English + Arabic), 0 failures | **Working** |
| Replay of recorded runs at `/replay/<run>`, founder export, run metrics, claims audit | **Working** |
| Public hosting (pages are served on the founder's computer); sending outreach and support replies and posting launch posts (the founder does it personally) | **MOCKED** |
| MVP storage, accounts, and acceptance criteria that need them (listed as DEFERRED) | **STUBBED** |

## Architecture

A state machine (`app/orchestrator.py`) moves a run through six phases and stops wherever only the founder can decide. Each agent (`app/agents/`) has one job and one prompt and returns schema-checked JSON. The evidence ledger keeps a citation only if the source was retrieved and supports it; gates compute a recommendation from thresholds fixed in advance, and the founder decides. Details: [ARCHITECTURE.md](ARCHITECTURE.md).

## Models and free resources

- Default: `qwen3:8b` (open weights) via [Ollama](https://ollama.com), locally. Any Ollama model works (`MODEL=gpt-oss:20b` in `.env`).
- No GPU: `LLM_PROVIDER=openai` with a free tier serving open weights, e.g. Groq with `openai/gpt-oss-120b` (used for the committed demo runs; key in your untracked `.env`). A used-up limit falls back to the local model; the log names the model.
- Research: Hacker News, Stack Exchange, Wikipedia and DuckDuckGo, no keys; off-topic results are dropped, and if sources are unreachable claims are labelled ASSUMPTION.
- No paid service is needed.

## Cost per run

**About $0.00 per run** (open-weight model, local or free tier). The demo run (`48fc7649`) used ~52k tokens in 19 model calls across all six phases. Generating the Phase 3 core code costs 1-2 more calls (~10k tokens, ~5k per repair); the MVP app and its user guide need no model call. The second run used ~33k tokens in 9 calls before it stopped. Per-call tokens are in `decision_log.json`, per-run totals in [`evals/run_metrics.md`](evals/run_metrics.md).

## Demo video

[Watch the demo (about 2 minutes, Google Drive)](https://drive.google.com/file/d/1nmll2xgWQJ5ui48mlx0c92nQQqpJg0Ck/view?usp=sharing): the real app running the committed demo run through all six phases and gates, the working MVP app, the second and third runs, and a crypto-signals idea stopped by the policy screen.

## What our system will NOT do

- Promise income or guarantee success.
- Write fake reviews, testimonials, sign-ups, traction numbers or countdown timers.
- Pose as the founder, a customer or another brand.
- Hold, move, charge or refund money, create accounts, or store passwords or card numbers. Payments are mocked.
- Publish, send, spend or sign anything without the founder's explicit approval.
- Help with physical goods, financial, investment or crypto products, or health or legal advice products.
- Hide core features behind a paywall.
- Spin weak results: targets are set before the test, and the system recommends stop when they are missed.

Each limit is enforced in code by the guard and the approval queue, and tested in [`evals/red_team_report.md`](evals/red_team_report.md) (0 failures).

## How the project stays alive after the hackathon

- Maintainers: Mohamed (@Elgahmy1) and contributors; MIT licence.
- Roadmap: [ARCHITECTURE.md](ARCHITECTURE.md#roadmap).
- Quality: every push to `main` runs the smoke tests, the red-team evaluation and the decision-log check in GitHub Actions, on free runners with no keys.
- Community: [CONTRIBUTING.md](CONTRIBUTING.md) (first contributions: guard rules, research tools, agents, translations), [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md), [SECURITY.md](SECURITY.md).
- Funding: it runs on free local models, so there is no hosting bill; grants or sponsorship would pay for maintainer time, never for paywalled features.
