"""Team planner: which roles this business needs, when, and where the founder can find people looking for that work.

The agent proposes roles from the run's own context (idea, MVP spec, launch kit, budget, hours, skills). Code then:
- marks a role "founder" when the founder's stated skills already cover it (no hire for what they can do);
- moves paid hires that the budget cannot carry to "freelancer" or "later";
- builds search links (LinkedIn people who are open to work, Upwork, Mostaql, Wuzzuf) from the role and the location.
The system never scrapes profiles, stores names or contacts anyone: the founder opens the links and decides.
The job post is a draft that passes the guard; the founder posts it personally.
"""
from __future__ import annotations

from typing import Literal
from urllib.parse import quote_plus

from pydantic import BaseModel, Field

from app.agents.base import Agent
from app.specificity import problems


class Role(BaseModel):
    title: str = Field(description="Common job title people search for, e.g. 'UI/UX designer', 'growth marketer'")
    why: str = Field(description="What in THIS business needs this role (a specific task from the run), not a generic reason")
    when: Literal["now", "after_validation", "after_launch"]
    hours_per_week: float
    how: Literal["founder", "freelancer", "part_time", "co_founder", "later"]
    skills: list[str] = Field(description="2-4 concrete skills to look for")


class TeamPlan(BaseModel):
    roles: list[Role] = Field(min_length=1, max_length=6)
    first_hire: str = Field(description="The single role to fill first and why, given the budget and the riskiest step")
    job_post_title: str
    job_post: str = Field(description="Short, honest post for the first role: the task, hours, paid or unpaid, stage of the "
                          "product (no traction it does not have), and how to apply. No promises of equity value or income.")


def search_links(title: str, location: str) -> dict[str, str]:
    q = quote_plus(f"{title} {location}".strip())
    t = quote_plus(title)
    links = {"LinkedIn (people open to work)": f"https://www.linkedin.com/search/results/people/?keywords={quote_plus(title + ' open to work ' + location)}",
             "Upwork (freelancers)": f"https://www.upwork.com/nx/search/talent/?q={t}"}
    if "egypt" in location.lower() or "مصر" in location or not location:
        links["Mostaql (Arabic freelancers)"] = f"https://mostaql.com/freelancers?keyword={t}"
        links["Wuzzuf (Egypt job board)"] = f"https://wuzzuf.net/search/jobs/?q={q}"
    return links


def apply_rules(plan: TeamPlan, brief) -> tuple[TeamPlan, list[str]]:
    """Founder's own skills first; no paid hire now that the budget cannot carry."""
    notes, roles = [], []
    have = {s.lower() for s in brief.skills}
    for r in plan.roles:
        covered = any(h in " ".join(r.skills + [r.title]).lower() or any(w in h for w in r.title.lower().split() if len(w) > 3)
                      for h in have)
        if covered and r.how != "founder":
            notes.append(f"{r.title}: you listed a matching skill, so you do this yourself for now")
            r = r.model_copy(update={"how": "founder"})
        elif r.how == "part_time" and r.when == "now" and brief.budget_usd < 500:
            notes.append(f"{r.title}: a part-time hire now does not fit a ${brief.budget_usd:g} budget; use a small freelance task")
            r = r.model_copy(update={"how": "freelancer"})
        roles.append(r)
    return plan.model_copy(update={"roles": roles}), notes


class TeamPlannerAgent(Agent):
    role = "team_planner"

    def plan(self, brief, context: str) -> TeamPlan:
        user = f"FOUNDER BRIEF\n{brief.as_text()}\n\nWHAT THE RUN HAS PRODUCED SO FAR\n{context}"
        return self.ask("plan_team", user, TeamPlan, critique=lambda d: problems(d, brief))


def render_md(plan: TeamPlan, notes: list[str], location: str) -> str:
    how = {"founder": "you (founder)", "freelancer": "freelancer, per task", "part_time": "part-time hire",
           "co_founder": "co-founder", "later": "later"}
    lines = ["# Team plan: who this business needs, and where to find them", "",
             "Roles proposed by the team planner from this run; code applied your skills and budget. The links search public "
             "job boards for people looking for this work; this system never scrapes profiles, stores names or contacts anyone.", "",
             "| Role | Why this business needs it | When | Hours/week | How |", "|---|---|---|---|---|"]
    lines += [f"| {r.title} | {r.why} | {r.when.replace('_', ' ')} | {r.hours_per_week:g} | {how[r.how]} |" for r in plan.roles]
    if notes:
        lines += ["", "Adjusted in code:", *[f"- {n}" for n in notes]]
    lines += ["", f"**Fill first:** {plan.first_hire}", "", "## Where to look"]
    for r in plan.roles:
        if r.how in ("founder", "later"):
            continue
        lines += ["", f"**{r.title}** ({', '.join(r.skills)})"] + [f"- [{k}]({v})" for k, v in search_links(r.title, location).items()]
    lines += ["", f"## Job post draft: {plan.job_post_title}", "", "A draft: you post it yourself, on your own accounts.", "",
              plan.job_post, ""]
    return "\n".join(lines)
