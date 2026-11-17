"""Pricer (Phase 4, core step: Set the price and policies).

Proposes tiers from comparable products. A comparable price counts as
evidence only if its source was retrieved in this run and mentions it
(app/evidence.py); otherwise it is labelled ASSUMPTION. The core feature
always stays in a free tier: the system never hides core features behind
a paywall. No payment is configured or taken.
"""
from __future__ import annotations

from pydantic import BaseModel, Field

from app.agents.base import Agent
from app.agents.builder import MvpSpec
from app.agents.strategist import LeanCanvas
from app.brief import FounderBrief
from app.evidence import RawClaim
from app.research import Doc, docs_for_prompt


class Tier(BaseModel):
    name: str
    price_usd_per_month: float = Field(ge=0, le=500)
    includes: list[str] = Field(min_length=1, description="Feature names from the MVP spec")
    who_for: str


class Comparable(BaseModel):
    product: str
    pricing_note: str = Field(description="What it charges and for what, as stated in the source, or 'unknown'")
    source_ids: list[str] = Field(default_factory=list)


class PricingPlan(BaseModel):
    tiers: list[Tier] = Field(min_length=1, max_length=4)
    comparables: list[Comparable] = Field(min_length=1, max_length=6)
    rationale: str
    price_test: str = Field(description="How the founder will test willingness to pay without taking money")
    claims: list[RawClaim]


class PricerAgent(Agent):
    role = "pricer"

    def price(self, brief: FounderBrief, canvas: LeanCanvas, spec: MvpSpec, docs: list[Doc],
              feedback: str | None = None, alternatives: list[str] | None = None) -> PricingPlan:
        features = ", ".join(f.name for f in spec.must_have)
        user = (
            f"FOUNDER BRIEF\n{brief.as_text()}\n\nREVENUE STREAMS (Lean Canvas)\n{canvas.revenue_streams}\n\n"
            f"MVP FEATURES\n{features}\n\nALTERNATIVES PEOPLE USE TODAY\n{', '.join(alternatives or []) or 'unknown'}\n\nSOURCES\n{docs_for_prompt(docs)}"
        )
        if feedback:
            user += f"\n\nFEEDBACK FROM THE LAST COMMERCIAL GATE (fix these)\n{feedback}"
        return self.ask("propose_pricing", user, PricingPlan, sources=[d.url for d in docs])
