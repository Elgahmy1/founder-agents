"""Marketing plan for ideas the co-founder rates strong or promising (Phase 1, after the funding scout).

The agent proposes 3-5 tactics tied to where THIS run found the customers. Code then keeps it honest and affordable:
- every tactic's action passes the guard (no fake reviews, fake urgency, impersonation, posting on the founder's behalf);
- tactics are kept in order until their total cost would exceed the founder's budget; the rest are marked over budget;
- each tactic carries a measurable target, so the launch gate can later compare it with what really happened.
Posting stays with the founder: these are suggestions and drafts, nothing is published.
"""
from __future__ import annotations

from pydantic import BaseModel, Field

from app import guard
from app.agents.base import Agent
from app.specificity import problems


class Tactic(BaseModel):
    channel: str = Field(description="e.g. Facebook group, TikTok, university club, WhatsApp community, SEO, partnership")
    where: str = Field(description="The specific place from the run (a community from the market analysis or a source), "
                       "or a description of how to find it; never an invented name")
    action: str = Field(description="What the founder does this week, concretely (what to post or offer, how many times)")
    cost_usd: float = Field(ge=0)
    hours: float = Field(ge=0)
    metric: str = Field(description="What to count, e.g. 'waitlist sign-ups from this link'")
    target: str = Field(description="A number to reach in a stated time, e.g. '20 sign-ups in 14 days'")


class GrowthPlan(BaseModel):
    positioning_line: str = Field(description="One sentence a customer would understand: who it is for and why it beats the strongest alternative")
    tactics: list[Tactic] = Field(min_length=2, max_length=5)
    avoid: list[str] = Field(description="1-3 channels or tactics that would waste this founder's time or money, and why")


def apply_rules(plan: GrowthPlan, budget: float) -> tuple[list[dict], list[str]]:
    rows, dropped, spent = [], [], 0.0
    for t in plan.tactics:
        text = f"{t.action} {t.where}"
        v = guard.check_request(text)  # a tactic is an instruction to the founder: screen it like a request ...
        if v.allowed:
            v = guard.check_output(text)  # ... and like published copy
        if not v.allowed:
            dropped.append(f"{t.channel}: removed by the guard ({v.rule})")
            continue
        fits = spent + t.cost_usd <= budget
        if fits:
            spent += t.cost_usd
        rows.append(t.model_dump() | {"fits_budget": fits})
    return rows, dropped


class GrowthAgent(Agent):
    role = "growth"

    def plan(self, brief, context: str) -> GrowthPlan:
        user = f"FOUNDER BRIEF\n{brief.as_text()}\n\nWHAT THIS RUN FOUND\n{context}"
        return self.ask("plan_marketing", user, GrowthPlan, critique=lambda d: problems(d, brief))


def render_md(plan: GrowthPlan, rows: list[dict], dropped: list[str], budget: float) -> str:
    spent = sum(r["cost_usd"] for r in rows if r["fits_budget"])
    lines = ["# Phase 1, step 6: How to market it (the idea was rated strong or promising)", "",
             f"**Positioning:** {plan.positioning_line}", "",
             f"Tactics in order; code kept them within your ${budget:g} budget (planned spend ${spent:g}) and checked every "
             "action against the guard. You post everything yourself; nothing is published by this system.", "",
             "| Channel | Where | This week | Cost | Hours | Measure | Target |", "|---|---|---|---|---|---|---|"]
    lines += [f"| {r['channel']} | {r['where']} | {r['action']} | ${r['cost_usd']:g}{'' if r['fits_budget'] else ' (over budget: skip for now)'} "
              f"| {r['hours']:g} | {r['metric']} | {r['target']} |" for r in rows]
    if dropped:
        lines += ["", "Removed in code:", *[f"- {d}" for d in dropped]]
    lines += ["", "## Avoid", *[f"- {a}" for a in plan.avoid], ""]
    return "\n".join(lines)
