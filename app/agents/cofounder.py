"""Co-founder verdict (end of Phase 1): an honest judgement of the idea, then concrete ways to make it stronger.

The agent reads the founder's brief, the chosen opportunity, the market, the evidence ledger and the evidence
gate, and answers like a candid co-founder: is this strong, promising, weak, or not worth pursuing, why, what
would kill it, and 2-4 specific improvements with the cheapest test for each. It agrees only when the evidence
is strong: `cap_verdict` makes sure, in code, that the verdict is never more positive than the evidence gate.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from app.agents.base import Agent
from app.specificity import problems

VERDICTS = ["do_not_pursue", "weak", "promising", "strong"]  # least to most positive


class Improvement(BaseModel):
    change: str = Field(description="One concrete change to the idea, customer, channel or offer")
    why: str = Field(description="Which weakness it fixes, tied to the evidence or the founder's constraints")
    cheapest_test: str = Field(description="The cheapest way to test it this week, within the founder's budget and hours")


class CofounderVerdict(BaseModel):
    verdict: Literal["strong", "promising", "weak", "do_not_pursue"]
    one_line: str = Field(description="The verdict in one plain sentence, as a co-founder would say it")
    reasons_for: list[str] = Field(description="1-3 reasons it could work, each tied to a source id or the founder's strengths")
    reasons_against: list[str] = Field(description="1-3 reasons it could fail, as specific as the reasons for")
    killer_risk: str = Field(description="The single thing most likely to kill it")
    improvements: list[Improvement] = Field(min_length=2, max_length=4)
    change_my_mind: str = Field(description="The evidence that would move the verdict up or down")


def cap_verdict(v: CofounderVerdict, gate_recommendation: str, best_score: float) -> tuple[CofounderVerdict, str | None]:
    """The verdict may not be more positive than the evidence: go allows any; repeat at most promising; pivot at most
    weak; stop means do_not_pursue. A best opportunity score under 3.5/5 also caps it at promising."""
    ceiling = {"go": "strong", "repeat": "promising", "pivot": "weak", "stop": "do_not_pursue"}.get(gate_recommendation, "weak")
    if best_score < 3.5 and VERDICTS.index(ceiling) > VERDICTS.index("promising"):
        ceiling = "promising"
    if VERDICTS.index(v.verdict) <= VERDICTS.index(ceiling):
        return v, None
    note = (f"Capped in code from {v.verdict.upper()} to {ceiling.upper()}: the evidence gate said "
            f"{gate_recommendation.upper()} and the best opportunity scored {best_score:g}/5.")
    return v.model_copy(update={"verdict": ceiling}), note


class CofounderAgent(Agent):
    role = "cofounder"

    def verdict(self, brief, opp_json: str, market_json: str, ledger_md: str, gate_md: str) -> CofounderVerdict:
        user = (f"FOUNDER BRIEF\n{brief.as_text()}\n\nCHOSEN OPPORTUNITY\n{opp_json}\n\nMARKET\n{market_json}\n\n"
                f"EVIDENCE (claims with sources or ASSUMPTION)\n{ledger_md}\n\nEVIDENCE GATE\n{gate_md}")
        return self.ask("cofounder_verdict", user, CofounderVerdict, critique=lambda d: problems(d, brief))


def render_md(v: CofounderVerdict, cap_note: str | None, opp_name: str) -> str:
    label = {"strong": "STRONG", "promising": "PROMISING", "weak": "WEAK", "do_not_pursue": "DO NOT PURSUE"}[v.verdict]
    lines = [f"# Phase 1, step 4: Co-founder verdict on '{opp_name}'", "",
             f"**Verdict: {label}.** {v.one_line}", ""]
    if cap_note:
        lines += [f"_{cap_note}_", ""]
    lines += ["## Why it could work"] + [f"- {r}" for r in v.reasons_for]
    lines += ["", "## Why it could fail"] + [f"- {r}" for r in v.reasons_against]
    lines += ["", f"**Most likely to kill it:** {v.killer_risk}", "", "## How to make it stronger", "",
              "| Change | Why | Cheapest test this week |", "|---|---|---|"]
    lines += [f"| {i.change} | {i.why} | {i.cheapest_test} |".replace("\n", " ") for i in v.improvements]
    lines += ["", f"**What would change my mind:** {v.change_my_mind}", "",
              "Written by the co-founder agent after the evidence gate. It cannot be more positive than the evidence: "
              "the gate's recommendation caps the verdict in code, and the founder still decides.", ""]
    return "\n".join(lines)
