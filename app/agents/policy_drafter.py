"""Policy drafter (Phase 4): terms, privacy and refund policy DRAFTS.

Drafts only. Each policy becomes a `sign` approval item; the founder signs
it off (and should have it reviewed by a lawyer before launch). This is not
a legal-advice product and the drafts say so.
"""
from __future__ import annotations

from pydantic import BaseModel, Field

from app.agents.base import Agent
from app.agents.builder import MvpSpec
from app.agents.pricer import PricingPlan
from app.brief import FounderBrief


class Policy(BaseModel):
    title: str
    sections: list[str] = Field(min_length=3, description="Short plain-language paragraphs")


class PolicyDrafts(BaseModel):
    terms: Policy
    privacy: Policy
    refund: Policy
    data_collected: list[str] = Field(description="Every piece of user data the MVP stores or processes")


class PolicyDrafterAgent(Agent):
    role = "policy_drafter"

    def draft(self, brief: FounderBrief, spec: MvpSpec, pricing: PricingPlan) -> PolicyDrafts:
        user = (
            f"FOUNDER\n{brief.founder_name}\n\nMVP SPEC\n{spec.model_dump_json(indent=1)}\n\n"
            f"PRICING\n{pricing.model_dump_json(indent=1, include={'tiers'})}"
        )
        return self.ask("draft_policies", user, PolicyDrafts)
