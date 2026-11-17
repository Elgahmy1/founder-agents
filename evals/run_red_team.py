"""Runs every trick prompt in red_team_prompts.json through the same path as
the web app's "Ask the team" box (guard first, then the advisor model with
output scrubbing) and writes evals/red_team_report.md.

  python evals/run_red_team.py               # guard + the advisor model on the normal requests
  python evals/run_red_team.py --guard-only  # guard only: no model calls, no cost, no quota
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
    guard_only = "--guard-only" in sys.argv
    s = load_settings()
    prompts = json.loads((ROOT / "evals" / "red_team_prompts.json").read_text(encoding="utf-8"))
    llm = None if guard_only else make_llm(s)
    advisor = None
    if not guard_only:
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
        if guard_only:
            rows.append(("allow", p, "PASSED GUARD", "model not called (--guard-only)", "PASS"))
            continue
        ans = advisor.answer(ctx, p).answer
        clean, removed = guard.scrub_output(ans)
        rows.append(("allow", p, "ANSWERED", (clean[:140] + "...") if len(clean) > 140 else clean, "PASS"))
    # Product policy screen (what an idea or opportunity is checked against before any agent works on it).
    for kind, key, want_block, fn in (("stop product", "products_must_stop", True, guard.check_product),
                                      ("allow product", "products_must_pass", False, guard.check_product),
                                      ("block copy", "outputs_must_block", True, guard.check_output),
                                      ("block reply", "support_replies_must_block", True, guard.check_support_reply),
                                      ("allow copy", "outputs_must_pass", False, guard.check_support_reply)):
        for p in prompts.get(key, []):
            v = fn(p)
            ok = (not v.allowed) == want_block
            failures += not ok
            rows.append((kind, p, "BLOCKED" if not v.allowed else "ALLOWED", v.rule or "", "PASS" if ok else "FAIL"))

    def count(prefix):
        rs = [r for r in rows if r[0] == prefix]
        return f"{sum(r[4] == 'PASS' for r in rs)}/{len(rs)}"
    mode = "guard only (no model calls)" if guard_only else f"model `{llm.model}`"
    md = ["# Red-team evaluation", "",
          f"Run {datetime.now(timezone.utc).isoformat(timespec='seconds')} with {mode}, "
          "by `python evals/run_red_team.py" + (" --guard-only" if guard_only else "") + "`.", "",
          f"- Trick requests refused: {count('refuse')}",
          f"- Normal requests allowed: {count('allow')}",
          f"- Excluded products stopped (crypto, finance, health, legal, physical, fake reviews): {count('stop product')}",
          f"- Allowed digital products passed: {count('allow product')}",
          f"- Promises, fake testimonials and fake urgency blocked in generated copy: {count('block copy')}",
          f"- Support replies that promise refunds or ask for payment details blocked: {count('block reply')}",
          f"- Honest disclaimers and replies allowed: {count('allow copy')}",
          f"- Failures: {failures}",
          "", "| Expect | Input | Result | Rule / answer | Pass |", "|---|---|---|---|---|"]
    md += [f"| {a} | {b.replace('|', '/')} | {c} | {d.replace('|', '/').replace(chr(10), ' ')} | {e} |" for a, b, c, d, e in rows]
    (ROOT / "evals" / "red_team_report.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print("\n".join(md[:13]))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
