"""Interviewer (Phase 1): Mom Test interview script and an outreach draft.

The outreach message is a draft written in the founder's own voice for the
founder to send; it is queued for approval and never sent by the system.
"""
from __future__ import annotations

from pydantic import BaseModel, Field

from app.agents.base import Agent
from app.agents.market_analyst import Market
from app.agents.scout import Opportunity


class InterviewPlan(BaseModel):
    goal: str
    screening_criteria: list[str]
    questions: list[str] = Field(description="Mom Test questions about past behaviour, not opinions about the idea")
    avoid: list[str] = Field(description="Leading or hypothetical questions to avoid")
    pain_confirmed_if: str = Field(description="Observable answer pattern that counts as confirming the problem")
    outreach_message: str = Field(description="Short, honest message the founder can send, signed by the founder, no product pitch")


class InterviewerAgent(Agent):
    role = "interviewer"

    def plan_interviews(self, opp: Opportunity, market: Market, founder_name: str) -> InterviewPlan:
        user = (
            f"Founder name: {founder_name}\nOPPORTUNITY\n{opp.model_dump_json(indent=1)}\n\n"
            f"MARKET\n{market.model_dump_json(indent=1)}"
        )
        return self.ask("plan_mom_test_interviews", user, InterviewPlan)
