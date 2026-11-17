# Security

Please report a vulnerability privately through GitHub's "Report a vulnerability" (Security tab of this repository) rather than a public issue. We aim to reply within 7 days.

What is in scope, because it is what the project promises:

- Anything that lets an action leave the system (publish, send, spend, sign) without the founder's approval (`app/approval.py`).
- A way past the guard (`app/guard.py`): fake reviews or sign-ups, income promises, impersonation, money movement, credentials, prompt injection, or an excluded product. A new case for `evals/red_team_prompts.json` is the most useful report.
- A way for model-written code to reach files, the network or other processes from the Phase 3 sandbox (`app/sandbox.py`).
- A secret or personal data ending up in `outputs/`, `decision_log.json` or a log.

The app is meant to run on the founder's own machine. It stores no passwords or card numbers and takes no payments; keys stay in the untracked `.env`.
