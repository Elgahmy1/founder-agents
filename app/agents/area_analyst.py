"""Area check (first step of Phase 1): will this idea work where the founder wants to sell it?

Given the founder's location (a country or city) and the sources the researcher found, including searches
aimed at that place, the agent judges local fit, whether what the product needs is available there (language,
content, internet access, tools, the people to reach), and where the idea would stand among local and global
competitors. Every factual claim goes through the evidence ledger; `cap_fit` keeps the verdict at "unknown"
when no retrieved source says anything about the place, so a guess never reads as a finding.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from app.agents.base import Agent
from app.evidence import RawClaim
from app.research import Doc, docs_for_prompt
from app.specificity import problems


class Resource(BaseModel):
    need: str = Field(description="Something the product or its customers need in this place (language support, content, internet access, a tool, a channel)")
    available: Literal["yes", "partly", "no", "unknown"]
    note: str = Field(description="What makes it available or not there, citing a source id when one supports it")


class Competitor(BaseModel):
    name: str
    where: Literal["local", "regional", "global"]
    offer: str = Field(description="What they offer to these customers in this place")
    gap: str = Field(description="What they leave open that this idea could take, or 'none'")


class AreaCheck(BaseModel):
    location: str
    fit: Literal["good", "mixed", "poor", "unknown"]
    why: str = Field(description="Two or three sentences on why the idea fits or not in this place, specific to it")
    local_factors: list[str] = Field(description="2-5 facts about this place that change the plan (language, habits, seasons, institutions, access)")
    resources: list[Resource] = Field(min_length=2, max_length=6)
    competitors: list[Competitor] = Field(max_length=6)
    positioning: str = Field(description="Where this idea would stand among those competitors, and the gap it would take")
    claims: list[RawClaim] = Field(description="Factual statements about this place, its customers or competitors, with source ids only where supported")


def cap_fit(area: AreaCheck, sourced_claims: int) -> tuple[AreaCheck, str | None]:
    """Without a single retrieved source about the place, the fit is 'unknown', whatever the model said."""
    if sourced_claims == 0 and area.fit != "unknown":
        return area.model_copy(update={"fit": "unknown"}), (
            f"Set to UNKNOWN in code (the model said {area.fit.upper()}): no retrieved source supports a claim about "
            f"{area.location}. Add local sources or ask local customers before relying on it.")
    return area, None


class AreaAnalystAgent(Agent):
    role = "area_analyst"

    def check(self, brief, docs: list[Doc]) -> AreaCheck:
        user = (f"FOUNDER BRIEF\n{brief.as_text()}\n\nWHERE THE FOUNDER WILL SELL: {brief.location}\n\n"
                f"SOURCES\n{docs_for_prompt(docs)}")
        return self.ask("check_area", user, AreaCheck, sources=[d.url for d in docs],
                        critique=lambda d: problems(d, brief))


def render_md(a: AreaCheck, claims_md: list[str], cap_note: str | None) -> str:
    lines = [f"# Phase 1, step 0: Area check: will this work in {a.location}?", "",
             f"**Local fit: {a.fit.upper()}.** {a.why}", ""]
    if cap_note:
        lines += [f"_{cap_note}_", ""]
    lines += ["## What is different about this place"] + [f"- {f}" for f in a.local_factors]
    lines += ["", "## Is what the product needs available here?", "", "| Need | Available | Why |", "|---|---|---|"]
    lines += [f"| {r.need} | {r.available} | {r.note} |".replace("\n", " ") for r in a.resources]
    lines += ["", "## Competitors and where this idea would stand", "", "| Competitor | Where | What they offer | Gap they leave |",
              "|---|---|---|---|"]
    lines += [f"| {c.name} | {c.where} | {c.offer} | {c.gap} |".replace("\n", " ") for c in a.competitors] or ["| none found | | | |"]
    lines += ["", f"**Positioning:** {a.positioning}", "", "## Claims", *[f"- {c}" for c in claims_md], ""]
    return "\n".join(lines)
