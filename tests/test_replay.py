"""The committed demo runs can be replayed read-only from decision_log.json, with no model."""
from fastapi.testclient import TestClient

import app.main as main
from app import replay


def test_replay_of_the_committed_demo_run():
    c = TestClient(main.app)
    home = c.get("/").text
    assert "Recorded runs" in home and "/replay/48fc7649" in home
    page = c.get("/replay/48fc7649").text
    assert "Replay of a real run" in page and "valid" in page
    assert "learn gate" in page and "phase3_step4_code-a-web-app-that-turns-mes.md" in page
    assert "approve_publish" in page
    assert c.get("/replay/nope").status_code == 404


def test_runs_summary_counts_from_log():
    entries = main.orch.log.read()
    rs = replay.runs(entries)
    assert rs["48fc7649"]["phase"] == 6 and rs["e874df36"]["ended"] == "stop (policy screen)"
    assert sum(len(r["entries"]) for r in rs.values()) == sum(1 for e in entries if e.get("run_id"))
