# What works and what is mocked: full table

The step-by-step status behind the short table in the [README](../README.md#what-works-and-what-is-mocked). Every **Working** row has real output from the committed demo runs; [demo-run.md](demo-run.md) maps each step to its file in `outputs/`.

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
| Red-team evaluation: 102 trick requests and 27 normal requests (English, Egyptian Arabic and Franco-Arabic/Arabizi), 31 product ideas, 13 generated texts; report in [`evals/red_team_report.md`](../evals/red_team_report.md), 0 failures | **Working** |
| Phase 3 Build: MVP spec (user stories, acceptance criteria, scoped features with hour estimates) | **Working** |
| Phase 3 Build: clickable prototype from a safe template, published locally after founder approval | **Working** |
| Phase 3 Build: acceptance tests + build gate (scope vs founder hours, traceability, testability, safety) | **Working** |
| Phase 3 Build: coder agent writes core code for every user story in the MVP spec plus one check per acceptance criterion (criteria that need storage, a UI or hosting are listed as deferred, never faked); the sandbox (static allowlist + isolated process, no file/network/process access) runs them, with one repair attempt; CI re-runs the committed code against its checks on every push | **Working** |
| Phase 3 Build: MVP app: the tested core code wrapped in a working web app at `/mvp/<run>` after founder approval; each request runs the code in the sandbox, nothing is stored | **Working** locally; public hosting **MOCKED** |
| Phase 3 Build: user docs for the MVP: a user guide (what it does today, how to use it, a real example run, what was tested, what it does not do yet, data handling) written by the pipeline from the spec, the tested code and a sandbox run, no model call; published with the app at `/mvp/<run>/guide` after founder approval | **Working** locally; public hosting **MOCKED** |
| Phase 3 Build: MVP app storage, accounts, and the acceptance criteria that need them (listed as DEFERRED in `phase3_step4_code`) | **STUBBED** |
| Phase 4 Commercial setup: tiered pricing with the core feature always free; comparable prices SOURCED or labelled ASSUMPTION | **Working** |
| Phase 4 Commercial setup: terms, privacy and refund policy DRAFTS, each signed off by the founder; commercial gate | **Working** |
| Phase 5 Launch: store page rendered from the founder-approved prices, launch post drafts per channel, launch targets locked before launch, launch gate | **Working** |
| Phase 5 Launch: public hosting, posting to channels, checkout | **MOCKED** (founder posts personally; store served locally; no checkout) |
| Phase 5 Launch: payment → delivery, refunds, idempotency, reconciliation | **MOCKED** (real logic runs on mock events inside the launch gate; no provider) |
| Phase 6 Operate and learn: launch results vs the targets locked before launch (sign-ups counted by the app), support reply drafts for real feedback, learn gate (persevere / repeat / pivot / stop), learning memo | **Working** |
| Phase 6 usage analytics: store visits, landing and MVP app views and MVP app runs since launch, counted by the app itself (page name and date only: no cookies, IPs or user agents; the founder's own dashboard views are skipped) and used by the learn gate | **Working** (counts only visits reaching this server, since public hosting is MOCKED) |
| Phase 6: sending support replies | **MOCKED** (founder sends replies personally) |
| Replay of the recorded runs at `/replay/<run>`: phases, gates vs founder decisions, outputs and every logged action, read-only from the committed log, available before any model is downloaded | **Working** |
| Founder export: the whole run (brief, gates, decisions, approvals, decision log, outputs) as one Markdown file, no model call | **Working** |
| Run metrics from the decision log: calls, tokens, cost, time, gate recommendation vs founder decision, approval audit; [`evals/run_metrics.md`](../evals/run_metrics.md), checked against the log in CI | **Working** |
| Claims audit: every `[source: URL]` in `outputs/` must be a URL a logged research action actually retrieved, plus SOURCED vs ASSUMPTION counts per output; [`evals/claims_audit.md`](../evals/claims_audit.md), checked in CI (38 sourced claims, 24 ASSUMPTION labels, 0 unretrieved URLs) | **Working** |

- Funding scout (`app/agents/funding_scout.py`, `phase1_step5_funding`) and launch timing in the co-founder verdict. UI: technical items (files, approvals, report export, token use) moved into a collapsed Details section.
- Research relevance filter (`research.relevant`): results that share fewer than two content words with their query are dropped before the agents see them (a real run for Egyptian freelancers had pulled Wikipedia pages about wars that only mentioned Egypt).
- Batch 1: Arabic normalization (`app/arabic.py`) in quote matching and the guard; Masri and Franco-Arabic/Arabizi rules (+12 red-team cases); polite non-commitments ("إن شاء الله", "فكرة جامدة") moved to red flags in code; user stories cite a verified interview quote ID or are ASSUMPTION-DRIVEN; MVP page "Load tested sample input"; web results and transcripts that try to instruct the agents are stripped and logged as `indirect_injection_filtered`.
- Batch 2: a disconfirming search pass (2 counter queries per run) and a "Strongest counter-evidence" section in the market output, sourced or ASSUMPTION; every ASSUMPTION gets a stable ID (ASM-01...) shown on each later gate card and gate output before GO; `evals/consistency_audit.py` (CI) checks that Phase 6 never counts MOCKED activity as traction, that area-fit and verdict caps hold in saved outputs, and that every DEFERRED criterion is disclosed in the user guide.
- Batch 3: the Phase 2 landing page exports as one static file whose form posts to the founder's own endpoint (mailto: or an https form service); sign-ups exported from that form are imported as a CSV (only email hashes kept, duplicates dropped) and feed the demand gate as [FOUNDER-REPORTED METRIC]; Phase 6 imports the founder's own order/activation records as counts (no amounts, cards or logins); a PIVOT/REPEAT/STOP gate can fork a new run (`parent_run_id`, `fork_from_phase` logged; retrieved sources reused, parent untouched); `/compare/<a>/<b>` shows two runs side by side, read-only.
- Team planner (on demand, "Plan my team"): roles this business needs, when, and how (founder / freelancer / part-time / co-founder / later); code keeps work the founder has skills for with the founder and keeps paid hires within the budget; search links to people looking for that work (LinkedIn open to work, Upwork, Mostaql, Wuzzuf), never scraped or contacted; a guard-checked job post draft. Marketing plan (strong or promising ideas, `phase1_step6_marketing`): 2-5 tactics tied to where the run found the customers, each with this week's action, cost, hours and a numeric target; code keeps the total within the budget and screens every tactic with the guard.
