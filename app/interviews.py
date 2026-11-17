"""Phase 2: real customer interviews, analysed and checked in code.

`verify` keeps only quotes that appear in the transcript (ignoring case, spacing and punctuation differences),
so the analysis cannot attribute invented words to a customer, and it does not let a "problem confirmed"
verdict stand without at least one verified evidence quote. `render_md` writes the Phase 2 interview output.
Transcripts stay in the run's state under data/ (never in outputs/); the output file holds only short quotes.
"""
from __future__ import annotations

import re
import unicodedata

from app.agents.interview_analyst import InterviewAnalysis


def _norm(text: str) -> str:
    text = unicodedata.normalize("NFKC", text or "").lower()
    text = re.sub(r"[ً-ْـ]", "", text)  # Arabic diacritics and tatweel
    text = re.sub(r"[^\w\s]", " ", text)
    return " ".join(text.split())


def verify(analysis: InterviewAnalysis, transcript: str) -> tuple[InterviewAnalysis, list[str]]:
    """Drop quotes that are not in the transcript; a confirmation needs at least one verified quote."""
    t = _norm(transcript)
    dropped: list[str] = []

    def keep(items):
        out = []
        for e in items:
            q = _norm(e.quote)
            if q and len(q.split()) >= 2 and q in t:
                out.append(e)
            else:
                dropped.append(e.quote)
        return out

    a = analysis.model_copy(update={"evidence": keep(analysis.evidence), "red_flags": keep(analysis.red_flags)})
    if a.problem_confirmed and not a.evidence:
        a = a.model_copy(update={"problem_confirmed": False,
                                 "why": a.why + " (Set to not confirmed in code: no evidence quote was found in the transcript.)"})
    return a, dropped


def summary(interviews: list[dict]) -> tuple[int, int]:
    """(interviews analysed, interviews confirming the problem)."""
    return len(interviews), sum(1 for i in interviews if i["analysis"]["problem_confirmed"])


def render_md(interviews: list[dict], plan: dict) -> str:
    done, confirmed = summary(interviews)
    lines = ["# Phase 2, step 4: Customer interviews, analysed", "",
             f"Rule from the interview plan: problem confirmed if {plan.get('pain_confirmed_if', '')}", "",
             f"**{confirmed} of {done} interview(s) confirm the problem.** Each verdict below was made by the interview "
             "analyst agent and every quote was checked in code against the transcript; quotes that were not in the "
             "transcript were dropped. Transcripts are kept on the founder's computer (data/), not in this file.", ""]
    for i, item in enumerate(interviews, 1):
        a = item["analysis"]
        lines += [f"## Interview {i} ({item['source']}, {a['language']}): "
                  + ("problem CONFIRMED" if a["problem_confirmed"] else "problem NOT confirmed"), "",
                  f"- Why: {a['why']}", f"- What they do today: {a['current_workaround']}",
                  f"- What it costs them: {a['cost_of_problem']}", f"- Commitment: {a['commitment']}",
                  f"- Surprise: {a['surprise']}", "", "Evidence (verified quotes):"]
        lines += [f"- \"{e['quote']}\": {e['shows']}" for e in a["evidence"]] or ["- none"]
        if a["red_flags"]:
            lines += ["", "Does not count as evidence:"] + [f"- \"{e['quote']}\": {e['shows']}" for e in a["red_flags"]]
        if item.get("dropped"):
            lines += ["", f"Quotes dropped because they were not in the transcript: {len(item['dropped'])}"]
        lines += ["", "Ask next time:"] + [f"- {q}" for q in a["ask_next_time"]] + [""]
    return "\n".join(lines)
