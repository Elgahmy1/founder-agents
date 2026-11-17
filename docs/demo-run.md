# Demo run: where each working step's output is

The committed demo run (`48fc7649`, idea: a web app that turns lecture notes into exam-ready summaries) went through all six phases on `openai/gpt-oss-120b` (open weights, Groq free tier). Every file below was written by the pipeline during that run; the founder's decisions and overrides are in [`decision_log.json`](../decision_log.json). Two shorter runs show the system saying no: a weak idea stopped on evidence, and a crypto-signals idea stopped by the policy screen.

| Step | Output |
|---|---|
| Founder brief intake + policy screen (excluded products, unsafe requests) | [STOP example](../outputs/phase1_gate_policy-a-paid-telegram-group-th.md) |
| Phase 1 Discover: find and score opportunities | [output](../outputs/phase1_step1_opportunities-a-web-app-that-turns-mes.md) |
| Phase 1 Discover: define the market | [output](../outputs/phase1_step2_market-a-web-app-that-turns-mes.md) |
| Phase 1 Discover: Mom Test interview plan + outreach draft | [output](../outputs/phase1_step3_interview_plan-a-web-app-that-turns-mes.md) |
| Phase 1 evidence gate (go / repeat / pivot / stop) + founder decision | [output](../outputs/phase1_gate_decision-a-web-app-that-turns-mes.md) |
| Phase 2 Validate: Lean Canvas | [output](../outputs/phase2_step1_lean_canvas-a-web-app-that-turns-mes.md) |
| Phase 2 Validate: landing page copy, safe template, guard scrubbing | [output](../outputs/phase2_step2_landing_page-a-web-app-that-turns-mes.html) |
| Phase 2 demand gate (go / repeat / pivot / stop) + founder decision | [output](../outputs/phase2_gate_decision-a-web-app-that-turns-mes.md) |
| Phase 3 Build: MVP spec (user stories, acceptance criteria, scoped features with hour estimates) | [output](../outputs/phase3_step1_mvp_spec-a-web-app-that-turns-mes.md) |
| Phase 3 Build: clickable prototype from a safe template, published locally after founder approval | [output](../outputs/phase3_step2_prototype-a-web-app-that-turns-mes.html) |
| Phase 3 Build: acceptance tests + build gate (scope vs founder hours, traceability, testability, safety) | [output](../outputs/phase3_gate_decision-a-web-app-that-turns-mes.md) |
| Phase 3 Build: coder agent writes the primary user story's core code plus one check per acceptance criterion; the sandbox (static allowlist + isolated process, no file/network/process access) runs them, with one repair attempt | [output](../outputs/phase3_step4_code-a-web-app-that-turns-mes.md) |
| Phase 3 Build: MVP app: the tested core code (summary and practice questions) in a working web app at `/mvp/<run>`, published after founder approval, each request run in the sandbox | [output](../outputs/phase3_step5_mvp_app-a-web-app-that-turns-mes.html) |
| Phase 4 Commercial setup: tiered pricing with the core feature always free; comparable prices SOURCED or labelled ASSUMPTION | [output](../outputs/phase4_step1_pricing-a-web-app-that-turns-mes.md) |
| Phase 4 Commercial setup: terms, privacy and refund policy DRAFTS, each signed off by the founder; commercial gate | [policies](../outputs/phase4_step2_policies-a-web-app-that-turns-mes.md), [gate](../outputs/phase4_gate_decision-a-web-app-that-turns-mes.md) |
| Phase 5 Launch: store page rendered from the founder-approved prices, launch post drafts per channel, launch targets locked before launch, launch gate | [store page](../outputs/phase5_step1_store_page-a-web-app-that-turns-mes.html), [launch kit](../outputs/phase5_step2_launch_kit-a-web-app-that-turns-mes.md), [gate](../outputs/phase5_gate_decision-a-web-app-that-turns-mes.md) |
| Phase 5 Sell, deliver, get paid on the MVP app in test mode (payments MOCKED): orders, webhook retries ignored, access keys, a refund that revokes access, reconciliation | [test sales](../outputs/phase5_step4_test_sales-a-web-app-that-turns-mes.md), [self-test log](../outputs/payment_test_log.md) |
| Phase 6 Operate and learn: launch results vs the targets locked before launch (sign-ups counted by the app), support reply drafts for real feedback, learn gate (persevere / repeat / pivot / stop), learning memo | [metrics](../outputs/phase6_step1_metrics-a-web-app-that-turns-mes.md), [replies](../outputs/phase6_step2_support_replies-a-web-app-that-turns-mes.md), [gate](../outputs/phase6_gate_decision-a-web-app-that-turns-mes.md), [memo](../outputs/phase6_step3_learning_memo-a-web-app-that-turns-mes.md) |
| Phase 1 evidence gate on a weak idea (water-reminder app): repeat, then stop | [gate](../outputs/phase1_gate_decision-idea-a-mobile-app-that-r.md) |

Gate decisions in this run: Discover GO; Validate PIVOT recommended, founder overrode to GO (logged); Build PIVOT (over scope), then GO; Commercial setup REPEAT, then GO; Launch GO; Operate and learn STOP on real launch numbers (0 visits, 0 sign-ups).

## Second run: a different idea, stopped after validation

Run `066dfbad` (idea: a web app that turns a freelancer's messy time logs into a weekly status report per client), same model, founder decisions at every gate. Discover GO (5 sourced claims, 83% sourced, 2 independent pain sources); Validate PIVOT (0 real sign-ups against a target of 100, 12 interviews against 15); second discovery STOP (only 1 independent pain source). The system recommended stopping before any build time was spent. The 12 interviews were done by the founder before the run; the founder entered their results at the demand gate, which is why they appear a few minutes after the run started in the log.

| Step | Output |
|---|---|
| Phase 1: opportunities, market, interview plan | [opportunities](../outputs/phase1_step1_opportunities-a-web-app-that-turns-a-f.md), [market](../outputs/phase1_step2_market-a-web-app-that-turns-a-f.md), [interview plan](../outputs/phase1_step3_interview_plan-a-web-app-that-turns-a-f.md) |
| Phase 1 evidence gate | [gate](../outputs/phase1_gate_decision-a-web-app-that-turns-a-f.md) |
| Phase 2: Lean Canvas, landing page, demand test | [canvas](../outputs/phase2_step1_lean_canvas-a-web-app-that-turns-a-f.md), [landing page](../outputs/phase2_step2_landing_page-a-web-app-that-turns-a-f.html), [demand test](../outputs/phase2_step3_demand_test-a-web-app-that-turns-a-f.md) |
| Phase 2 demand gate | [gate](../outputs/phase2_gate_decision-a-web-app-that-turns-a-f.md) |
