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
| Red-team evaluation: 70 trick requests, 31 product ideas, 13 generated texts; report in [`evals/red_team_report.md`](../evals/red_team_report.md), 0 failures | **Working** |
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
