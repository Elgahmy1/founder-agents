import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location("ca", Path(__file__).parent.parent / "evals" / "consistency_audit.py")
ca = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ca)


def test_committed_outputs_are_consistent():
    assert ca.audit() == []


def test_each_rule_catches_its_violation(tmp_path):
    (tmp_path / "phase6_step1_metrics-x.md").write_text("| Paid orders | 5 | 3 | from checkout |\n", encoding="utf-8")
    (tmp_path / "phase1_step0_area_check-x.md").write_text("**Local fit: GOOD.** no sources\n", encoding="utf-8")
    (tmp_path / "phase1_step4_cofounder_verdict-x.md").write_text("**Verdict: STRONG.** yes\n", encoding="utf-8")
    (tmp_path / "phase1_gate_decision-x.md").write_text("**System recommendation: PIVOT**\n", encoding="utf-8")
    (tmp_path / "phase3_step4_code-x.md").write_text("| US1 | Given a file, when deleted, then 404 | - | DEFERRED (STUBBED): needs storage |\n", encoding="utf-8")
    (tmp_path / "phase3_step6_user_guide-x.md").write_text("# Guide\nNothing about limits.\n", encoding="utf-8")
    found = ca.audit(tmp_path)
    assert len(found) == 4, found
    assert any("MOCKED" in p for p in found) and any("UNKNOWN" in p for p in found)
    assert any("more positive" in p for p in found) and any("not disclosed" in p for p in found)


def test_assumptions_get_stable_ids_and_show_on_every_gate(make_orch, brief, settings):
    from app.evidence import assumption_ids
    led = [{"text": "a", "status": "ASSUMPTION"}, {"text": "b", "status": "SOURCED"}, {"text": "c", "status": "ASSUMPTION"},
           {"text": "a", "status": "ASSUMPTION"}]
    assert assumption_ids(led) == [("ASM-01", "a"), ("ASM-02", "c")]
    st = make_orch().start(brief)
    gate = (settings.outputs_dir / next(o for o in st.outputs if o.startswith("phase1_gate_decision"))).read_text(encoding="utf-8")
    if any(c["status"] == "ASSUMPTION" for c in st.ledger):
        assert "## Unproven assumptions before you choose GO" in gate and "ASM-01" in gate


def test_market_output_has_sourced_counter_evidence(make_orch, brief, settings):
    st = make_orch().start(brief)
    m = (settings.outputs_dir / next(o for o in st.outputs if o.startswith("phase1_step2_market"))).read_text(encoding="utf-8")
    sec = m.split("## Strongest counter-evidence")[1].split("## ")[0]
    assert "notion and obsidian" in sec and "example.com/notion-vs-obsidian" in sec


def test_research_always_runs_a_disconfirming_pass():
    from app.agents.researcher import QueryPlan
    assert "counter_queries" in QueryPlan.model_fields
