"""Advisor: answers the founder's free-text requests, after the guard."""
from __future__ import annotations

from pydantic import BaseModel

from app.agents.base import Agent
from app.specificity import problems


class Advice(BaseModel):
    answer: str


class AdvisorAgent(Agent):
    role = "advisor"

    def answer(self, context: str, request: str) -> Advice:
        return self.ask("answer_founder_request", f"RUN CONTEXT\n{context}\n\nFOUNDER REQUEST\n{request}", Advice,
                        critique=lambda d: problems(d))
