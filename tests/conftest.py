"""Test fixtures. FakeLLM is used ONLY in tests so they run without a model;
the app itself always uses the real local model."""
from __future__ import annotations

import re
import sys
from dataclasses import replace
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.agents.interview_analyst import InterviewAnalysis
from app.agents.cofounder import CofounderVerdict
from app.agents.area_analyst import AreaCheck
from app.agents.funding_scout import FundingPlan
from app.agents.team_planner import TeamPlan
from app.agents.growth import GrowthPlan
from app.support import SupportReply
from app.agents.advisor import Advice  # noqa: E402
from app.agents.analyst import DemandTestPlan, GateMemo  # noqa: E402
from app.agents.builder import MvpSpec  # noqa: E402
from app.agents.launcher import LaunchKit  # noqa: E402
from app.agents.operator import SupportDrafts  # noqa: E402
from app.agents.coder import CodeDraft  # noqa: E402
from app.agents.policy_drafter import PolicyDrafts  # noqa: E402
from app.agents.pricer import PricingPlan  # noqa: E402
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


GOOD_CODE = {
    "module_code": "import re\n\ndef summarize(notes: str, max_words: int = 300) -> str:\n"
                   "    \"\"\"Extractive summary: first sentences up to max_words.\"\"\"\n"
                   "    out = []\n    for s in re.split(r'(?<=[.!?])\\s+', notes.strip()):\n"
                   "        if len(' '.join(out + [s]).split()) > max_words:\n            break\n        out.append(s)\n"
                   "    return ' '.join(out)\n",
    "checks": [{"story_id": "US1", "criterion": "Given pasted notes, when I press Summarize, then a summary of at most 300 words appears",
                "code": "s = summarize('Cells divide. ' * 400)\nassert 0 < len(s.split()) <= 300"}],
    "notes": "Deterministic extractive summary stands in for the model call; UI and storage come later.",
}


class FakeLLM:
    def __init__(self, strong: bool = True):
        self.model = "fake-test-model"
        self.usage = Usage()
        self.strong = strong

    code_drafts: list = []    # queued CodeDraft dicts; empty -> the passing default below
    translations: dict = {}   # feedback -> English rendering returned by the fake support agent
    support_reply = "Thanks for telling me. — Mohamed"
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

    free_tier = True
    policy_extra = ""

    def pricing(self):
        tiers = [{"name": "Pro", "price_usd_per_month": 4, "includes": ["Key terms", "PDF export"], "who_for": "heavy users"}]
        if self.free_tier:
            tiers.insert(0, {"name": "Free", "price_usd_per_month": 0, "includes": ["Paste and summarize"], "who_for": "every student"})
        return {"tiers": tiers,
                "comparables": [{"product": "Notion", "pricing_note": "unknown", "source_ids": []},
                                {"product": "Obsidian", "pricing_note": "students use obsidian for lecture notes", "source_ids": ["S3"]}],
                "rationale": "Keep the core free; charge for volume.", "price_test": "Ask about past spending on study tools.",
                "claims": [{"text": "Students use Notion and Obsidian for notes", "source_ids": ["S3"]}]}

    def policies(self):
        pol = lambda t: {"title": t, "sections": ["What this covers.", "What we do.", "Contact." + self.policy_extra]}
        return {"terms": pol("Terms of use"), "privacy": pol("Privacy policy"), "refund": pol("Refund policy"),
                "data_collected": ["uploaded notes (deleted after processing)", "email if given"]}

    post_text = "Hi r/college, I'm Mohamed. I built a free tool that turns lecture notes into summaries. Honest feedback welcome."

    def launch(self):
        return {"headline": "Exam-ready notes", "subheadline": "Turn lecture notes into summaries",
                "what_you_get": ["A summary of your notes", "Key terms to revise"],
                "faq": [{"question": "Is it free?", "answer": "The core is free."},
                        {"question": "Does it replace studying?", "answer": "No, it helps you revise."}],
                "posts": [{"channel": "r/college", "text": self.post_text},
                          {"channel": "Facebook groups", "text": "Join 5,000 happy students! Only 3 spots left."}],
                "targets": {"window_days": 14, "store_visits": 200, "free_signups": 30, "paid_orders": 2,
                            "rationale": "ASSUMPTION: 15% of visitors try the free tier."}}

    def structured(self, system, user, schema):
        self.usage.calls += 1
        if schema is CodeDraft and self.code_drafts:
            return schema.model_validate(self.code_drafts.pop(0))
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
                     "unknowns": ["willingness to pay"],
                     "counter_evidence": [{"text": "students use notion and obsidian for lecture notes", "source_ids": ["S3"]}]},
            InterviewPlan: {"goal": "learn how students prepare", "screening_criteria": ["has exams this term"],
                            "questions": ["Tell me about the last time you prepared for an exam."],
                            "avoid": ["Would you use this?"], "pain_confirmed_if": "spent >3h rewriting notes",
                            "outreach_message": "Hi, I'm Mohamed, a student researching how people prep for exams. 15 min?"},
            LeanCanvas: {"problem": ["messy notes"], "customer_segments": ["students"], "unique_value_proposition": "Exam-ready notes",
                         "solution": ["summaries"], "channels": ["campus groups"], "revenue_streams": ["subscription later"],
                         "cost_structure": ["hosting"], "key_metrics": ["weekly active"], "unfair_advantage": "none yet",
                         "riskiest_assumptions": ["students feel the pain"], "claims": c[:1],
                         "carried_forward": [{"item": "Killer risk: students stay with ChatGPT",
                                              "how_addressed": "UVP now names the exam-format output ChatGPT does not give, and the riskiest assumption tests switching"}]},
            LandingCopy: {"headline": "Exam-ready notes", "subheadline": "Turn lecture notes into summaries",
                          "bullets": ["Upload notes", "Get a summary", "Trusted by 10,000 students"],
                          "call_to_action": "Join the waitlist", "honesty_note": "Early product being tested."},
            DemandTestPlan: {"hypothesis": "students want this", "waitlist_signups_target": 50, "window_days": 14,
                             "interviews_target": 10, "pain_confirm_rate_target": 0.5, "channels": ["campus"],
                             "rationale": "ASSUMPTION: 5% conversion"},
            GateMemo: {"summary": "s", "what_we_learned": [], "next_steps": []},
            Advice: {"answer": "Talk to 10 students this week."},
            SupportReply: {"answer": "From your run: the learn gate said STOP. Suggestion: test one course first."},
            GrowthPlan: {"positioning_line": "Exam-format summaries from your own lecture notes, which ChatGPT does not give",
                         "tactics": [
                {"channel": "Facebook group", "where": "the faculty's student group (search the faculty name + students)",
                 "action": "post one free summary of this week's lecture and link the waitlist", "cost_usd": 0, "hours": 2,
                 "metric": "waitlist sign-ups from the post link", "target": "20 sign-ups in 14 days"},
                {"channel": "Paid ads", "where": "Instagram", "action": "run a boosted post", "cost_usd": 300, "hours": 1,
                 "metric": "clicks", "target": "200 clicks in 7 days"},
                {"channel": "Reviews", "where": "app store", "action": "write 20 five-star reviews from friends", "cost_usd": 0,
                 "hours": 1, "metric": "rating", "target": "4.9 stars"}],
                         "avoid": ["Paid ads before the message is proven: the $100 budget would be gone in a week"]},
            TeamPlan: {"roles": [
                {"title": "UI/UX designer", "why": "the upload and summary screens in the MVP spec", "when": "now", "hours_per_week": 5,
                 "how": "part_time", "skills": ["Figma", "mobile layouts"]},
                {"title": "Python developer", "why": "the summarizer core", "when": "now", "hours_per_week": 10, "how": "freelancer",
                 "skills": ["python", "FastAPI"]},
                {"title": "Content marketer", "why": "posts in campus groups from the launch kit", "when": "after_launch",
                 "hours_per_week": 3, "how": "later", "skills": ["Arabic copywriting"]}],
                       "first_hire": "UI/UX designer: the summary screen decides whether students switch from ChatGPT",
                       "job_post_title": "Freelance UI/UX designer, 5 h/week, student exam tool",
                       "job_post": "Early-stage tool, no users yet. One task: design 2 screens in Figma. Paid per task within a $100 budget. Reply with 2 samples."},
            FundingPlan: {"funders": [
                {"name": "Notion for Startups", "kind": "sponsor", "what_they_fund": "credits for student tools", "history": "runs since 2019",
                 "criteria_met": ["student focus", "early stage"], "criteria_missed": ["incorporated company"],
                 "apply_via": "https://example.com/notion-vs-obsidian", "source_ids": ["S3"]},
                {"name": "Imaginary Founders Fund", "kind": "grant", "what_they_fund": "edtech", "history": "unknown",
                 "criteria_met": ["edtech"], "criteria_missed": [], "apply_via": "hello@imaginary.example", "source_ids": []},
                {"name": "City Bank Startup Loans", "kind": "sponsor", "what_they_fund": "small business loans", "history": "-",
                 "criteria_met": [], "criteria_missed": [], "apply_via": "", "source_ids": []}],
                          "email_to": "Notion for Startups", "email_subject": "Student exam-notes tool: are we eligible?",
                          "email_body": "Hi, I'm Mohamed. I am testing a tool that turns lecture notes into exam summaries for university students in Egypt. Two sources show the pain; demand is unproven. Are student-built tools eligible for your credits? — Mohamed"},
            AreaCheck: {"location": "Egypt", "fit": "good", "why": "Large public universities with crowded lectures; Arabic and English slides.",
                        "local_factors": ["Exams are mostly in English for STEM", "Students share notes in course WhatsApp groups"],
                        "resources": [{"need": "Arabic interface", "available": "partly", "note": "S1 mentions bilingual notes"},
                                      {"need": "internet on phones", "available": "yes", "note": "assumption"}],
                        "competitors": [{"name": "ChatGPT", "where": "global", "offer": "free summaries", "gap": "not tied to the course"}],
                        "positioning": "Course-specific practice for Egyptian STEM students, below the price of private tutoring.",
                        "claims": [{"text": "Students struggle organizing lecture notes before exams", "source_ids": ["S1"]},
                                   {"text": "Egyptian students use WhatsApp groups to share notes", "source_ids": []}]},
            CofounderVerdict: {"verdict": "strong", "one_line": "Strong for engineering students in Egypt if it beats ChatGPT on their own slides.",
                               "reasons_for": ["S1 shows students rewriting notes", "the founder tutors STEM students"],
                               "reasons_against": ["ChatGPT is free and already used"], "killer_risk": "students stay with ChatGPT",
                               "improvements": [{"change": "practice questions in the professor's exam style", "why": "ChatGPT cannot see past exams",
                                                 "cheapest_test": "5 students, 2 of the founder's 15 weekly hours, $0"},
                                                {"change": "start with one course", "why": "reach within $100", "cheapest_test": "post in one course group"}],
                               "change_my_mind": "3 of 5 students say ChatGPT already solves it",
                               "best_window": "1-20 December 2026", "timing_why": "3 weeks before January finals; 2 weeks to build at 15 h/week",
                               "avoid_window": "the exam weeks themselves"},
            InterviewAnalysis: {"language": "English", "problem_confirmed": True,
                                "why": "She rewrites notes for hours before every exam, which meets the rule.",
                                "current_workaround": "rewrites slides by hand into a notebook",
                                "cost_of_problem": "about 4 hours per exam", "commitment": "offered to share her notes",
                                "evidence": [{"quote": "I spend like four hours rewriting the slides", "shows": "cost"},
                                             {"quote": "the professor said this would change everything", "shows": "invented"}],
                                "red_flags": [{"quote": "sounds like a cool idea", "shows": "compliment"}],
                                "surprise": "she prints the slides first", "ask_next_time": ["Tell me about your last exam week."]},
            MvpSpec: self.mvp(),
            PricingPlan: self.pricing(),
            PolicyDrafts: self.policies(),
            LaunchKit: self.launch(),
            CodeDraft: GOOD_CODE,
            SupportDrafts: {"replies": [{"feedback": f, "feedback_english": self.translations.get(f, f), "category": "other",
                                         "reply": self.support_reply,
                                         "product_change": "none" if i else "add key terms export"}
                                        for i, f in enumerate(re.findall(r"^- (.+)$", user, re.M))]},
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
