# Founder Agents

An open-source team of AI agents that takes a founder's brief (idea, skills, budget, time, target market, values) toward a validated digital product. It gathers real sources, labels everything else as an ASSUMPTION, sets evidence targets before testing, and recommends **stop** when the evidence is weak. The founder approves everything that is published, sent, spent or signed, and that rule lives in code (`app/approval.py`).

## Quickstart

```bash
docker compose up
```

Then open http://localhost:8000, fill in a founder brief and press **Start Discover**. The run goes through all six phases (Discover → Validate → Build → Commercial setup → Launch → Operate and learn) and stops at every gate for your decision. The first start downloads the open-weight model (about 5 GB for `qwen3:8b`), so it takes a few minutes once.

Without Docker: install [Ollama](https://ollama.com), run `ollama pull qwen3:8b`, then `pip install -r requirements.txt && uvicorn app.main:app`. A terminal version is available with `python -m app.cli run briefs/study-notes.json`.

## What works and what is mocked

Every **Working** row below has real output from the committed demo runs: [docs/demo-run.md](docs/demo-run.md) maps each step to its file in `outputs/` and its gate decision (a full six-phase run, plus a second idea stopped after validation).

| Step | Status |
|---|---|
| Founder brief intake + policy screen (excluded products, unsafe requests) | **Working** |
| Phase 1 Discover: research from free sources (Hacker News, Stack Exchange, Wikipedia, DuckDuckGo, founder URLs), mixed so no single source fills the budget | **Working** |
| Phase 1 Discover: find and score opportunities | **Working** |
| Phase 1 Discover: define the market | **Working** |
| Phase 1 Discover: Mom Test interview plan + outreach draft | **Working** |
| Sending the outreach message | **MOCKED** (approved drafts are for the founder to send personally) |
| Evidence ledger: claims SOURCED or labelled ASSUMPTION, enforced in code | **Working** |
| Phase 1 evidence gate (go / repeat / pivot / stop) + founder decision | **Working** |
| Phase 2 Validate: Lean Canvas | **Working** |
| Phase 2 Validate: landing page copy, safe template, guard scrubbing | **Working** |
| Landing page publishing, after founder approval | **Working** locally at `/lp/<run>`; public hosting **MOCKED** |
| Waitlist sign-ups counted from real form submissions | **Working** |
| Demand targets proposed and locked by the founder before the test | **Working** |
| Phase 2 demand gate (go / repeat / pivot / stop) + founder decision | **Working** |
| Approval queue (publish / send / spend / sign) | **Working** |
| Decision log with required keys + tamper-evident hash chain | **Working** |
| Red-team guard (fake reviews, urgency, income promises, impersonation, money, credentials, prompt injection; English + Arabic) | **Working** |
| Red-team evaluation: 70 trick requests, 31 product ideas, 13 generated texts; report in [`evals/red_team_report.md`](evals/red_team_report.md), 0 failures | **Working** |
| Phase 3 Build: MVP spec (user stories, acceptance criteria, scoped features with hour estimates) | **Working** |
| Phase 3 Build: clickable prototype from a safe template, published locally after founder approval | **Working** |
| Phase 3 Build: acceptance tests + build gate (scope vs founder hours, traceability, testability, safety) | **Working** |
| Phase 3 Build: coder agent writes the primary user story's core code plus one check per acceptance criterion; the sandbox (static allowlist + isolated process, no file/network/process access) runs them, with one repair attempt | **Working** |
| Phase 3 Build: full application code (user interface, storage, hosting) and deployment | **STUBBED** |
| Phase 4 Commercial setup: tiered pricing with the core feature always free; comparable prices SOURCED or labelled ASSUMPTION | **Working** |
| Phase 4 Commercial setup: terms, privacy and refund policy DRAFTS, each signed off by the founder; commercial gate | **Working** |
| Phase 5 Launch: store page rendered from the founder-approved prices, launch post drafts per channel, launch targets locked before launch, launch gate | **Working** |
| Phase 5 Launch: public hosting, posting to channels, checkout | **MOCKED** (founder posts personally; store served locally; no checkout) |
| Phase 5 Launch: payment → delivery, refunds, idempotency, reconciliation | **MOCKED** (real logic runs on mock events inside the launch gate; no provider) |
| Phase 6 Operate and learn: launch results vs the targets locked before launch (sign-ups counted by the app), support reply drafts for real feedback, learn gate (persevere / repeat / pivot / stop), learning memo | **Working** |
| Phase 6: sending support replies; usage analytics | **MOCKED** (founder sends replies personally and enters store visits from their own analytics) |
| Founder export: the whole run (brief, gates, decisions, approvals, decision log, outputs) as one Markdown file, no model call | **Working** |

## Architecture

An explicit state machine (`app/orchestrator.py`) moves a run through the six phases and stops wherever only the founder can decide. Each agent (`app/agents/`) has one job and one prompt (`prompts/`), and returns schema-checked JSON from a local open-weight model. Every claim passes through the evidence ledger (`app/evidence.py`), which keeps a citation only if the source was actually retrieved and mentions the claim. Gates (`app/gates.py`) compute a recommendation from thresholds fixed in advance, and the founder makes the final call, with any override logged. Full design, including sale to cash: [ARCHITECTURE.md](ARCHITECTURE.md).

## Models and free resources

- Default model: `qwen3:8b` (open weights) via [Ollama](https://ollama.com), running locally. Set `MODEL=gpt-oss:20b` (or any Ollama model) in `.env` to switch.
- The committed demo run (`outputs/`, `decision_log.json`) used `openai/gpt-oss-120b` (open weights) on Groq's free tier, from a laptop without a GPU. Every model call in the log names the model it used.
- Research: Hacker News Algolia API, Stack Exchange API, Wikipedia API, DuckDuckGo HTML results, interleaved so no single source dominates. No keys, no accounts.
- If the free tier stays rate-limited, calls fall back to the local model (`FALLBACK_MODEL` in `.env.example`); the log records which model answered.
- No GPU? Set `LLM_PROVIDER=openai` with a free-tier OpenAI-compatible endpoint that serves open-weight models (for example Groq's free tier with `openai/gpt-oss-120b`); see `.env.example`. The key stays in your untracked `.env`.
- No paid service is used or required. If research sites are unreachable, the run continues and every claim is labelled ASSUMPTION.

## Cost per run

About $0.00 per run (open-weight model, local via Ollama or Groq free tier). The demo run used ~50k tokens in 18 model calls on `openai/gpt-oss-120b` via the Groq free tier across all six phases, including one redraft each of the MVP spec, pricing and policies; the optional Phase 3 core-code step added ~16k tokens in 5 calls (three generations and two repairs). The second run used ~33k tokens in 9 calls before it stopped. Token counts per call are in `decision_log.json`, and the app shows the token count of each run.

## Demo video

[Watch the demo (1:57, Google Drive)](https://drive.google.com/file/d/1_zaOqoK2jAYvnqTKnCU149WhFfONbSl3/view?usp=sharing): a captioned screen recording of the real app. It walks the committed demo run through all six phases and their gates, then shows a crypto-signals idea stopped by the policy screen.

## What our system will NOT do

- Promise income or guarantee success.
- Write fake reviews, testimonials, sign-ups, traction numbers or countdown timers.
- Pose as the founder, a customer or another brand. Outreach drafts are for the founder to send personally.
- Hold, move, charge or refund money, create accounts, or store passwords or card numbers. Payments are mocked.
- Publish, send, spend or sign anything without the founder's explicit approval.
- Help with physical goods, financial, investment or crypto products, or health or legal advice products.
- Hide any of its own features behind a paywall.
- Spin weak results: gate targets are set before the test, and the system recommends stop when they are missed.

Each limit is checked in code by the guard and the approval queue; [`evals/red_team_report.md`](evals/red_team_report.md) shows every trick request, excluded product and unsafe text the guard was tested on, with 0 failures.

## How the project stays alive after the hackathon

- Maintainers: Mohamed (@Elgahmy1) and contributors; MIT licensed.
- Roadmap: phase 3 full-app code generation in a container sandbox, real payment-provider webhooks in the founder's own account, and product analytics for phase 6, in the order of [ARCHITECTURE.md](ARCHITECTURE.md#roadmap).
- Quality: every push to `main` runs the smoke tests, the guard-only red-team evaluation and the decision-log check in GitHub Actions (`.github/workflows/tests.yml`), on free runners with no keys.
- Community: [CONTRIBUTING.md](CONTRIBUTING.md), [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md) and [SECURITY.md](SECURITY.md); CONTRIBUTING lists first contributions (guard rules, research tools, new agents, translations); red-team prompts in `evals/` run in `tests/` and live via `python evals/run_red_team.py`.
- Funding: runs on free local models, so there is no hosting bill to cover; grants or sponsorship would pay for maintainer time, never for paywalling features.
