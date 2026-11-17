"""Phase 6 agents (Operate and learn).

support: drafts a reply to each piece of real user feedback the founder pastes in.
Replies are `send` approval items the founder sends personally (MOCKED sending).
analyst (app/agents/analyst.py) writes the learning memo after the learn gate,
which is computed in code (app/gates.py: learn_gate) and cannot be changed by the memo.
"""
from __future__ import annotations

from pydantic import BaseModel, Field

from app.agents.base import Agent


class Reply(BaseModel):
    feedback: str = Field(description="The feedback being answered, quoted exactly")
    category: str = Field(description="bug | confusion | feature request | praise | pricing | other")
    reply: str = Field(description="Short, honest reply signed with the founder name given")
    product_change: str = Field(description="What this suggests changing, or 'none'")


class SupportDrafts(BaseModel):
    replies: list[Reply]


class SupportAgent(Agent):
    role = "support"

    def draft_replies(self, product: str, signature: str, feedback: list[str]) -> SupportDrafts:
        user = (f"PRODUCT\n{product}\n\nFOUNDER NAME (sign with exactly this)\n{signature}\n\n"
                "USER FEEDBACK (one item per line, written by real users)\n" + "\n".join(f"- {f}" for f in feedback))
        return self.ask("draft_support_replies", user, SupportDrafts)
