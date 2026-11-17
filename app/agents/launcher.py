"""Launcher (Phase 5, core step: Open the store; deliver automatically).

Writes store-page copy, launch-post drafts for the founder's own accounts,
and launch targets. Prices on the store page come from the pricing the
founder approved in Phase 4, never from the model. Every post and the page
are approval items; the system never posts or creates accounts.
"""
from __future__ import annotations

from pydantic import BaseModel, Field

from app.agents.base import Agent
from app.specificity import problems
from app.agents.builder import MvpSpec
from app.agents.market_analyst import Market
from app.agents.pricer import PricingPlan
from app.brief import FounderBrief


class Faq(BaseModel):
    question: str
    answer: str


class Post(BaseModel):
    channel: str = Field(description="One of the places where the customers gather")
    text: str = Field(description="Written in the founder's own voice, signed by the founder, no hype")


class LaunchTargets(BaseModel):
    window_days: int = Field(ge=7, le=90)
    store_visits: int = Field(ge=1)
    free_signups: int = Field(ge=1)
    paid_orders: int = Field(ge=0)
    rationale: str = Field(description="Why these numbers; label guesses as ASSUMPTION")


class LaunchKit(BaseModel):
    headline: str
    subheadline: str
    what_you_get: list[str] = Field(min_length=2, max_length=6)
    faq: list[Faq] = Field(min_length=2, max_length=6)
    posts: list[Post] = Field(min_length=1, max_length=4)
    targets: LaunchTargets


class LauncherAgent(Agent):
    role = "launcher"

    def launch_kit(self, brief: FounderBrief, spec: MvpSpec, pricing: PricingPlan, market: Market,
                   feedback: str | None = None) -> LaunchKit:
        user = (
            f"FOUNDER NAME (sign posts with exactly this; never invent a name)\n{brief.signature}\n\n"
            f"PRODUCT\n{spec.product_name}: {spec.one_line}\n"
            f"Features: {'; '.join(f'{f.name}: {f.description}' for f in spec.must_have)}\n"
            f"Not in this version: {', '.join(spec.out_of_scope)}\n\n"
            f"PLANS (the page shows them from the approved pricing; never describe plans, limits or prices yourself)\n"
            f"{', '.join(t.name for t in pricing.tiers)}\n\n"
            f"WHERE CUSTOMERS GATHER\n{', '.join(market.where_they_gather)}"
        )
        if feedback:
            user += f"\n\nFEEDBACK FROM THE LAST LAUNCH GATE (fix these)\n{feedback}"
        return self.ask("write_launch_kit", user, LaunchKit, critique=lambda d: problems(d, brief))
