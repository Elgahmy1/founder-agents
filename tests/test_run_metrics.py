import json
from pathlib import Path

from evals import run_metrics

ROOT = Path(__file__).resolve().parent.parent


def test_committed_metrics_report_matches_the_log():
    entries = json.loads((ROOT / "decision_log.json").read_text(encoding="utf-8"))
    assert (ROOT / "evals" / "run_metrics.md").read_text(encoding="utf-8") == run_metrics.report(entries)


def test_no_action_was_executed_without_founder_approval():
    entries = json.loads((ROOT / "decision_log.json").read_text(encoding="utf-8"))
    audit = run_metrics.approval_audit(entries)
    assert audit["executed"] > 0 and audit["unapproved"] == []


def test_audit_flags_an_execution_without_approval():
    entries = [{"agent": "executor", "action": "execute_publish_landing_local", "approved_by": None, "item_id": "x"}]
    assert run_metrics.approval_audit(entries)["unapproved"] == ["execute_publish_landing_local"]
