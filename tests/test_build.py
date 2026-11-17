"""Phase 3 Build: MVP spec, clickable prototype, acceptance tests and the build gate."""
from fastapi.testclient import TestClient

from app.decision_log import validate


def _to_build(orch, brief):
    st = orch.start(brief)
    _, q = orch.load(st.run_id)
    for i in q.pending():
        orch.approve(st.run_id, i.id, True)
    st = orch.founder_gate_decision(st.run_id, "go")
    _, q = orch.load(st.run_id)
    for i in q.pending():
        orch.approve(st.run_id, i.id, True)  # publishes the landing page
    st = orch.founder_lock_targets(st.run_id, True)
    for n in range(st.targets["waitlist_signups"]):
        orch.add_signup(st.run_id, f"real{n}@example.com")  # stands in for real form posts
    st = orch.founder_record_results(st.run_id, interviews_done=10, pain_confirmed=8)
    assert st.gates[-1]["recommendation"] == "go"
    return orch.founder_gate_decision(st.run_id, "go")


def test_build_phase_produces_spec_prototype_tests_and_go(make_orch, brief, settings):
    orch = make_orch()
    st = _to_build(orch, brief)
    assert st.error is None, st.error
    assert st.stage == "p3_gate_wait"
    g = st.gates[-1]
    assert g["gate"] == "build_gate" and g["recommendation"] == "go", g
    for prefix in ("phase3_step1_mvp_spec", "phase3_step2_prototype", "phase3_step3_acceptance_tests", "phase3_gate_decision"):
        assert any(o.startswith(prefix) for o in st.outputs), prefix
    proto = (settings.outputs_dir / next(o for o in st.outputs if o.startswith("phase3_step2"))).read_text()
    assert "<script" not in proto and "<form" not in proto and "SAMPLE output" in proto
    _, q = orch.load(st.run_id)
    assert [i.title for i in q.pending()] == [f"Publish clickable prototype for review: {st.run_id}"]
    st = orch.founder_gate_decision(st.run_id, "go")
    assert st.stage == "done"
    assert not any(o.startswith("phase3_") and "STUBBED" in o for o in st.outputs)
    assert any(o.startswith("phase4_") and "STUBBED" in o for o in st.outputs)
    assert not validate(orch.log.read())


def test_build_over_budget_pivots_then_stops(make_orch, brief):
    orch = make_orch()
    orch.llm.mvp_hours = 80  # 160 h against 15 h/week x 4 = 60 h
    st = _to_build(orch, brief)
    assert st.gates[-1]["recommendation"] == "pivot"
    st = orch.founder_gate_decision(st.run_id, "pivot")
    assert st.stage == "p3_gate_wait"
    assert st.build_feedback and "smaller MVP" in st.build_feedback
    assert st.gates[-1]["recommendation"] == "stop"


def test_prototype_drops_password_and_payment_fields(make_orch, brief, settings):
    orch = make_orch()
    orch.llm.mvp_extra_inputs = ["Password", "Card number"]
    st = _to_build(orch, brief)
    proto = (settings.outputs_dir / next(o for o in st.outputs if o.startswith("phase3_step2"))).read_text()
    assert "Password" not in proto and "Card number" not in proto
    assert st.gates[-1]["recommendation"] == "repeat"


def test_prototype_is_served_only_after_founder_approval(monkeypatch, make_orch, brief):
    import app.main as main
    orch = make_orch()
    monkeypatch.setattr(main, "orch", orch)
    monkeypatch.setattr(main, "settings", orch.settings)
    c = TestClient(main.app)
    st = _to_build(orch, brief)
    assert c.get(f"/proto/{st.run_id}").status_code == 404
    page = c.get(f"/runs/{st.run_id}")
    assert "prototype" in page.text.lower()
    _, q = orch.load(st.run_id)
    orch.approve(st.run_id, q.pending()[0].id, True)
    r = c.get(f"/proto/{st.run_id}")
    assert r.status_code == 200 and "Clickable prototype" in r.text


def test_prototype_safety_check_and_escaping():
    from app.agents.builder import MvpSpec
    from app.prototype import prototype_is_safe, render_prototype
    from tests.conftest import FakeLLM
    data = FakeLLM().mvp()
    data["screens"][0]["sample_output"] = "<script>alert(1)</script><a href='https://evil.example'>x</a>"
    page, _ = render_prototype(MvpSpec.model_validate(data))
    assert prototype_is_safe(page) == []
    for bad in ("<script>x</script>", "<div onclick='x()'>", "<form action=/x>", "<img src='https://x.example/a.png'>"):
        assert prototype_is_safe(page + bad), bad
