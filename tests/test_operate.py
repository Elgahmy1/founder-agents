"""Phase 6 Operate and learn: real results vs locked launch targets, support drafts, learn gate, memo."""
from fastapi.testclient import TestClient

from app.decision_log import validate
from tests.test_launch import _to_launch


def _to_operate(orch, brief):
    base = orch.llm.launch

    def clean():
        d = base()
        d["posts"] = d["posts"][:1]
        return d
    orch.llm.launch = clean
    st = _to_launch(orch, brief)
    _, q = orch.load(st.run_id)
    for i in q.pending():
        orch.approve(st.run_id, i.id, True)
    return orch.founder_gate_decision(st.run_id, "go")


def test_weak_launch_recommends_stop_with_memo(make_orch, brief, settings):
    orch = make_orch()
    st = _to_operate(orch, brief)
    assert st.stage == "p6_collecting"
    orch.add_signup(st.run_id, "a@example.com")  # 1 real sign-up against a target of 30
    st = orch.founder_record_launch_results(st.run_id, visits=40, paid_orders=0, feedback=["Summaries were too long"])
    assert st.error is None, st.error
    assert st.stage == "p6_gate_wait"
    g = st.gates[-1]
    assert g["gate"] == "learn_gate" and g["recommendation"] == "stop", g
    assert st.operate["signups"] == 1
    for prefix in ("phase6_step1_metrics", "phase6_step2_support_replies", "phase6_gate_decision", "phase6_step3_learning_memo"):
        assert any(o.startswith(prefix) for o in st.outputs), prefix
    _, q = orch.load(st.run_id)
    assert [i.executor for i in q.pending()] == ["send_support_reply_mock"]
    st = orch.founder_gate_decision(st.run_id, "stop")
    assert st.stage == "stopped"
    assert not validate(orch.log.read())


def test_strong_launch_perseveres(make_orch, brief):
    orch = make_orch()
    st = _to_operate(orch, brief)
    for n in range(30):
        orch.add_signup(st.run_id, f"u{n}@example.com")
    st = orch.founder_record_launch_results(st.run_id, visits=250, paid_orders=0,
                                            feedback=["love it", "summaries help", "please add flashcards"])
    assert st.gates[-1]["recommendation"] == "go"
    _, q = orch.load(st.run_id)
    for i in q.pending():
        orch.approve(st.run_id, i.id, True)
    st = orch.founder_gate_decision(st.run_id, "go")
    assert st.stage == "done"


def test_web_launch_results_form_and_done_page(monkeypatch, make_orch, brief):
    import app.main as main
    orch = make_orch()
    monkeypatch.setattr(main, "orch", orch)
    monkeypatch.setattr(main, "settings", orch.settings)
    c = TestClient(main.app)
    st = _to_operate(orch, brief)
    page = c.get(f"/runs/{st.run_id}").text
    assert "real launch results" in page and "counted by the app" in page
    for n in range(30):
        orch.add_signup(st.run_id, f"u{n}@example.com")
    st = orch.founder_record_launch_results(st.run_id, visits=250, paid_orders=0, feedback=["a", "b", "c"])
    _, q = orch.load(st.run_id)
    for i in q.pending():
        orch.approve(st.run_id, i.id, True)
    orch.founder_gate_decision(st.run_id, "go")
    page = c.get(f"/runs/{st.run_id}")
    assert page.status_code == 200 and "All six phases complete" in page.text


def test_finished_launch_run_can_continue_into_operate(make_orch, brief):
    orch = make_orch()
    st = _to_operate(orch, brief)
    st, q = orch.load(st.run_id)
    st.stage = "done"
    orch.save(st, q)
    st = orch.founder_continue(st.run_id)
    assert st.stage == "p6_collecting"
