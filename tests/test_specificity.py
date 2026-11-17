"""The specificity critic sends generic drafts back once and logs what it found."""
from pathlib import Path

from pydantic import BaseModel

from app import specificity
from app.agents.base import Agent, AgentContext
from app.brief import FounderBrief
from app.decision_log import DecisionLog, validate
from app.llm import Usage

BRIEF = FounderBrief(idea="Exam summaries from lecture notes", skills=["Python", "tutoring STEM students"], budget_usd=200,
                     hours_per_week=10, target_market="university students in Egypt")


class Plan(BaseModel):
    advice: str


class ScriptedLLM:
    """Returns the queued drafts in order and remembers the prompts it got."""
    def __init__(self, drafts):
        self.model, self.usage, self.drafts, self.prompts = "fake", Usage(), list(drafts), []

    def structured(self, system, user, schema):
        self.usage.calls += 1
        self.prompts.append(user)
        return schema(**self.drafts.pop(0))


class Planner(Agent):
    role = "advisor"


def _agent(tmp_path, drafts):
    llm = ScriptedLLM(drafts)
    log = DecisionLog(tmp_path / "log.json")
    ctx = AgentContext(llm=llm, log=log, prompts_dir=Path("prompts"), run_id="r1")
    return Planner(ctx), llm, log


def test_generic_phrases_and_missing_constraints_are_named():
    found = specificity.problems(Plan(advice="Leverage social media and build a strong brand."), BRIEF)
    assert any("leverage social media" in p.lower() for p in found)
    assert any("build a strong brand" in p.lower() for p in found)
    assert any("never uses the founder's constraints" in p for p in found)
    ok = Plan(advice="With $200 and 10 hours a week, post in two Cairo University course groups and book 5 interviews by Friday.")
    assert specificity.problems(ok, BRIEF) == []


def test_generic_draft_is_redrafted_once_and_logged(tmp_path):
    agent, llm, log = _agent(tmp_path, [
        {"advice": "Focus on user experience and leverage social media."},
        {"advice": "Spend 3 of your 10 hours this week interviewing 5 university students in Egypt you tutor; $0 spent."},
    ])
    out = agent.ask("plan", "help", Plan, critique=lambda d: specificity.problems(d, BRIEF))
    assert "10 hours" in out.advice and llm.usage.calls == 2
    assert "TOO GENERIC" in llm.prompts[1] and "leverage social media" in llm.prompts[1].lower()
    entries = log.read()
    check = [e for e in entries if e["action"] == "specificity_check"][-1]
    assert check["outcome"] == "redrafted" and check["checked"] == "plan" and check["model"] is None
    assert [e["action"] for e in entries[:2]] == ["plan", "redraft_plan"]
    assert not validate(entries)


def test_specific_draft_passes_without_an_extra_call(tmp_path):
    agent, llm, log = _agent(tmp_path, [{"advice": "Use your Python skills and $200 to ship a paste-text MVP in 2 weeks."}])
    agent.ask("plan", "help", Plan, critique=lambda d: specificity.problems(d, BRIEF))
    assert llm.usage.calls == 1
    assert [e for e in log.read() if e["action"] == "specificity_check"][-1]["outcome"] == "pass"


def test_opportunities_must_name_the_strongest_alternative():
    from app.agents.scout import Opportunities
    o = {"name": "Exam summaries", "problem": "p", "customer": "university students in Egypt", "digital_product": "web app",
         "current_alternatives": ["manual notes"], "claims": [], "biggest_risk": "With $200 the model costs must stay low",
         "scores": {"pain": 3, "founder_fit": 4, "feasibility": 4, "reach": 3, "differentiation": 2}}
    found = specificity.problems(Opportunities(opportunities=[o]), BRIEF, need_alternative=True)
    assert any("strongest alternative" in p for p in found)
    o.update(strongest_alternative="ChatGPT (free): students paste slides and ask for a summary",
             why_switch="Questions tied to their own course slides and past exam style; ChatGPT does not know either")
    assert specificity.problems(Opportunities(opportunities=[o]), BRIEF, need_alternative=True) == []


def test_suggesting_any_payment_even_a_test_is_sent_back():
    found = specificity.problems(Plan(advice="With $200, add a $5 pre-order button (Stripe test mode) for 10 hours of work."), BRIEF)
    assert any("takes no payments of any kind" in p for p in found)
    ok = Plan(advice="With $200 and 10 hours, show the $5 price next to a free waitlist and ask 5 students what they paid for tutoring.")
    assert specificity.problems(ok, BRIEF) == []
