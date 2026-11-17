"""Market analyst (Phase 1): defines the market for the chosen opportunity."""
from __future__ import annotations

from pydantic import BaseModel, Field

from app.agents.base import Agent
from app.specificity import problems
from app.agents.scout import Opportunity
from app.brief import FounderBrief
from app.evidence import RawClaim
from app.research import Doc, docs_for_prompt


class Market(BaseModel):
    ideal_customer: str
    segments: list[str]
    where_they_gather: list[str] = Field(description="Communities/channels where these customers can be reached")
    alternatives: list[str]
    claims: list[RawClaim]
    unknowns: list[str] = Field(description="What we do not know yet and must learn in interviews")
    counter_evidence: list[RawClaim] = Field(default_factory=list, description="1-3 strongest points AGAINST this "
                                             "opportunity (a free alternative that already works, complaints, a failed "
                                             "predecessor, people unwilling to pay), citing source IDs where possible")


class MarketAnalystAgent(Agent):
    role = "market_analyst"

    def define_market(self, brief: FounderBrief, opp: Opportunity, docs: list[Doc]) -> Market:
        user = (
            f"FOUNDER BRIEF\n{brief.as_text()}\n\nCHOSEN OPPORTUNITY\n{opp.model_dump_json(indent=1)}\n\n"
            f"SOURCES\n{docs_for_prompt(docs)}"
        )
        return self.ask("define_market", user, Market, sources=[d.url for d in docs],
                        critique=lambda d: problems(d, brief) + ([] if d.counter_evidence else [
                            "counter_evidence is empty: add the strongest evidence AGAINST this opportunity from the "
                            "sources (cite its source ID), or state it as an assumption with no source ID."]))
