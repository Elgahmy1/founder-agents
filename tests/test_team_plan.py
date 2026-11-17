"""Team plan: roles from the run, founder skills and budget applied in code, search links only (no scraping)."""
from fastapi.testclient import TestClient

from app.agents.team_planner import search_links


def test_team_plan_applies_skills_and_budget_and_links_job_boards(monkeypatch, make_orch, brief, settings):
    import app.main as main
    orch = make_orch()
    monkeypatch.setattr(main, "orch", orch)
    st = orch.start(brief)
    r = TestClient(main.app).post(f"/runs/{st.run_id}/team", follow_redirects=False)
    assert r.status_code == 303 and "_team_plan" in r.headers["location"]
    st, _ = orch.load(st.run_id)
    out = (settings.outputs_dir / next(o for o in st.outputs if "_team_plan" in o)).read_text(encoding="utf-8")
    assert "| Python developer |" in out and "you (founder)" in out  # the founder listed python
    assert "UI/UX designer: a part-time hire now does not fit a $100 budget" in out
    assert "linkedin.com/search/results/people/?keywords=UI%2FUX+designer+open+to+work" in out
    assert "never scrapes profiles" in out and "you post it yourself" in out
    assert any(e["action"] == "plan_team_and_search_links" for e in orch.log.read())


def test_search_links_add_local_boards_for_egypt():
    links = search_links("Flutter developer", "Egypt")
    assert any("mostaql.com" in v for v in links.values()) and any("wuzzuf.net" in v for v in links.values())
    assert not any("mostaql" in v for v in search_links("Flutter developer", "Germany").values())


def test_marketing_plan_for_promising_ideas_fits_budget_and_passes_the_guard(make_orch, brief, settings):
    st = make_orch().start(brief)
    assert st.verdict["verdict"] in ("strong", "promising")
    out = (settings.outputs_dir / next(o for o in st.outputs if o.startswith("phase1_step6_marketing"))).read_text(encoding="utf-8")
    assert "faculty's student group" in out and "20 sign-ups in 14 days" in out
    assert "$300 (over budget: skip for now)" in out  # $100 budget
    assert "five-star" not in out and "removed by the guard" in out


def test_weak_ideas_get_no_marketing_plan(make_orch, brief):
    st = make_orch(strong=False).start(brief)
    assert st.marketing is None
