"""Phase 1 co-founder verdict: honest, specific, and never more positive than the evidence gate."""
from app.agents.cofounder import CofounderVerdict, cap_verdict


def _v(verdict="strong"):
    return CofounderVerdict(verdict=verdict, one_line="x", reasons_for=["a"], reasons_against=["b"], killer_risk="k",
                            improvements=[{"change": "c", "why": "w", "cheapest_test": "t"}] * 2, change_my_mind="m")


def test_verdict_is_capped_by_the_evidence():
    assert cap_verdict(_v("strong"), "go", 4.2) == (_v("strong"), None)
    v, note = cap_verdict(_v("strong"), "repeat", 4.0)
    assert v.verdict == "promising" and "Capped in code" in note
    assert cap_verdict(_v("promising"), "pivot", 3.8)[0].verdict == "weak"
    assert cap_verdict(_v("weak"), "stop", 2.0)[0].verdict == "do_not_pursue"
    assert cap_verdict(_v("strong"), "go", 3.2)[0].verdict == "promising"  # a low score caps it too
    assert cap_verdict(_v("weak"), "go", 4.5)[1] is None  # being more critical than the gate is allowed


def test_phase1_writes_the_verdict_and_the_gate_card_shows_it(make_orch, brief, settings, monkeypatch):
    from fastapi.testclient import TestClient
    import app.main as main
    orch = make_orch()
    monkeypatch.setattr(main, "orch", orch)
    st = orch.start(brief)
    out = (settings.outputs_dir / next(o for o in st.outputs if o.startswith("phase1_step4_cofounder_verdict"))).read_text(encoding="utf-8")
    assert "How to make it stronger" in out and "Cheapest test this week" in out
    assert "## When to launch" in out and "1-20 December 2026" in out
    assert st.verdict["verdict"] in ("strong", "promising")
    _, q = orch.load(st.run_id)
    for i in q.pending():
        orch.approve(st.run_id, i.id, True)
    assert "co-founder&#x27;s verdict" in TestClient(main.app).get(f"/runs/{st.run_id}").text or \
        "co-founder's verdict" in TestClient(main.app).get(f"/runs/{st.run_id}").text
    assert "cap_cofounder_verdict" in [e["action"] for e in orch.log.read()]


def test_weak_evidence_caps_an_enthusiastic_verdict(make_orch, brief, settings):
    orch = make_orch(strong=False)
    st = orch.start(brief)
    if st.verdict:  # a weak idea's verdict can never read as strong or promising when the gate says stop or pivot
        assert st.gates[-1]["recommendation"] != "go" and st.verdict["verdict"] in ("weak", "do_not_pursue", "promising")
        assert st.verdict["cap_note"]
