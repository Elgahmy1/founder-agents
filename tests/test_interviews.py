"""Phase 2 interviews: the analyst's quotes are checked against the transcript in code."""
import pytest
from fastapi.testclient import TestClient

from app import interviews as iv
from app.agents.interview_analyst import InterviewAnalysis

TRANSCRIPT = ("Interviewer: tell me about the last exam you prepared for. Student: honestly I spend like four hours "
              "rewriting the slides before every midterm, I print them first and then copy everything into a notebook. "
              "Interviewer: what did you try? Student: I tried ChatGPT once but it missed half the formulas. "
              "Anyway it sounds like a cool idea.")


def _analysis(**kw):
    base = {"language": "English", "problem_confirmed": True, "why": "w", "current_workaround": "rewrites",
            "cost_of_problem": "4 hours", "commitment": "none", "surprise": "prints slides",
            "evidence": [{"quote": "I spend like four hours rewriting the slides", "shows": "cost"}],
            "red_flags": [], "ask_next_time": ["Tell me about your last exam week."]}
    base.update(kw)
    return InterviewAnalysis(**base)


def test_invented_quotes_are_dropped_and_real_ones_kept():
    a, dropped = iv.verify(_analysis(evidence=[{"quote": "I spend like four HOURS rewriting the slides!", "shows": "cost"},
                                               {"quote": "I would pay 10 dollars a month", "shows": "invented"}]), TRANSCRIPT)
    assert [e.quote for e in a.evidence] == ["I spend like four HOURS rewriting the slides!"]
    assert dropped == ["I would pay 10 dollars a month"] and a.problem_confirmed


def test_confirmation_without_a_verified_quote_is_overturned():
    a, dropped = iv.verify(_analysis(evidence=[{"quote": "this app would save my semester", "shows": "invented"}]), TRANSCRIPT)
    assert not a.problem_confirmed and "no evidence quote" in a.why and len(dropped) == 1


def test_arabic_quotes_match_despite_diacritics():
    t = "الطالب: بصراحة بقعد أربع ساعات أكتب السلايدز تاني قبل كل امتحان، وجربت شات جي بي تي ومنفعش."
    a, dropped = iv.verify(_analysis(language="Egyptian Arabic", evidence=[{"quote": "بقعد أربع ساعات أكتب السلايدز تاني", "shows": "cost"}]), t)
    assert a.problem_confirmed and not dropped


def test_interview_flow_feeds_the_demand_gate(make_orch, brief, settings, monkeypatch):
    import app.main as main
    orch = make_orch()
    monkeypatch.setattr(main, "orch", orch)
    st = orch.start(brief)
    st = orch.founder_gate_decision(st.run_id, "go")
    with pytest.raises(ValueError):
        orch.founder_add_interview(st.run_id, TRANSCRIPT)  # targets are not locked yet
    _, q = orch.load(st.run_id)
    for i in q.pending():
        orch.approve(st.run_id, i.id, True)  # outreach draft and landing page
    st = orch.founder_lock_targets(st.run_id, True)
    c = TestClient(main.app)
    assert "Analyse this interview" in c.get(f"/runs/{st.run_id}").text
    r = c.post(f"/runs/{st.run_id}/interview", data={"transcript": TRANSCRIPT, "consent": "1"}, follow_redirects=False)
    assert r.status_code == 303
    st = orch.load(st.run_id)[0]
    a = st.interviews[0]["analysis"]
    assert a["problem_confirmed"] and [e["quote"] for e in a["evidence"]] == ["I spend like four hours rewriting the slides"]
    assert st.interviews[0]["dropped"] == ["the professor said this would change everything"]
    out = (settings.outputs_dir / next(o for o in st.outputs if o.startswith("phase2_step4_interviews"))).read_text(encoding="utf-8")
    assert "1 of 1 interview(s) confirm the problem" in out and "four hours" in out and "Quotes dropped" in out
    assert "copy everything into a notebook" not in out  # the transcript itself stays out of outputs/
    page = c.get(f"/runs/{st.run_id}").text
    assert 'name="interviews_done" min="0" required value="1"' in page  # pre-filled, still editable
    acts = [e["action"] for e in orch.log.read()]
    assert "analyse_interview" in acts and "verify_interview_quotes" in acts
    assert c.post(f"/runs/{st.run_id}/interview", data={"transcript": TRANSCRIPT}).status_code in (400, 422)  # no consent
