"""What Phase 1 learned (the co-founder's killer risk and suggested changes) reaches Phase 2 and 3 outputs."""
from app import carry
from app.agents.builder import MvpSpec


def _out(settings, st, prefix):
    return (settings.outputs_dir / next(o for o in st.outputs if o.startswith(prefix))).read_text(encoding="utf-8")


def test_lean_canvas_answers_the_killer_risk_and_flags_what_it_skipped(make_orch, brief, settings):
    orch = make_orch()
    st = orch.start(brief)
    st = orch.founder_gate_decision(st.run_id, "go")
    canvas = _out(settings, st, "phase2_step1_lean_canvas")
    assert "## Risk and evidence carried forward" in canvas
    assert "Killer risk: students stay with ChatGPT" in canvas and "exam-format output ChatGPT does not give" in canvas
    assert "Suggested change" in canvas and "**not addressed**" in canvas  # the fake skipped it: shown, never hidden
    checks = [e for e in orch.log.read() if e["action"] == "specificity_check" and e.get("checked") == "design_lean_canvas"]
    assert checks and checks[-1]["outcome"] == "redrafted_with_problems_left"  # the critic sent it back once


def test_interview_objections_are_carried_into_the_mvp_spec():
    class St:
        verdict = {"killer_risk": "nobody switches from ChatGPT", "improvements": [{"change": "target one course"}]}
        area = None
        interviews = [{"analysis": {"red_flags": [{"quote": "I would totally use it"}], "current_workaround": "asks ChatGPT"}}]
    items = carry.collect(St(), with_interviews=True)
    assert [i["from"] for i in items] == ["phase1_step4_cofounder_verdict"] * 2 + ["phase2_step4_interviews"] * 2
    assert "CARRIED FORWARD" in carry.prompt_block(items)
    spec = MvpSpec.model_construct(carried_forward=[])
    assert len(carry.check(spec, items)) == 4
    assert carry.collect(St(), with_interviews=False)[-1]["from"] == "phase1_step4_cofounder_verdict"
