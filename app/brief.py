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
    location: str = Field(default="", description="Where the founder will sell: a country or city (optional)")
    values: list[str] = Field(default_factory=list)
    source_urls: list[str] = Field(default_factory=list, description="Optional sources the founder already has")

    @property
    def signature(self) -> str:
        """The name agents may sign with: the founder's own, or a placeholder. Never an invented name."""
        n = (self.founder_name or "").strip()
        return n if n and n.lower() not in ("founder", "name", "your name") else "[your name]"

    def as_text(self) -> str:
        return (
            f"Idea: {self.idea}\n"
            f"Founder skills: {', '.join(self.skills) or 'not stated'}\n"
            f"Budget: ${self.budget_usd:,.0f}\n"
            f"Time available: {self.hours_per_week:g} hours/week\n"
            f"Target market: {self.target_market}\n"
            + (f"Where the founder will sell: {self.location}\n" if self.location else "")
            + f"Values: {', '.join(self.values) or 'not stated'}"
        )

    def all_text(self) -> str:
        return " ".join([self.idea, self.target_market, *self.skills, *self.values])
