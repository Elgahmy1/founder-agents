"""Strategist (Phase 2, core step: Design the business): Lean Canvas."""
from __future__ import annotations

from app import carry as carry_mod
from app.carry import CarryAnswer
from pydantic import BaseModel, Field

from app.agents.base import Agent
from app.specificity import problems
from app.agents.market_analyst import Market
from app.agents.scout import Opportunity
from app.brief import FounderBrief
from app.evidence import RawClaim
from app.research import Doc, docs_for_prompt


class LeanCanvas(BaseModel):
    problem: list[str]
    customer_segments: list[str]
    unique_value_proposition: str
    solution: list[str]
    channels: list[str]
    revenue_streams: list[str] = Field(description="How it could earn money later; no payments are taken in this system")
    cost_structure: list[str]
    key_metrics: list[str]
    unfair_advantage: str
    riskiest_assumptions: list[str] = Field(description="Ordered, riskiest first; these are what Validate tests")
    claims: list[RawClaim]
    carried_forward: list[CarryAnswer] = Field(default_factory=list, description="One answer per carried-forward item, if any")


class StrategistAgent(Agent):
    role = "strategist"

    def lean_canvas(self, brief: FounderBrief, opp: Opportunity, market: Market, docs: list[Doc],
                    carry: list[dict] | None = None) -> LeanCanvas:
        user = (
            f"FOUNDER BRIEF\n{brief.as_text()}\n\nOPPORTUNITY\n{opp.model_dump_json(indent=1)}\n\n"
            f"MARKET\n{market.model_dump_json(indent=1)}\n\nSOURCES\n{docs_for_prompt(docs)}"
        ) + carry_mod.prompt_block(carry or [])
        return self.ask("design_lean_canvas", user, LeanCanvas, sources=[d.url for d in docs],
                        critique=lambda d: problems(d, brief) + carry_mod.check(d, carry or []))
