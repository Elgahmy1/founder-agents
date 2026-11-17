from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TypeVar

from pydantic import BaseModel

from app.decision_log import DecisionLog
from app.llm import LLM

T = TypeVar("T", bound=BaseModel)


@dataclass
class AgentContext:
    llm: LLM
    log: DecisionLog
    prompts_dir: Path
    run_id: str


class Agent:
    role: str = "agent"

    def __init__(self, ctx: AgentContext):
        self.ctx = ctx

    def system_prompt(self) -> str:
        policy = (self.ctx.prompts_dir / "policy.md").read_text()
        own = (self.ctx.prompts_dir / f"{self.role}.md").read_text()
        return f"{own}\n\n{policy}"

    def ask(self, action: str, user: str, schema: type[T], sources: list[str] | None = None) -> T:
        before = self.ctx.llm.usage.total_tokens
        out = self.ctx.llm.structured(self.system_prompt(), user, schema)
        self.ctx.log.append(
            agent=self.role,
            action=action,
            sources=sources or [],
            model=self.ctx.llm.model,
            cost=0,
            run_id=self.ctx.run_id,
            tokens=self.ctx.llm.usage.total_tokens - before,
        )
        return out
