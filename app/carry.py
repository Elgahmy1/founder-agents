"""Risk and evidence carried forward between phases.

What earlier phases learned must change what later phases produce. The co-founder's killer risk and suggested
changes (Phase 1), the area check's positioning (Phase 1) and the verified quotes and red flags from real interviews
(Phase 2) are handed to the Lean Canvas (Phase 2) and the MVP spec (Phase 3). Each of those drafts must say, item by
item, how it addresses what was carried forward; code checks that every item got a concrete answer and sends the
draft back once if not (the same critique loop as the specificity critic). The answers are written into the outputs
under "Risk and evidence carried forward".
"""
from __future__ import annotations

from pydantic import BaseModel, Field


class CarryAnswer(BaseModel):
    item: str = Field(description="The carried-forward item, copied as given")
    how_addressed: str = Field(description="What in THIS draft changes because of it (a box, a story, a feature, a cut), "
                               "or why it is deliberately not addressed yet and what would test it")


def collect(st, *, with_interviews: bool) -> list[dict]:
    """Items to carry, each {'item', 'from'}. Only verified material: interview quotes were checked in code."""
    out: list[dict] = []
    v = getattr(st, "verdict", None)
    if v:
        out.append({"item": f"Killer risk: {v['killer_risk']}", "from": "phase1_step4_cofounder_verdict"})
        for i in v.get("improvements", [])[:2]:
            out.append({"item": f"Suggested change: {i['change']}", "from": "phase1_step4_cofounder_verdict"})
    a = getattr(st, "area", None)
    if a and a.get("positioning"):
        out.append({"item": f"Local positioning ({a.get('location', '')}): {a['positioning']}", "from": "phase1_step0_area_check"})
    if with_interviews:
        for n, iv in enumerate(getattr(st, "interviews", None) or [], 1):
            an = iv["analysis"]
            for e in an.get("red_flags", [])[:1]:
                out.append({"item": f"Objection or red flag (interview {n}): \"{e['quote']}\"", "from": "phase2_step4_interviews"})
            if an.get("current_workaround") and an["current_workaround"] != "not said":
                out.append({"item": f"Current workaround (interview {n}): {an['current_workaround']}", "from": "phase2_step4_interviews"})
    return out[:8]


def prompt_block(items: list[dict]) -> str:
    if not items:
        return ""
    lines = "\n".join(f"- {i['item']}" for i in items)
    return ("\n\nCARRIED FORWARD FROM EARLIER PHASES (answer every item in `carried_forward`: say what in this draft "
            f"changes because of it; do not just restate it)\n{lines}")


def check(draft, items: list[dict]) -> list[str]:
    """Problems for the redraft: carried items that got no answer, or an answer that only repeats the item."""
    if not items:
        return []
    answers = {a.item.strip().lower()[:40]: a.how_addressed for a in getattr(draft, "carried_forward", []) or []}
    out = []
    for i in items:
        key = i["item"].strip().lower()[:40]
        ans = next((v for k, v in answers.items() if k[:25] == key[:25]), "")
        if len(ans.split()) < 6 or ans.strip().lower() in i["item"].lower():
            out.append(f"Carried-forward item not addressed: \"{i['item']}\". In `carried_forward`, copy it as `item` and "
                       "say concretely what in this draft changes because of it.")
    return out


def render(items: list[dict], draft) -> list[str]:
    if not items:
        return []
    answers = {a.item.strip().lower()[:25]: a.how_addressed for a in getattr(draft, "carried_forward", []) or []}
    rows = [f"| {i['item']} | `{i['from']}` | {answers.get(i['item'].strip().lower()[:25], '**not addressed**')} |"
            for i in items]
    return ["", "## Risk and evidence carried forward", "",
            "What earlier phases found, and what this step changed because of it (checked in code: every item needs an answer).",
            "", "| Carried forward | From | How this step addresses it |", "|---|---|---|", *rows]
