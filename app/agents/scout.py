"""Opportunity scout (Phase 1, core step: Find opportunities).

Sharpens the founder's starting idea into a few concrete opportunities and
scores each against the founder's constraints and the alternatives people
already use. Scores are the model's judgement; the claims behind them go
through the evidence ledger.
"""
from __future__ import annotations

from pydantic import BaseModel, Field

from app.agents.base import Agent
from app.brief import FounderBrief
from app.evidence import RawClaim
from app.research import Doc, docs_for_prompt
from app.specificity import problems


class Scores(BaseModel):
    pain: int = Field(ge=1, le=5, description="How painful/frequent the problem is, per the sources")
    founder_fit: int = Field(ge=1, le=5, description="Fit with the founder's skills and values")
    feasibility: int = Field(ge=1, le=5, description="Can a digital MVP be built within the budget and hours")
    reach: int = Field(ge=1, le=5, description="Can the founder reach these customers cheaply")
    differentiation: int = Field(ge=1, le=5, description="Better than the alternatives people use today")


class Opportunity(BaseModel):
    name: str
    problem: str
    customer: str
    digital_product: str
    current_alternatives: list[str]
    scores: Scores
    claims: list[RawClaim]
    pain_source_ids: list[str] = Field(default_factory=list, description="Source ids where real people describe this pain")
    strongest_alternative: str = Field(default="", description="What these customers use today that is hardest to beat, "
                                       "including free general-purpose AI assistants (ChatGPT, Gemini) where they apply")
    why_switch: str = Field(default="", description="The concrete reason a customer would switch from that alternative, "
                            "or a plain statement that they would not")
    biggest_risk: str

    @property
    def score(self) -> float:
        s = self.scores
        return round((s.pain + s.founder_fit + s.feasibility + s.reach + s.differentiation) / 5, 2)


class Opportunities(BaseModel):
    opportunities: list[Opportunity] = Field(min_length=1, max_length=3)


class ScoutAgent(Agent):
    role = "scout"

    def find_opportunities(self, brief: FounderBrief, docs: list[Doc]) -> Opportunities:
        user = (
            f"FOUNDER BRIEF\n{brief.as_text()}\n\nSOURCES\n{docs_for_prompt(docs)}\n\n"
            "Produce up to 3 sharpened digital-product opportunities derived from the idea, "
            "including the founder's original framing as one of them."
        )
        return self.ask("find_opportunities", user, Opportunities, sources=[d.url for d in docs],
                        critique=lambda d: problems(d, brief, need_alternative=True))
