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
    text = (settings.outputs_dir / next(n for n in names if n.startswith("phase1_step1"))).read_text()
    assert "ASSUMPTION" in text and "https://www.reddit.com" in text


def test_full_validate_flow_and_stop_on_missed_targets(make_orch, brief, settings):
    orch = make_orch(strong=True)
    st = orch.start(brief)
    st = orch.founder_gate_decision(st.run_id, "go")
    assert st.stage == "p2_targets_wait", st.error
    # landing copy contained a fake traction line; it must have been scrubbed
    html = (settings.outputs_dir / next(n for n in st.outputs if n.startswith("phase2_step2"))).read_text()
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
