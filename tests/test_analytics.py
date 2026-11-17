"""Phase 6 usage analytics counted by the app: page name and date only, dashboard views skipped."""
import json

from fastapi.testclient import TestClient

from app.analytics import PageCounter, from_dashboard
from tests.test_operate import _to_operate


def test_counter_stores_only_page_and_date(tmp_path):
    c = PageCounter(tmp_path, "r1")
    c.hit("store"); c.hit("store"); c.hit("mvp_run")
    snap = c.totals()
    c.hit("store")
    assert snap["store"] == 2 and c.since(snap)["store"] == 1 and c.since(snap)["mvp_run"] == 0
    data = json.loads(c.path.read_text())
    assert set(data) == {"store", "mvp_run"} and all(len(k) == 10 for d in data.values() for k in d)
    assert from_dashboard("http://localhost:8000/runs/abc") and not from_dashboard(None)


def test_launch_results_use_counted_visits(make_orch, brief, monkeypatch):
    import app.main as main
    orch = make_orch()
    monkeypatch.setattr(main, "orch", orch)
    monkeypatch.setattr(main, "settings", orch.settings)
    c = TestClient(main.app)
    st = _to_operate(orch, brief)
    assert st.stage == "p6_collecting"
    for _ in range(3):
        assert c.get(f"/store/{st.run_id}").status_code == 200
    c.get(f"/store/{st.run_id}", headers={"referer": f"http://testserver/runs/{st.run_id}"})  # founder: not counted
    assert "<b>3</b> store visits" in c.get(f"/runs/{st.run_id}").text
    c.post(f"/runs/{st.run_id}/operate", data={"visits": "", "paid_orders": "0", "feedback": "too long"})
    for _ in range(50):
        st, _ = orch.load(st.run_id)
        if st.stage != "p6_running" and st.operate:
            break
        import time; time.sleep(0.05)
    assert st.operate["visits"] == 3 and st.operate["visits_source"] == "counted by the app"
    md = (orch.settings.outputs_dir / next(o for o in st.outputs if o.startswith("phase6_step1"))).read_text()
    assert "| 3 | counted by the app |" in md and "no cookies" in md
    assert any(e["action"] == "count_launch_usage" for e in orch.log.read())


def test_founder_can_override_visits_and_output_says_so(make_orch, brief):
    orch = make_orch()
    st = _to_operate(orch, brief)
    st = orch.founder_record_launch_results(st.run_id, visits=40, paid_orders=0, feedback=["x"])
    assert st.operate["visits_source"] == "entered by the founder"
