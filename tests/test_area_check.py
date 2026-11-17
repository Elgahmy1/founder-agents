"""Discover starts with an area check when the founder says where they will sell."""
from app.agents.area_analyst import AreaCheck, cap_fit


def _area(fit="good"):
    return AreaCheck(location="Egypt", fit=fit, why="w", local_factors=["f"], positioning="p", claims=[],
                     resources=[{"need": "a", "available": "yes", "note": "n"}, {"need": "b", "available": "unknown", "note": "n"}],
                     competitors=[{"name": "ChatGPT", "where": "global", "offer": "o", "gap": "g"}])


def test_fit_is_unknown_without_a_single_source_about_the_place():
    a, note = cap_fit(_area("good"), sourced_claims=0)
    assert a.fit == "unknown" and "UNKNOWN in code" in note
    assert cap_fit(_area("mixed"), sourced_claims=2) == (_area("mixed"), None)


def test_area_check_runs_first_and_feeds_the_opportunities(make_orch, brief, settings):
    orch = make_orch()
    st = orch.start(brief.model_copy(update={"location": "Egypt"}))
    out = (settings.outputs_dir / next(o for o in st.outputs if o.startswith("phase1_step0_area_check"))).read_text(encoding="utf-8")
    assert "will this work in Egypt" in out and "Competitors and where this idea would stand" in out and "ASSUMPTION" in out
    assert st.area["fit"] == "good" and st.outputs.index(next(o for o in st.outputs if o.startswith("phase1_step0"))) < \
        st.outputs.index(next(o for o in st.outputs if o.startswith("phase1_step1")))
    acts = [e["action"] for e in orch.log.read()]
    assert acts.index("check_area") < acts.index("find_opportunities") and "cap_area_fit" in acts


def test_no_location_means_no_area_check(make_orch, brief):
    st = make_orch().start(brief)
    assert st.area is None and not any(o.startswith("phase1_step0") for o in st.outputs)
