"""Specificity critic: rejects generic advice before a founder sees it.

A draft from a key agent (opportunities, market, Lean Canvas, MVP spec, pricing, launch kit) is checked in
code, not by a model, for two things:

1. Stock advice that would fit any startup ("leverage social media", "build a strong brand",
   "focus on user experience", ...). Each phrase must be replaced by a concrete action for this founder.
2. No use of the founder's own constraints: a draft that never mentions the founder's budget, weekly hours,
   skills or target market was not written for this founder.

For opportunities it also requires the strongest alternative customers use today (including free,
general-purpose AI assistants where they apply) and why a customer would switch from it.

If a draft has problems, the agent gets one redraft with the problems listed (`Agent.ask(critique=...)`), and
the result is logged as `specificity_check`, including any problem the redraft did not fix.
"""
from __future__ import annotations

import re

from pydantic import BaseModel

# Stock phrases that carry no decision for this founder. Matched case-insensitively.
GENERIC_PHRASES = [
    r"leverag\w* social media", r"use social media (marketing|to promote)", r"build(ing)? a strong brand",
    r"focus(ing)? on (the )?user experience", r"create (engaging|high[- ]quality|valuable) content",
    r"build(ing)? a (strong |loyal )?community", r"stand out from (the )?competit\w*", r"word[- ]of[- ]mouth marketing",
    r"seamless (user )?experience", r"user[- ]friendly interface", r"cutting[- ]edge", r"game[- ]chang\w*",
    r"revolutioni[sz]\w*", r"one[- ]stop[- ]shop", r"in today'?s (fast[- ]paced|digital|competitive)",
    r"(boost|increase|drive) (brand )?(awareness|engagement)", r"leverag\w* (ai|technology|data) to",
    r"(various|multiple) (channels|platforms|strategies)", r"best[- ]in[- ]class", r"state[- ]of[- ]the[- ]art",
    r"partner(ships)? with (influencers|universities|companies)\b(?![^.]{0,60}\d)",
]
_GENERIC = [re.compile(p, re.I) for p in GENERIC_PHRASES]


def _texts(obj) -> list[str]:
    """Every string value in a model (or nested lists and dicts)."""
    if isinstance(obj, BaseModel):
        obj = obj.model_dump()
    if isinstance(obj, str):
        return [obj]
    if isinstance(obj, dict):
        return [t for v in obj.values() for t in _texts(v)]
    if isinstance(obj, (list, tuple)):
        return [t for v in obj for t in _texts(v)]
    return []


def brief_facts(brief) -> list[str]:
    """Lower-cased facts from the founder brief a specific draft would use."""
    facts: list[str] = []
    if getattr(brief, "budget_usd", 0):
        b = int(brief.budget_usd)
        facts += [f"${b}", f"{b} usd", f"{b} dollars", f"${b:,}"]
    if getattr(brief, "hours_per_week", 0):
        h = brief.hours_per_week
        h = int(h) if float(h).is_integer() else h
        facts += [f"{h} hours", f"{h} h/week", f"{h}h/week", f"{h} hrs", f"{h}-hour", f"{h} hours/week", f"{h} hours per week"]
    for s in getattr(brief, "skills", []) or []:
        facts += [w for w in re.findall(r"[a-z][a-z0-9+#./-]{2,}", s.lower()) if w not in ("and", "the", "web", "apps")]
    market = (getattr(brief, "target_market", "") or "").lower()
    facts += [w for w in re.findall(r"[a-z]{4,}", market)]
    return sorted(set(facts))


def problems(draft, brief=None, *, need_alternative: bool = False) -> list[str]:
    """What makes this draft generic, as instructions the agent can act on. Empty list: specific enough."""
    texts = _texts(draft)
    blob = "\n".join(texts)
    low = blob.lower()
    out: list[str] = []
    seen: set[str] = set()
    for rx in _GENERIC:
        m = rx.search(blob)
        if m and m.group(0).lower() not in seen:
            seen.add(m.group(0).lower())
            out.append(f"Generic phrase \"{m.group(0)}\": replace it with a concrete action for this founder "
                       "(who exactly, where, how many, by when, within the budget and hours).")
    if brief is not None:
        facts = brief_facts(brief)
        if facts and not any(f in low for f in facts):
            out.append("The draft never uses the founder's constraints. Tie the recommendations to the founder's budget "
                       f"(${int(getattr(brief, 'budget_usd', 0) or 0)}), weekly hours ({getattr(brief, 'hours_per_week', '')}), "
                       "skills and target market where they change the answer.")
    if need_alternative:
        for o in (draft.model_dump().get("opportunities", []) if isinstance(draft, BaseModel) else []):
            if not (o.get("strongest_alternative") or "").strip() or not (o.get("why_switch") or "").strip():
                out.append(f"Opportunity \"{o.get('name', '')}\": name the strongest alternative customers use today "
                           "(include free general-purpose AI assistants such as ChatGPT or Gemini if people could use them "
                           "for this) in `strongest_alternative`, and in `why_switch` the concrete reason a customer would "
                           "switch from it, or say plainly that they would not.")
    return out
