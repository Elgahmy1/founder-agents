"""Funding scout (end of Phase 1, only for ideas the co-founder rates strong or promising).

Searches free sources for non-dilutive and early-stage support near the founder: grants, accelerators,
competitions, university programs, foundations and sponsors. For each, the agent lists what they fund, a short
history, and which of their criteria this idea meets or misses. Code then keeps it honest:
- the fit percentage is criteria met / criteria checked: a match score, never a probability of being funded;
- a funder whose name appears in no retrieved source is marked UNVERIFIED (check it exists before applying);
- a contact or application link is shown only if it appears in a retrieved source, otherwise "check their site";
- banks, loans and anything that lends money are dropped (no financial products or advice).
The outreach email is a draft for the founder to send personally, queued for approval like every other send.
"""
from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, Field

from app.agents.base import Agent
from app.research import Doc, docs_for_prompt
from app.specificity import problems

LENDING = re.compile(r"\b(bank|loans?|lend\w*|credit|interest rate|microfinance|debt)\b", re.I)


class Funder(BaseModel):
    name: str
    kind: Literal["grant", "accelerator", "competition", "university_program", "foundation", "sponsor"]
    what_they_fund: str
    history: str = Field(description="Brief past history: since when, what kinds of teams they backed, one example if a source names it")
    criteria_met: list[str] = Field(description="Their stated criteria this idea and founder meet")
    criteria_missed: list[str] = Field(description="Their stated criteria this idea or founder does not meet yet")
    apply_via: str = Field(default="", description="Application link or contact email exactly as it appears in a source, else empty")
    source_ids: list[str] = Field(default_factory=list)


class FundingPlan(BaseModel):
    funders: list[Funder] = Field(max_length=6)
    email_to: str = Field(description="Name of the best-fit funder the draft email is for")
    email_subject: str
    email_body: str = Field(description="Short, honest email in the founder's voice: who they are, the problem, the evidence "
                            "so far (including what is unproven), and one clear ask. No promises, no invented traction.")


def score(f: Funder) -> int | None:
    n = len(f.criteria_met) + len(f.criteria_missed)
    return round(100 * len(f.criteria_met) / n) if n else None


def verify(plan: FundingPlan, docs: list[Doc]) -> tuple[list[dict], list[str]]:
    """Rows for the output (with fit %, verified flag and safe contact) and the names dropped as lending."""
    text = " ".join(f"{d.url} {d.title} {d.snippet}" for d in docs).lower()
    by_id = {d.id: f"{d.url} {d.title} {d.snippet}".lower() for d in docs}
    rows, dropped = [], []
    for f in plan.funders:
        if LENDING.search(f"{f.name} {f.what_they_fund}"):
            dropped.append(f.name)
            continue
        words = re.findall(r"[a-z0-9]{4,}", f.name.lower())
        cited = [by_id[i] for i in f.source_ids if i in by_id]
        verified = f.name.lower() in text or bool(words and any(words[0] in c for c in cited))
        contact = f.apply_via if f.apply_via and f.apply_via.lower() in text else ""
        rows.append({**f.model_dump(), "fit": score(f), "verified": verified, "contact": contact})
    rows.sort(key=lambda r: (r["verified"], r["fit"] or 0), reverse=True)
    return rows, dropped


class FundingScoutAgent(Agent):
    role = "funding_scout"

    def plan(self, brief, idea_summary: str, verdict_line: str, docs: list[Doc]) -> FundingPlan:
        user = (f"FOUNDER BRIEF\n{brief.as_text()}\n\nOPPORTUNITY\n{idea_summary}\n\nCO-FOUNDER VERDICT\n{verdict_line}\n\n"
                f"SOURCES (search results about funding near the founder)\n{docs_for_prompt(docs)}")
        return self.ask("find_funding", user, FundingPlan, sources=[d.url for d in docs],
                        critique=lambda d: problems(d, brief))


def render_md(rows: list[dict], dropped: list[str], plan: FundingPlan, location: str) -> str:
    lines = [f"# Phase 1, step 5: Who could fund or sponsor this{(' in ' + location) if location else ''}", "",
             "Grants, accelerators, competitions, university programs, foundations and sponsors found by the funding scout. "
             "**Fit** is the share of each funder's stated criteria this idea meets today, computed in code: it is a match "
             "score, not a probability of being funded. Banks and loans are never suggested.", "",
             "| Funder | Type | Fit | What they fund | History | Meets | Missing | Apply / contact |", "|---|---|---|---|---|---|---|---|"]
    for r in rows:
        name = r["name"] + ("" if r["verified"] else " (UNVERIFIED: not in the retrieved sources, check it exists)")
        fit = f"{r['fit']}%" if r["fit"] is not None else "unknown"
        contact = r["contact"] or "not in the sources: use their official website"
        lines.append(" | ".join(["", name, r["kind"].replace("_", " "), fit, r["what_they_fund"], r["history"],
                                 "; ".join(r["criteria_met"]) or "-", "; ".join(r["criteria_missed"]) or "-", contact, ""]).strip()
                     .replace("\n", " "))
    if not rows:
        lines.append("| none found in the sources | | | | | | | |")
    if dropped:
        lines += ["", f"Dropped (lending is out of scope): {', '.join(dropped)}"]
    lines += ["", f"## Draft email to {plan.email_to} (a draft only: nothing is sent, you send it yourself if you choose)", "",
              f"**Subject:** {plan.email_subject}", "", plan.email_body, ""]
    return "\n".join(lines)
