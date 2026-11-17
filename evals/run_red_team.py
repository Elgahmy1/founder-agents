"""Runs every trick prompt in red_team_prompts.json through the same path as
the web app's "Ask the team" box (guard first, then the advisor model with
output scrubbing) and writes evals/red_team_report.md.

  python evals/run_red_team.py
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app import guard  # noqa: E402
from app.agents.advisor import AdvisorAgent  # noqa: E402
from app.agents.base import AgentContext  # noqa: E402
from app.config import load_settings  # noqa: E402
from app.decision_log import DecisionLog  # noqa: E402
from app.llm import make_llm  # noqa: E402


def main() -> int:
    s = load_settings()
    prompts = json.loads((ROOT / "evals" / "red_team_prompts.json").read_text(encoding="utf-8"))
    llm = make_llm(s)
    # Eval runs log to their own file so the committed demo decision log stays the demo's.
    log = DecisionLog(ROOT / "evals" / "red_team_decision_log.json")
    advisor = AdvisorAgent(AgentContext(llm, log, s.prompts_dir, "redteam"))
    ctx = "Idea: a web app that turns lecture notes into exam summaries. Stage: Discover."
    rows, failures = [], 0
    for p in prompts["must_refuse"]:
        v = guard.check_request(p)
        ok = not v.allowed
        failures += not ok
        rows.append(("refuse", p, "REFUSED" if ok else "ALLOWED", v.rule or "", "PASS" if ok else "FAIL"))
    for p in prompts["must_allow"]:
        v = guard.check_request(p)
        if not v.allowed:
            failures += 1
            rows.append(("allow", p, "REFUSED", v.rule or "", "FAIL"))
            continue
        ans = advisor.answer(ctx, p).answer
        clean, removed = guard.scrub_output(ans)
        rows.append(("allow", p, "ANSWERED", (clean[:140] + "...") if len(clean) > 140 else clean, "PASS"))
    md = ["# Red-team evaluation", "",
          f"Run {datetime.now(timezone.utc).isoformat(timespec='seconds')} with model `{llm.model}`.",
          f"Trick prompts refused: {sum(1 for r in rows if r[0] == 'refuse' and r[4] == 'PASS')}/{len(prompts['must_refuse'])}. "
          f"Normal requests answered: {sum(1 for r in rows if r[0] == 'allow' and r[4] == 'PASS')}/{len(prompts['must_allow'])}.",
          "", "| Expect | Prompt | Result | Rule / answer | Pass |", "|---|---|---|---|---|"]
    md += [f"| {a} | {b.replace('|', '/')} | {c} | {d.replace('|', '/').replace(chr(10), ' ')} | {e} |" for a, b, c, d, e in rows]
    (ROOT / "evals" / "red_team_report.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print("\n".join(md[:4]))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
