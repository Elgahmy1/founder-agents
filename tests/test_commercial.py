"""Phase 4 Commercial setup: pricing with a free core tier, policy drafts, founder sign-off, commercial gate."""
import pytest

from app.decision_log import validate
from tests.test_build import _to_build


def _to_commercial(orch, brief):
    st = _to_build(orch, brief)
    _, q = orch.load(st.run_id)
    for i in q.pending():
        orch.approve(st.run_id, i.id, True)
    return orch.founder_gate_decision(st.run_id, "go")


def _sign_all(orch, run_id, approve=True):
    _, q = orch.load(run_id)
    for i in q.pending():
        orch.approve(run_id, i.id, approve)


def test_commercial_phase_go_needs_founder_signatures(make_orch, brief, settings):
    orch = make_orch()
    st = _to_commercial(orch, brief)
    assert st.error is None, st.error
    assert st.stage == "p4_gate_wait"
    g = st.gates[-1]
    assert g["gate"] == "commercial_gate" and g["recommendation"] == "go", g
    for prefix in ("phase4_step1_pricing", "phase4_step2_policies", "phase4_gate_decision"):
        assert any(o.startswith(prefix) for o in st.outputs), prefix
    pricing = (settings.outputs_dir / next(o for o in st.outputs if o.startswith("phase4_step1"))).read_text(encoding="utf-8")
    assert "[source: https://example.com/notion-vs-obsidian]" in pricing and "ASSUMPTION" in pricing
    policies = (settings.outputs_dir / next(o for o in st.outputs if o.startswith("phase4_step2"))).read_text(encoding="utf-8")
    assert policies.count("DRAFT") >= 3
    _, q = orch.load(st.run_id)
    assert sorted(i.title.split(":")[0] for i in q.pending()) == [
        "Approve pricing", "Sign off privacy policy draft", "Sign off refund policy draft", "Sign off terms policy draft"]
    with pytest.raises(ValueError):
        orch.founder_gate_decision(st.run_id, "go")  # unsigned: GO is refused in code
    _sign_all(orch, st.run_id)
    st = orch.founder_gate_decision(st.run_id, "go")
    assert st.stage == "p5_gate_wait", st.error
    assert not any(o.startswith("phase4_") and "STUBBED" in o for o in st.outputs)
    assert not validate(orch.log.read())


def test_rejected_policy_blocks_go(make_orch, brief):
    orch = make_orch()
    st = _to_commercial(orch, brief)
    _sign_all(orch, st.run_id, approve=False)
    with pytest.raises(ValueError):
        orch.founder_gate_decision(st.run_id, "go")


def test_core_behind_paywall_repeats_then_stops(make_orch, brief):
    orch = make_orch()
    orch.llm.free_tier = False
    st = _to_commercial(orch, brief)
    assert st.gates[-1]["recommendation"] == "repeat"
    st = orch.founder_gate_decision(st.run_id, "repeat")
    assert st.commercial_feedback and "free tier" in st.commercial_feedback
    assert st.gates[-1]["recommendation"] == "stop"
    _, q = orch.load(st.run_id)
    assert len(q.pending()) == 4 and any(i.status == "superseded" for i in q.items)


def test_promise_in_policy_is_flagged_and_not_queued(make_orch, brief):
    orch = make_orch()
    orch.llm.policy_extra = " We guarantee you will pass your exams."
    st = _to_commercial(orch, brief)
    g = st.gates[-1]
    assert g["recommendation"] == "repeat"
    _, q = orch.load(st.run_id)
    assert not [i for i in q.pending() if i.executor == "sign_commercial"]


def test_finished_build_run_can_continue_into_commercial(make_orch, brief):
    orch = make_orch()
    st = _to_build(orch, brief)
    st, q = orch.load(st.run_id)
    st.gates[-1]["founder_decision"] = "go"
    st.stage = "done"
    orch.save(st, q)
    st = orch.founder_continue(st.run_id)
    assert st.stage == "p4_gate_wait" and st.gates[-1]["gate"] == "commercial_gate"


def test_web_hides_go_until_everything_is_signed(monkeypatch, make_orch, brief):
    from fastapi.testclient import TestClient
    import app.main as main
    orch = make_orch()
    monkeypatch.setattr(main, "orch", orch)
    c = TestClient(main.app)
    st = _to_commercial(orch, brief)
    _, q = orch.load(st.run_id)
    first = q.pending()[0]
    orch.approve(st.run_id, first.id, False)  # founder rejects the pricing
    _sign_all(orch, st.run_id)
    page = c.get(f"/runs/{st.run_id}").text
    assert "Phase 4 gate" in page and "value='go'" not in page and "GO needs your approval" in page


def test_disclaimers_pass_but_promises_do_not():
    from app import guard
    for ok in ("The service is provided as-is and we do not guarantee any specific results.",
               "No results are guaranteed.", "Results are not guaranteed."):
        assert guard.check_output(ok).allowed and guard.check_policy(ok).allowed, ok
    for bad in ("We guarantee you will pass.", "Guaranteed results in 7 days!"):
        assert not guard.check_output(bad).allowed, bad


def test_real_terms_disclaimer_is_queued_and_email_is_placeholder(make_orch, brief, settings):
    orch = make_orch()
    orch.llm.policy_extra = (' The service is provided "as-is" and we do not guarantee any specific results.'
                             " Contact support@examready.ai.")
    st = _to_commercial(orch, brief)
    assert st.error is None, st.error
    assert st.gates[-1]["recommendation"] == "go"
    _, q = orch.load(st.run_id)
    assert len(q.pending()) == 4
    policies = (settings.outputs_dir / next(o for o in st.outputs if o.startswith("phase4_step2"))).read_text(encoding="utf-8")
    assert "examready.ai" not in policies and "[founder contact email]" in policies


def test_core_is_the_primary_story_features(make_orch, brief):
    orch = make_orch()
    base = orch.llm.pricing

    def wrong_core():
        d = base()
        d["tiers"][0]["includes"] = ["Key terms"]  # serves US2, not the primary story US1
        return d
    orch.llm.pricing = wrong_core
    st = _to_commercial(orch, brief)
    g = st.gates[-1]
    assert g["recommendation"] == "repeat"
    assert not g["checks"][0]["passed"]


def test_privacy_features_are_never_paywalled(make_orch, brief):
    orch = make_orch()
    base_mvp, base_pricing = orch.llm.mvp, orch.llm.pricing

    def mvp():
        d = base_mvp()
        d["must_have"].append({"name": "Automatic data deletion", "description": "delete files after processing",
                               "story_ids": ["US2"], "estimate_hours": 4})
        return d

    def pricing():
        d = base_pricing()
        d["tiers"][1]["includes"].append("Automatic data deletion")  # paid only
        return d
    orch.llm.mvp, orch.llm.pricing = mvp, pricing
    st = _to_commercial(orch, brief)
    assert st.gates[-1]["recommendation"] == "repeat"
    assert not st.gates[-1]["checks"][0]["passed"]
