"""Analyst (Phase 2): proposes demand-test targets BEFORE the test runs, and
writes the gate memo. The gate outcome itself is computed in app/gates.py."""
from __future__ import annotations

from pydantic import BaseModel, Field

from app.agents.base import Agent
from app.agents.strategist import LeanCanvas
from app.brief import FounderBrief


class DemandTestPlan(BaseModel):
    hypothesis: str
    waitlist_signups_target: int = Field(ge=5, le=1000)
    window_days: int = Field(ge=3, le=30)
    interviews_target: int = Field(ge=5, le=30)
    pain_confirm_rate_target: float = Field(ge=0.3, le=0.9)
    channels: list[str]
    rationale: str = Field(description="Why these targets; label any benchmark without a source as an assumption")


class GateMemo(BaseModel):
    summary: str
    what_we_learned: list[str]
    next_steps: list[str]


class AnalystAgent(Agent):
    role = "analyst"

    def demand_test(self, brief: FounderBrief, canvas: LeanCanvas) -> DemandTestPlan:
        user = f"FOUNDER BRIEF\n{brief.as_text()}\n\nLEAN CANVAS\n{canvas.model_dump_json(indent=1)}"
        return self.ask("set_demand_targets", user, DemandTestPlan)

    def gate_memo(self, gate_md: str) -> GateMemo:
        return self.ask("write_gate_memo", f"GATE RESULT (do not change the recommendation)\n{gate_md}", GateMemo)
