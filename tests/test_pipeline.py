from app.decision_log import validate


def test_discover_strong_idea_reaches_gate_with_go(make_orch, brief, settings):
    orch = make_orch(strong=True)
    st = orch.start(brief)
    assert st.error is None, st.error
    assert st.stage == "p1_gate_wait"
    assert st.gates[-1]["recommendation"] == "go"
    names = st.outputs
    assert any(n.startswith("phase1_step1_opportunities") for n in names)
    assert any(n.startswith("phase1_gate_decision") for n in names)
    text = (settings.outputs_dir / next(n for n in names if n.startswith("phase1_step1"))).read_text(encoding="utf-8")
    assert "ASSUMPTION" in text and "https://www.reddit.com" in text


def test_full_validate_flow_and_stop_on_missed_targets(make_orch, brief, settings):
    orch = make_orch(strong=True)
    st = orch.start(brief)
    st = orch.founder_gate_decision(st.run_id, "go")
    assert st.stage == "p2_targets_wait", st.error
    # landing copy contained a fake traction line; it must have been scrubbed
    html = (settings.outputs_dir / next(n for n in st.outputs if n.startswith("phase2_step2"))).read_text(encoding="utf-8")
    assert "10,000" not in html and "<script" not in html.lower()
    st = orch.founder_lock_targets(st.run_id, True)
    assert st.stage == "p2_collecting"
    st = orch.founder_record_results(st.run_id, interviews_done=10, pain_confirmed=1)
    assert st.gates[-1]["recommendation"] == "stop"
    st = orch.founder_gate_decision(st.run_id, "stop")
    assert st.stage == "stopped"
    assert not validate(orch.log.read())


def test_weak_idea_recommends_stop(make_orch, brief):
    orch = make_orch(strong=False)
    st = orch.start(brief)
    assert st.gates[-1]["recommendation"] == "stop"


def test_excluded_product_is_stopped_before_any_agent(make_orch, brief):
    orch = make_orch()
    b = brief.model_copy(update={"idea": "A crypto trading signals bot"})
    st = orch.start(b)
    assert st.stage == "stopped"
    assert orch.llm.usage.calls == 0


def test_pivot_moves_back_to_discover(make_orch, brief):
    orch = make_orch()
    st = orch.start(brief)
    st = orch.founder_gate_decision(st.run_id, "pivot")
    assert st.stage == "p1_gate_wait"
    assert st.tried == [0]


def test_second_discovery_pass_without_pain_evidence_stops():
    from app.gates import discover_gate
    first = discover_gate(sourced_claims=4, total_claims=7, pain_sources=0, best_score=3.6, excluded_reason=None, attempt=1)
    assert first.recommendation == "repeat"
    second = discover_gate(sourced_claims=4, total_claims=7, pain_sources=0, best_score=3.6, excluded_reason=None, attempt=2)
    assert second.recommendation == "stop"
    ok = discover_gate(sourced_claims=4, total_claims=7, pain_sources=2, best_score=3.6, excluded_reason=None, attempt=2)
    assert ok.recommendation == "go"


def test_excluded_opportunities_from_model_are_never_chosen(make_orch, brief, settings):
    """An allowed brief can still drift: the model proposes a crypto tracker and a wallet.
    Those are dropped in code; the allowed opportunity is the one pursued."""
    from tests.conftest import opp
    orch = make_orch()
    base = orch.llm.structured

    def drifting(system, user, schema):
        out = base(system, user, schema)
        if schema.__name__ == "Opportunities":
            good = out.opportunities[0].model_dump()
            bad1 = dict(good, name="Crypto Portfolio Tracker", digital_product="app to track crypto holdings",
                        scores={k: 5 for k in good["scores"]})
            bad2 = dict(good, name="Digital Personal Wallet App", digital_product="mobile wallet for payments",
                        scores={k: 5 for k in good["scores"]})
            return schema.model_validate({"opportunities": [bad1, good, bad2]})
        return out
    orch.llm.structured = drifting
    st = orch.start(brief)
    assert st.error is None, st.error
    assert st.opportunities[st.chosen]["name"] == "Note Summaries"
    text = (settings.outputs_dir / next(n for n in st.outputs if n.startswith("phase1_step1"))).read_text(encoding="utf-8")
    assert text.count("EXCLUDED by policy") == 2
    assert any(e["action"] == "exclude_opportunity" for e in orch.log.read())


def test_all_opportunities_excluded_stops(make_orch, brief):
    orch = make_orch()
    base = orch.llm.structured

    def all_bad(system, user, schema):
        out = base(system, user, schema)
        if schema.__name__ == "Opportunities":
            good = out.opportunities[0].model_dump()
            return schema.model_validate({"opportunities": [dict(good, name="E-wallet for students")]})
        return out
    orch.llm.structured = all_bad
    st = orch.start(brief)
    assert st.stage == "stopped"
    assert st.gates[-1]["gate"] == "policy_gate" and st.gates[-1]["recommendation"] == "stop"
