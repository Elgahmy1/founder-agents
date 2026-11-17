# Founder Agents

An open-source team of AI agents that takes a founder's brief (idea, skills, budget, time, target market, values) toward a validated digital product. It gathers real sources, labels everything else as an ASSUMPTION, sets evidence targets before testing, and recommends **stop** when the evidence is weak. The founder approves everything that is published, sent, spent or signed, and that rule lives in code (`app/approval.py`).

In the committed demo run (`48fc7649`, an exam-summary app for students), the agents took one idea through all six phases on an open-weight model at $0.00: sourced research, a waitlist demand test (the system recommended PIVOT; the founder overrode it to GO, and the log keeps both), a tested MVP with a user guide, pricing and policy drafts signed by the founder, a store page and launch kit, and a learn gate that recommended **stop** on real launch numbers (0 visits, 0 sign-ups). Three other ideas were stopped earlier on weak evidence, and a crypto-signals idea was refused by the policy screen. You can replay every recorded run without a model at `/replay/<run>` ([demo-run map](docs/demo-run.md), [run metrics](evals/run_metrics.md)).

## Quickstart

```bash
docker compose up
```

Open http://localhost:8000, fill in a founder brief and press **Start Discover**. The run goes through all six phases and stops at every gate for your decision. The app opens at once; the open-weight model (`qwen3:8b`, about 5 GB) downloads in the background the first time. Meanwhile **Recorded runs** replays the committed demo runs read-only, with no model: http://localhost:8000/replay/48fc7649.

Without Docker: install [Ollama](https://ollama.com), `ollama pull qwen3:8b`, then `pip install -r requirements.txt && uvicorn app.main:app`. Terminal version: `python -m app.cli run briefs/study-notes.json`. Smoke tests: `python -m pytest -q` (no model, no network, no keys).

## What works and what is mocked

Every **Working** row has real output from the committed demo runs ([step-to-output map](docs/demo-run.md), [full step-by-step table](docs/status.md)).

| Step | Status |
|---|---|
| Brief intake + policy screen (excluded products, unsafe requests) | **Working** |
| 1 Discover: research from free sources (Hacker News, Stack Exchange, Wikipedia, DuckDuckGo) and scored opportunities | **Working** |
| 1 Discover: market definition and Mom Test interview plan with outreach draft | **Working** |
| Evidence ledger: every claim SOURCED (a retrieved URL) or labelled ASSUMPTION, enforced in code and audited in CI | **Working** |
| 2 Validate: Lean Canvas, landing page with real sign-up form, targets locked by the founder before the test | **Working** |
| 3 Build: MVP spec (user stories, acceptance criteria, hours vs budget), clickable prototype, build gate | **Working** |
| 3 Build: core code for every user story, tested against its acceptance criteria in a sandbox (CI re-runs the checks) | **Working** |
| 3 Build: MVP app at `/mvp/<run>` (each request runs the tested code in the sandbox) and its user guide at `/mvp/<run>/guide` | **Working** |
| 4 Commercial setup: pricing with the core feature always free, terms / privacy / refund DRAFTS signed by the founder | **Working** |
| 5 Launch: store page from the signed prices, launch posts, launch targets locked before launch | **Working** |
| 5 Launch: payment → automatic delivery, refund revokes access, idempotency, reconciliation | **MOCKED** (real logic on mock events; no provider, no money) |
| 6 Operate and learn: results vs locked targets (counted by the app), support reply drafts, learn gate, learning memo | **Working** |
| Gates after every phase (go / repeat / pivot / stop), recommending STOP on weak evidence | **Working** |
| Founder approval queue for everything published, sent, spent or signed, enforced in code | **Working** |
| Decision log (`decision_log.json`): every agent action, required keys, tamper-evident hash chain | **Working** |
| Red-team guard (fake reviews, urgency, income promises, impersonation, money, credentials, prompt injection; English + Arabic), 0 failures | **Working** |
| Replay of recorded runs at `/replay/<run>`, founder export, run metrics, claims audit | **Working** |
| Public hosting (pages are served on the founder's computer); sending outreach and support replies and posting launch posts (the founder does it personally) | **MOCKED** |
| MVP storage, accounts, and acceptance criteria that need them (listed as DEFERRED) | **STUBBED** |

## Architecture

An explicit state machine (`app/orchestrator.py`) moves a run through the six phases and stops wherever only the founder can decide. Each agent (`app/agents/`) has one job and one prompt (`prompts/`) and returns schema-checked JSON from an open-weight model. Every claim passes the evidence ledger (`app/evidence.py`), which keeps a citation only if the source was actually retrieved and supports it. Gates (`app/gates.py`) compute a recommendation from thresholds fixed in advance; the founder decides, and overrides are logged. Details, diagrams and sale to cash: [ARCHITECTURE.md](ARCHITECTURE.md).

## Models and free resources

- Default: `qwen3:8b` (open weights) via [Ollama](https://ollama.com), locally. Any Ollama model works (`MODEL=gpt-oss:20b` in `.env`).
- No GPU: `LLM_PROVIDER=openai` with a free-tier endpoint serving open weights, e.g. Groq's free tier with `openai/gpt-oss-120b` (see `.env.example`; the key stays in your untracked `.env`). When it is rate-limited, calls fall back to the local model and the log records which model answered.
- The committed demo runs used `openai/gpt-oss-120b` on Groq's free tier from a laptop without a GPU.
- Research: Hacker News, Stack Exchange, Wikipedia and DuckDuckGo, with no keys or accounts. If they are unreachable, the run continues and claims are labelled ASSUMPTION.
- No paid service is used or required.

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

Each limit is enforced in code by the guard and the approval queue; [`evals/red_team_report.md`](evals/red_team_report.md) lists the 70 trick requests, 31 product ideas and 13 unsafe texts it was tested on, with 0 failures.

## How the project stays alive after the hackathon

- Maintainers: Mohamed (@Elgahmy1) and contributors; MIT licence.
- Roadmap: [ARCHITECTURE.md](ARCHITECTURE.md#roadmap) (MVP storage in a container sandbox, more SOURCED prices, provider webhooks in the founder's own account, product analytics).
- Quality: every push to `main` runs the smoke tests, the red-team evaluation and the decision-log check in GitHub Actions, on free runners with no keys.
- Community: [CONTRIBUTING.md](CONTRIBUTING.md) (first contributions: guard rules, research tools, agents, translations), [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md), [SECURITY.md](SECURITY.md).
- Funding: it runs on free local models, so there is no hosting bill; grants or sponsorship would pay for maintainer time, never for paywalled features.
