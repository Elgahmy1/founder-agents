from __future__ import annotations

from pydantic import BaseModel, Field


class FounderBrief(BaseModel):
    """The founder's short brief: a starting idea plus constraints."""
    founder_name: str = Field(default="Founder")
    idea: str
    skills: list[str] = Field(default_factory=list)
    budget_usd: float = 0
    hours_per_week: float = 10
    target_market: str
    values: list[str] = Field(default_factory=list)
    source_urls: list[str] = Field(default_factory=list, description="Optional sources the founder already has")

    def as_text(self) -> str:
        return (
            f"Idea: {self.idea}\n"
            f"Founder skills: {', '.join(self.skills) or 'not stated'}\n"
            f"Budget: ${self.budget_usd:,.0f}\n"
            f"Time available: {self.hours_per_week:g} hours/week\n"
            f"Target market: {self.target_market}\n"
            f"Values: {', '.join(self.values) or 'not stated'}"
        )

    def all_text(self) -> str:
        return " ".join([self.idea, self.target_market, *self.skills, *self.values])
