"""The concrete next step under a gate recommendation, for this founder.

A gate's recommendation (go / repeat / pivot / stop) is computed from fixed thresholds in `app/gates.py`. This
module adds one line under it that turns the recommendation into an action for this founder, in code and from
the run's own data: the founder's weekly hours and budget, the chosen customer, the places the market analysis
found they gather, and the numbers that failed. It never changes the recommendation, and it calls no model.
"""
from __future__ import annotations


def _num(x) -> str:
    x = float(x or 0)
    return f"{x:g}"


def _where(market: dict | None, n: int = 2) -> str:
    places = [p for p in (market or {}).get("where_they_gather", []) if p][:n]
    return " and ".join(places) if places else "the communities where they already talk about it"


def _check(gate: dict, word: str) -> dict | None:
    return next((c for c in gate.get("checks", []) if word in c["name"].lower()), None)


def next_step(gate: dict, brief: dict, market: dict | None = None, customer: str | None = None) -> str:
    """One specific action for the founder under this gate's recommendation."""
    rec, name = gate["recommendation"], gate["gate"]
    hours, budget = _num(brief.get("hours_per_week")), _num(brief.get("budget_usd"))
    who = (customer or (market or {}).get("ideal_customer") or brief.get("target_market") or "your customers").strip().rstrip(".")
    where = _where(market)
    if name == "evidence_gate":
        if rec == "go":
            return (f"Next step for you: before building anything, spend about 3 of your {hours} weekly hours on the Mom Test "
                    f"interviews: book 5 conversations with {who} through {where}, using the script in phase1_step3.")
        if rec == "repeat":
            pain = _check(gate, "pain")
            if pain and not pain["passed"]:
                return (f"Next step for you: only {pain['actual']} retrieved source(s) show the pain, and the target is {pain['target'][3:]}. "
                        f"Find 2 posts where {who} describe this problem in their own words (start with {where}), add their "
                        f"URLs as founder sources and repeat discovery: about 1-2 of your {hours} weekly hours, $0 spent.")
            return (f"Next step for you: add 2-3 founder sources (threads, reviews of the alternatives, course forums) and repeat "
                    f"discovery; about 1-2 of your {hours} weekly hours, $0 spent.")
        if rec == "pivot":
            return (f"Next step for you: keep {who} and the problem, and run discovery on the next-best opportunity. Nothing is "
                    f"built yet, so this costs only discovery time ($0 of your ${budget}).")
        return (f"Next step for you: stop here. You have spent $0 of your ${budget} and none of your build hours; bring a "
                "different idea, or real complaints from your customers as founder sources, to a new run.")
    if name == "demand_gate":
        sign, inter, conf = _check(gate, "sign-up"), _check(gate, "interviews completed"), _check(gate, "confirming")
        got = f"{sign['actual']} sign-ups against {sign['target'][3:]}" if sign else "the sign-ups"
        if rec == "go":
            return (f"Next step for you: build. Scope the MVP to what fits {_num(float(hours) * 4)} hours (4 weeks at {hours} "
                    "hours) and start with the story the interviewees named most.")
        if rec == "repeat":
            return (f"Next step for you: run the same test once more without changing the targets ({got} so far); post the "
                    f"landing page in {where} and book the missing interviews, within your {hours} weekly hours.")
        if rec == "pivot":
            return (f"Next step for you: the problem is confirmed but {got}. Change one thing and re-test for 7 days with the "
                    f"same targets: the audience, the channel (try {where}) or the offer (show one finished example of the "
                    "output on the landing page). Do not build yet.")
        return (f"Next step for you: stop. {got}"
                + (f" and {conf['actual']} of interviewees confirming the problem" if conf else "")
                + f" is the answer. You have spent $0 of your ${budget}; keep your {hours} weekly hours for the next idea.")
    if name == "learn_gate":
        visits, sign = _check(gate, "visits"), _check(gate, "sign-ups")
        got = (f"{visits['actual']} store visits and {sign['actual']} sign-ups against targets of {visits['target'][3:]} and "
               f"{sign['target'][3:]}") if visits and sign else "the launch results"
        if rec == "go":
            return f"Next step for you: persevere. Keep the same {hours} weekly hours on the channel that brought the sign-ups."
        if rec == "repeat":
            return (f"Next step for you: run one more window with the same targets ({got} so far) and post in {where} "
                    "before deciding.")
        if rec == "pivot":
            return (f"Next step for you: go back to Discover with what users wrote; {got}. Keep {who} and test a different "
                    "angle on their problem.")
        return (f"Next step for you: stop operating this product: {got}. Keep the learning memo, and put your {hours} weekly "
                "hours into the next idea's discovery.")
    return ""
