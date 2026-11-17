# Founder Agents

An open-source team of AI agents that takes a founder's brief (idea, skills, budget, time, target market, values) toward a validated digital product. It gathers real sources, labels everything else as an ASSUMPTION, sets evidence targets before testing, and recommends **stop** when the evidence is weak. The founder approves everything that is published, sent, spent or signed, and that rule lives in code (`app/approval.py`).

## Quickstart

```bash
docker compose up
```

Then open http://localhost:8000, fill in a founder brief and press **Start Discover**. The run goes Discover → Validate → Build, and stops at every gate for your decision. The first start downloads the open-weight model (about 5 GB for `qwen3:8b`), so it takes a few minutes once.

Without Docker: install [Ollama](https://ollama.com), run `ollama pull qwen3:8b`, then `pip install -r requirements.txt && uvicorn app.main:app`. A terminal version is available with `python -m app.cli run briefs/study-notes.json`.

## What works and what is mocked

| Step | Status |
|---|---|
| Founder brief intake + policy screen (excluded products, unsafe requests) | **Working** |
| Phase 1 Discover: research from free sources (Hacker News, Stack Exchange, DuckDuckGo, founder URLs) | **Working** |
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
| Phase 3 Build: MVP spec (user stories, acceptance criteria, scoped features with hour estimates) | **Working** |
| Phase 3 Build: clickable prototype from a safe template, published locally after founder approval | **Working** |
| Phase 3 Build: acceptance tests + build gate (scope vs founder hours, traceability, testability, safety) | **Working** |
| Phase 3 Build: generating and running the MVP's code in a sandbox | **STUBBED** |
| Phase 4 Commercial setup (price, policies) | **STUBBED** |
| Phase 5 Launch: store page, launch posts | **STUBBED** |
| Phase 5 Launch: payment → delivery, refunds, idempotency, reconciliation | **MOCKED** (logic runs on mock events, no provider) |
| Phase 6 Operate and learn | **STUBBED** |

## Architecture

An explicit state machine (`app/orchestrator.py`) moves a run through the six phases and stops wherever only the founder can decide. Each agent (`app/agents/`) has one job and one prompt (`prompts/`), and returns schema-checked JSON from a local open-weight model. Every claim passes through the evidence ledger (`app/evidence.py`), which keeps a citation only if the source was actually retrieved and mentions the claim. Gates (`app/gates.py`) compute a recommendation from thresholds fixed in advance, and the founder makes the final call, with any override logged. Full design, including sale to cash: [ARCHITECTURE.md](ARCHITECTURE.md).

## Models and free resources

- Model: `qwen3:8b` (open weights) via [Ollama](https://ollama.com), running locally. Set `MODEL=gpt-oss:20b` (or any Ollama model) in `.env` to switch.
- Research: Hacker News Algolia API, Stack Exchange API, DuckDuckGo HTML results. No keys, no accounts.
- No GPU? Set `LLM_PROVIDER=openai` with a free-tier OpenAI-compatible endpoint that serves open-weight models (for example Groq's free tier with `openai/gpt-oss-120b`); see `.env.example`. The key stays in your untracked `.env`.
- No paid service is used or required. If research sites are unreachable, the run continues and every claim is labelled ASSUMPTION.

## Cost per run

About $0.00 per run (open-weight model, local via Ollama or Groq free tier; the demo run used ~27k tokens in 9 model calls for Discover + Validate + Build). The app shows the token count of each run.

## Demo video

Link to be added.

## What our system will NOT do

- Promise income or guarantee success.
- Write fake reviews, testimonials, sign-ups, traction numbers or countdown timers.
- Pose as the founder, a customer or another brand. Outreach drafts are for the founder to send personally.
- Hold, move, charge or refund money, create accounts, or store passwords or card numbers. Payments are mocked.
- Publish, send, spend or sign anything without the founder's explicit approval.
- Help with physical goods, financial, investment or crypto products, or health or legal advice products.
- Hide any of its own features behind a paywall.
- Spin weak results: gate targets are set before the test, and the system recommends stop when they are missed.

## How the project stays alive after the hackathon

- Maintainers: Mohamed (@Elgahmy1) and contributors; MIT licensed.
- Roadmap: phase 3 code generation in a sandbox, then phases 4-6, in the order of [ARCHITECTURE.md](ARCHITECTURE.md#roadmap).
- Community: [CONTRIBUTING.md](CONTRIBUTING.md) lists first contributions (guard rules, research tools, phase 4-6 agents, translations); red-team prompts in `evals/` run in `tests/` and live via `python evals/run_red_team.py`.
- Funding: runs on free local models, so there is no hosting bill to cover; grants or sponsorship would pay for maintainer time, never for paywalling features.
