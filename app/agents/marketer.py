"""Marketer (Phase 2): landing-page copy for a demand test.

The model writes copy only. The HTML is rendered by our own template, so the
page cannot contain scripts, timers, testimonials or payment fields.
"""
from __future__ import annotations

from pydantic import BaseModel, Field

from app.agents.base import Agent
from app.agents.strategist import LeanCanvas


class LandingCopy(BaseModel):
    headline: str
    subheadline: str
    bullets: list[str] = Field(min_length=2, max_length=5)
    call_to_action: str = Field(description="Button text for joining a waitlist, e.g. 'Join the waitlist'")
    honesty_note: str = Field(description="One line telling visitors this is an early-stage product being tested")


class MarketerAgent(Agent):
    role = "marketer"

    def landing_copy(self, canvas: LeanCanvas, product_name: str) -> LandingCopy:
        user = f"PRODUCT NAME: {product_name}\nLEAN CANVAS\n{canvas.model_dump_json(indent=1)}"
        return self.ask("write_landing_copy", user, LandingCopy)
