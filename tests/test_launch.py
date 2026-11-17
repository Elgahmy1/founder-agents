"""Phase 5 Launch: store page from approved prices, launch posts as approval items,
launch targets locked before launch, MOCKED sale-to-cash test, launch gate."""
import pytest
from fastapi.testclient import TestClient

from app.decision_log import validate
from tests.test_commercial import _sign_all, _to_commercial


def _to_launch(orch, brief):
    st = _to_commercial(orch, brief)
    _sign_all(orch, st.run_id)
    return orch.founder_gate_decision(st.run_id, "go")


def test_launch_phase_outputs_gate_and_approvals(make_orch, brief, settings):
    orch = make_orch()
    st = _to_launch(orch, brief)
    assert st.error is None, st.error
    assert st.stage == "p5_gate_wait"
    g = st.gates[-1]
    assert g["gate"] == "launch_gate"
    for prefix in ("phase5_step1_store_page", "phase5_step2_launch_kit", "phase5_step3_payment_test", "phase5_gate_decision"):
        assert any(o.startswith(prefix) for o in st.outputs), prefix
    store = (settings.outputs_dir / next(o for o in st.outputs if o.startswith("phase5_step1"))).read_text()
    assert "4 USD / month" in store and "Free" in store and "<script" not in store and "<form" not in store
    assert "Not on sale yet" in store
    kit = (settings.outputs_dir / next(o for o in st.outputs if o.startswith("phase5_step2"))).read_text()
    assert "Only 3 spots left" not in kit and "BLOCKED by guard" in kit  # hype post blocked, never queued
    assert (settings.outputs_dir / "payment_test_log.md").read_text().count("PASS") >= 5
    # one post was blocked, so the gate recommends a redraft
    assert g["recommendation"] == "repeat"
    _, q = orch.load(st.run_id)
    titles = sorted(i.title.split(":")[0] for i in q.pending())
    assert titles == ["Lock launch targets before launch", "Post launch message on r/college", "Publish store page"]


def test_clean_launch_go_needs_store_and_targets(make_orch, brief, settings):
    orch = make_orch()
    base = orch.llm.launch

    def clean():
        d = base()
        d["posts"] = d["posts"][:1]
        return d
    orch.llm.launch = clean
    st = _to_launch(orch, brief)
    assert st.gates[-1]["recommendation"] == "go", st.gates[-1]
    with pytest.raises(ValueError):
        orch.founder_gate_decision(st.run_id, "go")
    _, q = orch.load(st.run_id)
    for i in q.pending():
        orch.approve(st.run_id, i.id, True)
    assert (settings.data_dir / "sites" / st.run_id / "store.html").exists()
    st = orch.founder_gate_decision(st.run_id, "go")
    assert st.stage == "p6_collecting"
    assert not any("STUBBED" in o for o in st.outputs)
    assert not validate(orch.log.read())


def test_store_served_only_after_approval(monkeypatch, make_orch, brief):
    import app.main as main
    orch = make_orch()
    monkeypatch.setattr(main, "orch", orch)
    monkeypatch.setattr(main, "settings", orch.settings)
    c = TestClient(main.app)
    st = _to_launch(orch, brief)
    assert c.get(f"/store/{st.run_id}").status_code == 404
    page = c.get(f"/runs/{st.run_id}").text
    assert "Your approval is needed" in page
    _, q = orch.load(st.run_id)
    store_item = next(i for i in q.pending() if i.executor == "publish_store_local")
    orch.approve(st.run_id, store_item.id, True)
    r = c.get(f"/store/{st.run_id}")
    assert r.status_code == 200 and "Not on sale yet" in r.text


def test_finished_commercial_run_can_continue_into_launch(make_orch, brief):
    orch = make_orch()
    st = _to_commercial(orch, brief)
    _sign_all(orch, st.run_id)
    st, q = orch.load(st.run_id)
    st.gates[-1]["founder_decision"] = "go"
    st.stage = "done"
    orch.save(st, q)
    st = orch.founder_continue(st.run_id)
    assert st.stage == "p5_gate_wait" and st.gates[-1]["gate"] == "launch_gate"


def test_post_with_invented_founder_name_is_blocked(make_orch, brief, settings):
    orch = make_orch()
    orch.llm.post_text = "Hi r/college, I'm Alex, the founder of a new notes tool. Feedback welcome.\n— Alex"
    base = orch.llm.launch

    def one_post():
        d = base()
        d["posts"] = d["posts"][:1]
        return d
    orch.llm.launch = one_post
    st = _to_launch(orch, brief)  # brief founder is Mohamed
    kit = (settings.outputs_dir / next(o for o in st.outputs if o.startswith("phase5_step2"))).read_text()
    assert "BLOCKED by guard" in kit and "is not the founder" in kit and "I'm Alex" not in kit
    assert st.gates[-1]["recommendation"] == "repeat"
    _, q = orch.load(st.run_id)
    assert not [i for i in q.pending() if i.executor == "post_launch_mock"]


def test_faq_cannot_invent_plan_terms(make_orch, brief, settings):
    orch = make_orch()
    base = orch.llm.launch

    def faq_quota():
        d = base()
        d["posts"] = d["posts"][:1]
        d["faq"].append({"question": "What are the limits?", "answer": "The free tier allows 3 documents per month."})
        return d
    orch.llm.launch = faq_quota
    st = _to_launch(orch, brief)
    store = (settings.outputs_dir / next(o for o in st.outputs if o.startswith("phase5_step1"))).read_text()
    assert "3 documents per month" not in store
    assert "What does each plan include?" in store and "4 USD / month" in store


def test_signature_placeholder_when_no_founder_name():
    from app.brief import FounderBrief
    b = FounderBrief(idea="x", target_market="y")
    assert b.signature == "[your name]"
    assert FounderBrief(founder_name="Mohamed", idea="x", target_market="y").signature == "Mohamed"
