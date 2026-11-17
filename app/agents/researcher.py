"""Researcher: turns the brief into search queries and gathers free sources."""
from __future__ import annotations

from pydantic import BaseModel, Field

from app.agents.base import Agent
from app.brief import FounderBrief
from app.research import Doc, Researcher


class QueryPlan(BaseModel):
    queries: list[str] = Field(description="3 short ENGLISH web search queries that would surface real people describing "
                                           "this problem; translate if the brief is in another language")
    counter_queries: list[str] = Field(default_factory=list, description="2 short ENGLISH queries that would find evidence "
                                       "AGAINST this idea: free alternatives people already use, complaints, failed predecessors")
    area_queries: list[str] = Field(default_factory=list, description="Only if the brief says where the founder will sell: "
                                    "2 short queries about that place (competitors there, how these customers there solve it)")


class ResearcherAgent(Agent):
    role = "researcher"

    def gather(self, brief: FounderBrief, tool: Researcher) -> list[Doc]:
        plan = self.ask("plan_research_queries", brief.as_text(), QueryPlan)
        queries = [q for q in plan.queries if q.strip()][:3] or [brief.idea[:80]]
        if brief.location:
            queries += [q for q in plan.area_queries if q.strip()][:2] or [f"{brief.target_market} {brief.location} {brief.idea[:40]}"]
        # Disconfirming pass: always look for what argues against the idea, not only for support.
        queries += [q for q in plan.counter_queries if q.strip()][:2] or [f"{brief.idea[:50]} free alternative",
                                                                         f"{brief.idea[:50]} failed startup"]
        docs = tool.gather(queries, brief.source_urls)
        self.ctx.log.append(
            agent=self.role, action="gather_sources", sources=[d.url for d in docs], model=None, cost=0,
            run_id=self.ctx.run_id, queries=queries, errors=tool.errors[:6], source_count=len(docs),
        )
        return docs
