"""Researcher: turns the brief into search queries and gathers free sources."""
from __future__ import annotations

from pydantic import BaseModel, Field

from app.agents.base import Agent
from app.brief import FounderBrief
from app.research import Doc, Researcher


class QueryPlan(BaseModel):
    queries: list[str] = Field(description="3 short web search queries that would surface real people describing this problem")


class ResearcherAgent(Agent):
    role = "researcher"

    def gather(self, brief: FounderBrief, tool: Researcher) -> list[Doc]:
        plan = self.ask("plan_research_queries", brief.as_text(), QueryPlan)
        queries = [q for q in plan.queries if q.strip()][:3] or [brief.idea[:80]]
        docs = tool.gather(queries, brief.source_urls)
        self.ctx.log.append(
            agent=self.role, action="gather_sources", sources=[d.url for d in docs], model=None, cost=0,
            run_id=self.ctx.run_id, queries=queries, errors=tool.errors[:6], source_count=len(docs),
        )
        return docs
