"""Gate decisions end with a next step built from this founder's data, without changing the recommendation."""
from app.next_steps import next_step

BRIEF = {"hours_per_week": 10, "budget_usd": 200, "target_market": "Students"}
MARKET = {"ideal_customer": "STEM undergraduates", "where_they_gather": ["r/EngineeringStudents", "course Discord servers"]}


def test_evidence_repeat_names_the_gap_the_places_and_the_hours():
    g = {"gate": "evidence_gate", "recommendation": "repeat",
         "checks": [{"name": "Independent sources showing the pain", "target": ">= 2", "actual": "1", "passed": False}]}
    s = next_step(g, BRIEF, MARKET, "STEM undergraduates")
    assert "only 1 retrieved source(s)" in s and "r/EngineeringStudents" in s and "10 weekly hours" in s and "$0" in s


def test_demand_pivot_uses_the_real_numbers_and_says_do_not_build():
    g = {"gate": "demand_gate", "recommendation": "pivot",
         "checks": [{"name": "Waitlist sign-ups (real, counted by the app)", "target": ">= 120 in 14 days", "actual": "0", "passed": False}]}
    s = next_step(g, BRIEF, MARKET)
    assert "0 sign-ups against 120 in 14 days" in s and "Do not build yet" in s


def test_learn_stop_and_the_gate_output(make_orch, brief, settings):
    g = {"gate": "learn_gate", "recommendation": "stop",
         "checks": [{"name": "Store visits in the window", "target": ">= 200", "actual": "0", "passed": False},
                    {"name": "Free sign-ups (counted by the app from real form posts)", "target": ">= 50", "actual": "0", "passed": False}]}
    assert "0 store visits and 0 sign-ups against targets of 200 and 50" in next_step(g, BRIEF, MARKET)
    orch = make_orch()
    st = orch.start(brief)
    out = (settings.outputs_dir / next(o for o in st.outputs if o.startswith("phase1_gate_decision"))).read_text(encoding="utf-8")
    assert "Next step for you:" in out
