"""Builder (Phase 3, core step: Build the product).

Turns the validated Lean Canvas into a scoped MVP: user stories with testable
acceptance criteria, must-have features with hour estimates, and the screens
of a clickable prototype. The model writes structured content only; our
template renders the prototype (app/prototype.py) and code checks it
(app/gates.py: build_gate) before the founder sees a release candidate.
"""
from __future__ import annotations

from app import carry as carry_mod
from app.carry import CarryAnswer
from pydantic import BaseModel, Field

from app.agents.base import Agent
from app.specificity import problems
from app.agents.scout import Opportunity
from app.agents.strategist import LeanCanvas
from app.brief import FounderBrief


class UserStory(BaseModel):
    id: str = Field(description="US1, US2, ...")
    as_a: str
    i_want: str
    so_that: str
    acceptance: list[str] = Field(min_length=1, description="Observable, testable checks: 'Given ... when ... then ...'")


class Feature(BaseModel):
    name: str
    description: str
    story_ids: list[str] = Field(description="User stories this feature serves")
    estimate_hours: float = Field(gt=0, le=200)


class Screen(BaseModel):
    title: str
    purpose: str
    inputs: list[str] = Field(default_factory=list, description="Field labels the user fills in; never passwords or payment data")
    action: str = Field(description="Button label")
    sample_output: str = Field(description="Illustrative result shown after the action, clearly fictional")


class MvpSpec(BaseModel):
    product_name: str
    one_line: str
    user_stories: list[UserStory] = Field(min_length=1, max_length=6)
    must_have: list[Feature] = Field(min_length=1, max_length=8)
    out_of_scope: list[str] = Field(description="Deliberately left out of the MVP")
    screens: list[Screen] = Field(min_length=1, max_length=4)
    tech_stack: list[str] = Field(description="Free, open-source tools only")
    risks: list[str]
    carried_forward: list[CarryAnswer] = Field(default_factory=list, description="One answer per carried-forward item, if any")


class BuilderAgent(Agent):
    role = "builder"

    def mvp_spec(self, brief: FounderBrief, opp: Opportunity, canvas: LeanCanvas, feedback: str | None = None,
                 carry: list[dict] | None = None) -> MvpSpec:
        user = (
            f"FOUNDER BRIEF\n{brief.as_text()}\n\nOPPORTUNITY\n{opp.model_dump_json(indent=1)}\n\n"
            f"LEAN CANVAS\n{canvas.model_dump_json(indent=1, exclude={'claims'})}\n\n"
            f"BUILD BUDGET: {brief.hours_per_week} hours per week for 4 weeks = {brief.hours_per_week * 4:g} hours; "
            f"cash budget ${brief.budget_usd:g}."
        )
        if feedback:
            user += f"\n\nFEEDBACK FROM THE LAST BUILD GATE (fix these)\n{feedback}"
        user += carry_mod.prompt_block(carry or [])
        return self.ask("write_mvp_spec", user, MvpSpec,
                        critique=lambda d: problems(d, brief) + carry_mod.check(d, carry or []))
