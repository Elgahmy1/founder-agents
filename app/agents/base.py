from __future__ import annotations

from dataclasses import dataclass, field
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
    usage: dict = field(default_factory=dict)  # this run's running totals, saved with the run


class Agent:
    role: str = "agent"

    def __init__(self, ctx: AgentContext):
        self.ctx = ctx

    def system_prompt(self) -> str:
        policy = (self.ctx.prompts_dir / "policy.md").read_text(encoding="utf-8")
        own = (self.ctx.prompts_dir / f"{self.role}.md").read_text(encoding="utf-8")
        return f"{own}\n\n{policy}"

    def ask(self, action: str, user: str, schema: type[T], sources: list[str] | None = None,
            critique=None) -> T:
        """One model call. With `critique` (draft -> list of problems, see app/specificity.py), a draft that has
        problems gets one redraft with the problems listed; the check is logged as `specificity_check`."""
        out = self._ask_once(action, user, schema, sources)
        if critique is None:
            return out
        found = critique(out)
        if found:
            fix = "\n".join(f"- {p}" for p in found)
            out = self._ask_once(f"redraft_{action}", f"{user}\n\nYOUR LAST DRAFT WAS TOO GENERIC. Fix these and keep "
                                 f"everything that was specific:\n{fix}", schema, sources)
            left = critique(out)
        else:
            left = []
        self.ctx.log.append(agent="critic", action="specificity_check", sources=[], model=None, cost=0,
                            run_id=self.ctx.run_id, outcome=("pass" if not found else "redrafted" if not left
                                                             else "redrafted_with_problems_left"),
                            detail="; ".join(found + [f"still: {p}" for p in left])[:1500] or "no generic advice found",
                            checked=action)
        return out

    def _ask_once(self, action: str, user: str, schema: type[T], sources: list[str] | None = None) -> T:
        u = self.ctx.llm.usage
        before = (u.calls, u.prompt_tokens, u.completion_tokens, u.cost_usd)
        out = self.ctx.llm.structured(self.system_prompt(), user, schema)
        for k, b, now in zip(("calls", "prompt_tokens", "completion_tokens", "cost_usd"), before,
                             (u.calls, u.prompt_tokens, u.completion_tokens, u.cost_usd)):
            self.ctx.usage[k] = (self.ctx.usage.get(k) or 0) + now - b
        self.ctx.log.append(
            agent=self.role,
            action=action,
            sources=sources or [],
            model=self.ctx.llm.model,
            cost=0,
            run_id=self.ctx.run_id,
            tokens=u.prompt_tokens + u.completion_tokens - before[1] - before[2],
        )
        return out
