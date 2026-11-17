import pytest
from fastapi.testclient import TestClient

from app.approval import ApprovalRequired


def test_nothing_executes_without_founder_approval(make_orch, brief, settings):
    orch = make_orch()
    st = orch.start(brief)
    st = orch.founder_gate_decision(st.run_id, "go")
    _, q = orch.load(st.run_id)
    publish = next(i for i in q.items if i.kind == "publish")
    with pytest.raises(ApprovalRequired):
        q.execute(publish.id)
    assert not (settings.data_dir / "sites" / st.run_id / "index.html").exists()
    with pytest.raises(PermissionError):
        orch.add_signup(st.run_id, "a@b.c")


def test_rejected_item_is_never_executed(make_orch, brief, settings):
    orch = make_orch()
    st = orch.start(brief)
    st = orch.founder_gate_decision(st.run_id, "go")
    _, q = orch.load(st.run_id)
    publish = next(i for i in q.items if i.kind == "publish")
    orch.approve(st.run_id, publish.id, False)
    _, q = orch.load(st.run_id)
    with pytest.raises(ApprovalRequired):
        q.execute(publish.id)
    assert not (settings.data_dir / "sites" / st.run_id / "index.html").exists()


def test_approved_publish_goes_live_locally_and_logs_founder(make_orch, brief, settings):
    orch = make_orch()
    st = orch.start(brief)
    st = orch.founder_gate_decision(st.run_id, "go")
    _, q = orch.load(st.run_id)
    publish = next(i for i in q.items if i.kind == "publish")
    orch.approve(st.run_id, publish.id, True)
    assert (settings.data_dir / "sites" / st.run_id / "index.html").exists()
    approved = [e for e in orch.log.read() if e["action"] == "approve_publish"]
    assert approved and approved[0]["approved_by"] == "founder"


def test_guard_blocks_unsafe_artifact_from_queue(make_orch, brief):
    orch = make_orch()
    st = orch.start(brief)
    _, q = orch.load(st.run_id)
    with pytest.raises(PermissionError):
        q.submit("publish", "bad", "Guaranteed income! Only 3 spots left", "publish_landing_local", 2)


def test_landing_page_404_until_approved(monkeypatch, make_orch, brief, settings):
    import app.main as main
    orch = make_orch()
    monkeypatch.setattr(main, "orch", orch)
    monkeypatch.setattr(main, "settings", settings)
    st = orch.start(brief)
    st = orch.founder_gate_decision(st.run_id, "go")
    c = TestClient(main.app)
    assert c.get(f"/lp/{st.run_id}").status_code == 404


def test_concurrent_advance_does_not_duplicate_work(make_orch, brief):
    import threading
    orch = make_orch()
    st = orch.create(brief)
    ts = [threading.Thread(target=orch.advance, args=(st.run_id,)) for _ in range(5)]
    [t.start() for t in ts]
    [t.join() for t in ts]
    st, q = orch.load(st.run_id)
    assert st.stage == "p1_gate_wait"
    assert len(q.items) == 1 and len(st.gates) == 1
    assert sum(1 for e in orch.log.read() if e["action"] == "evidence_gate") == 1


def test_stale_approval_click_does_not_500(monkeypatch, make_orch, brief):
    import app.main as main
    orch = make_orch()
    monkeypatch.setattr(main, "orch", orch)
    st = orch.start(brief)
    r = TestClient(main.app).post(f"/runs/{st.run_id}/approvals/doesnotexist", data={"approve": "1"},
                                  follow_redirects=False)
    assert r.status_code == 303
