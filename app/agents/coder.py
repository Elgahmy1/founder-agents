"""Coder (Phase 3, step 4: write and test the MVP's core code).

Writes small, pure Python functions for every user story in the MVP spec and one executable check per
acceptance criterion; a criterion that needs storage, a UI or hosting is listed as deferred with a reason instead. The code runs only in app/sandbox.py (static allowlist + isolated process); it is never published,
deployed or run with network access. If checks fail, the coder gets one repair attempt with the failures.
"""
from __future__ import annotations

from pydantic import BaseModel, Field

from app.agents.base import Agent


class AcceptanceCheck(BaseModel):
    story_id: str
    criterion: str = Field(description="The acceptance criterion, quoted from the spec")
    code: str = Field(description="Python statements with assert, calling functions defined in the module")


class DeferredCriterion(BaseModel):
    story_id: str
    criterion: str = Field(description="The acceptance criterion, quoted from the spec")
    reason: str = Field(description="Why pure code cannot check it (needs storage, a user interface, hosting or a model)")


class CodeDraft(BaseModel):
    module_code: str = Field(description="Self-contained Python module: pure functions, standard library only")
    checks: list[AcceptanceCheck] = Field(min_length=1, max_length=14)
    deferred: list[DeferredCriterion] = Field(default_factory=list, max_length=8)
    notes: str = Field(description="What is implemented, and what is deliberately left for later (UI, storage, hosting)")


class CoderAgent(Agent):
    role = "coder"

    def write_core(self, spec_json: str, feedback: str | None = None) -> CodeDraft:
        user = f"MVP SPEC\n{spec_json}"
        if feedback:
            user += f"\n\nYOUR LAST ATTEMPT FAILED IN THE SANDBOX (fix these)\n{feedback}"
        return self.ask("write_mvp_core_code" if not feedback else "repair_mvp_core_code", user, CodeDraft)
