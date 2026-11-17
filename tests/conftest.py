"""Test fixtures. FakeLLM is used ONLY in tests so they run without a model;
the app itself always uses the real local model."""
from __future__ import annotations

import sys
from dataclasses import replace
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.agents.advisor import Advice  # noqa: E402
from app.agents.analyst import DemandTestPlan, GateMemo  # noqa: E402
from app.agents.builder import MvpSpec  # noqa: E402
from app.agents.interviewer import InterviewPlan  # noqa: E402
from app.agents.market_analyst import Market  # noqa: E402
from app.agents.marketer import LandingCopy  # noqa: E402
from app.agents.researcher import QueryPlan  # noqa: E402
from app.agents.scout import Opportunities  # noqa: E402
from app.agents.strategist import LeanCanvas  # noqa: E402
from app.config import load_settings  # noqa: E402
from app.llm import Usage  # noqa: E402
from app.research import Doc  # noqa: E402

DOCS = [
    Doc("S1", "https://www.reddit.com/r/college/comments/a1", "Lecture notes are a mess", "students struggle organizing lecture notes before exams", "reddit"),
    Doc("S2", "https://news.ycombinator.com/item?id=1", "Ask HN: note tools for students", "students spend hours rewriting lecture notes into summaries", "hackernews"),
    Doc("S3", "https://example.com/notion-vs-obsidian", "Notion vs Obsidian for students", "students use notion and obsidian for lecture notes", "web"),
]


def opp(name, pain, score, pain_ids, claims):
    return {"name": name, "problem": "students struggle organizing lecture notes", "customer": "university students",
            "digital_product": "web app that turns lecture notes into exam summaries",
            "current_alternatives": ["Notion", "Obsidian"],
            "scores": {"pain": pain, "founder_fit": score, "feasibility": score, "reach": score, "differentiation": score},
            "claims": claims, "pain_source_ids": pain_ids, "biggest_risk": "students may not pay"}


class FakeLLM:
    def __init__(self, strong: bool = True):
        self.model = "fake-test-model"
        self.usage = Usage()
        self.strong = strong

    mvp_hours = 8.0       # per feature; tests raise it to force an over-scope build gate
    mvp_extra_inputs: list = []

    def mvp(self):
        return {"product_name": "Exam Notes", "one_line": "Turn lecture notes into exam summaries.",
                "user_stories": [
                    {"id": "US1", "as_a": "a student", "i_want": "to paste my lecture notes", "so_that": "I can get a summary",
                     "acceptance": ["Given pasted notes, when I press Summarize, then a summary of at most 300 words appears"]},
                    {"id": "US2", "as_a": "a student", "i_want": "to see key terms", "so_that": "I can revise fast",
                     "acceptance": ["Given a summary, the page lists at least 5 key terms"]}],
                "must_have": [{"name": "Paste and summarize", "description": "text box + summary", "story_ids": ["US1"], "estimate_hours": self.mvp_hours},
                              {"name": "Key terms", "description": "extract terms", "story_ids": ["US2"], "estimate_hours": self.mvp_hours}],
                "out_of_scope": ["accounts", "mobile app"],
                "screens": [{"title": "Paste notes", "purpose": "Input", "inputs": ["Lecture notes", *self.mvp_extra_inputs],
                             "action": "Summarize", "sample_output": "Summary: photosynthesis converts light to energy..."},
                            {"title": "Key terms", "purpose": "Revise", "inputs": [], "action": "Show terms",
                             "sample_output": "chlorophyll, ATP, stomata"}],
                "tech_stack": ["Python", "FastAPI", "Ollama"], "risks": ["summaries may be wrong"]}

    def structured(self, system, user, schema):
        self.usage.calls += 1
        c = [{"text": "Students struggle organizing lecture notes before exams", "source_ids": ["S1"]},
             {"text": "Students spend hours rewriting lecture notes", "source_ids": ["S2"]},
             {"text": "Students use Notion and Obsidian for notes", "source_ids": ["S3"]},
             {"text": "30% of students would pay $5 a month", "source_ids": []}]
        weak = [{"text": "Everyone wants this", "source_ids": ["S9"]}, {"text": "Huge market", "source_ids": []}]
        data = {
            QueryPlan: {"queries": ["lecture notes mess", "exam summary tool"]},
            Opportunities: {"opportunities": [opp("Note Summaries", 4, 4, ["S1", "S2"], c)] if self.strong
                            else [opp("Vague Thing", 1, 2, [], weak)]},
            Market: {"ideal_customer": "2nd-year engineering students", "segments": ["engineering"],
                     "where_they_gather": ["r/college"], "alternatives": ["Notion"], "claims": c[:2],
                     "unknowns": ["willingness to pay"]},
            InterviewPlan: {"goal": "learn how students prepare", "screening_criteria": ["has exams this term"],
                            "questions": ["Tell me about the last time you prepared for an exam."],
                            "avoid": ["Would you use this?"], "pain_confirmed_if": "spent >3h rewriting notes",
                            "outreach_message": "Hi, I'm Mohamed, a student researching how people prep for exams. 15 min?"},
            LeanCanvas: {"problem": ["messy notes"], "customer_segments": ["students"], "unique_value_proposition": "Exam-ready notes",
                         "solution": ["summaries"], "channels": ["campus groups"], "revenue_streams": ["subscription later"],
                         "cost_structure": ["hosting"], "key_metrics": ["weekly active"], "unfair_advantage": "none yet",
                         "riskiest_assumptions": ["students feel the pain"], "claims": c[:1]},
            LandingCopy: {"headline": "Exam-ready notes", "subheadline": "Turn lecture notes into summaries",
                          "bullets": ["Upload notes", "Get a summary", "Trusted by 10,000 students"],
                          "call_to_action": "Join the waitlist", "honesty_note": "Early product being tested."},
            DemandTestPlan: {"hypothesis": "students want this", "waitlist_signups_target": 50, "window_days": 14,
                             "interviews_target": 10, "pain_confirm_rate_target": 0.5, "channels": ["campus"],
                             "rationale": "ASSUMPTION: 5% conversion"},
            GateMemo: {"summary": "s", "what_we_learned": [], "next_steps": []},
            Advice: {"answer": "Talk to 10 students this week."},
            MvpSpec: self.mvp(),
        }[schema]
        return schema.model_validate(data)


class FakeResearcher:
    def __init__(self):
        self.errors = []
        self.enabled = False

    def gather(self, queries, founder_urls=None):
        return list(DOCS)


@pytest.fixture
def settings(tmp_path):
    s = load_settings()
    return replace(s, data_dir=tmp_path / "data", outputs_dir=tmp_path / "outputs",
                   decision_log_path=tmp_path / "decision_log.json", web_research=False)


@pytest.fixture
def make_orch(settings):
    from app.orchestrator import Orchestrator

    def _make(strong=True):
        return Orchestrator(settings, FakeLLM(strong), FakeResearcher())
    return _make


@pytest.fixture
def brief():
    from app.brief import FounderBrief
    return FounderBrief(founder_name="Mohamed", idea="An app that turns lecture notes into exam summaries",
                        skills=["python"], budget_usd=100, hours_per_week=15, target_market="university students in Egypt",
                        values=["honesty"])
