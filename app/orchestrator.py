"""Orchestrator: an explicit state machine over the six phases.

The orchestrator runs agent steps until it reaches something only the
founder can decide (a gate decision, demand targets, interview results),
then stops and waits. Phases 1-2 are built; phases 3-6 are STUBBED.

Stages:
  new -> p1_running -> p1_gate_wait -> p2_running -> p2_targets_wait
      -> p2_collecting -> p2_gate_wait -> p3_6_stubbed -> done
  any gate can end in: stopped
"""
from __future__ import annotations

import json
import re
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from app import guard
from app.agents.analyst import AnalystAgent, DemandTestPlan
from app.agents.base import AgentContext
from app.agents.interviewer import InterviewerAgent, InterviewPlan
from app.agents.market_analyst import Market, MarketAnalystAgent
from app.agents.marketer import LandingCopy, MarketerAgent
from app.agents.researcher import ResearcherAgent
from app.agents.scout import Opportunities, Opportunity, ScoutAgent
from app.agents.strategist import LeanCanvas, StrategistAgent
from app.agents.stubs import STUB_PHASES, stub_report
from app.approval import ApprovalItem, ApprovalQueue
from app.brief import FounderBrief
from app.config import Settings
from app.decision_log import DecisionLog
from app.evidence import Ledger, resolve
from app.gates import OUTCOMES, DemandTargets, GateResult, demand_gate, discover_gate
from app.landing import render_landing
from app.llm import LLM
from app.research import Doc, Researcher


def slugify(s: str, n: int = 24) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")[:n].strip("-") or "run"


@dataclass
class RunState:
    run_id: str
    slug: str
    brief: dict
    stage: str = "new"
    docs: list[dict] = field(default_factory=list)
    ledger: list[dict] = field(default_factory=list)
    opportunities: list[dict] = field(default_factory=list)
    chosen: int = 0
    tried: list[int] = field(default_factory=list)
    market: dict | None = None
    interview_plan: dict | None = None
    canvas: dict | None = None
    landing: dict | None = None
    demand_plan: dict | None = None
    targets: dict | None = None
    results: dict | None = None
    gates: list[dict] = field(default_factory=list)
    approvals: list[dict] = field(default_factory=list)
    outputs: list[str] = field(default_factory=list)
    iterations: int = 0
    usage: dict = field(default_factory=dict)
    error: str | None = None


class Orchestrator:
    def __init__(self, settings: Settings, llm: LLM, researcher: Researcher | None = None):
        self.settings = settings
        self.llm = llm
        self.researcher = researcher or Researcher(settings.web_research, settings.max_sources)
        self.log = DecisionLog(settings.decision_log_path)
        self.runs_dir = settings.data_dir / "runs"
        self.sites_dir = settings.data_dir / "sites"

    # ---------- persistence ----------
    def _path(self, run_id: str) -> Path:
        return self.runs_dir / run_id / "state.json"

    def save(self, st: RunState, q: ApprovalQueue) -> None:
        st.approvals = q.to_list()
        st.usage = {"calls": self.llm.usage.calls, "prompt_tokens": self.llm.usage.prompt_tokens,
                    "completion_tokens": self.llm.usage.completion_tokens, "cost_usd": self.llm.usage.cost_usd}
        p = self._path(st.run_id)
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix(".tmp")
        tmp.write_text(json.dumps(st.__dict__, indent=1, ensure_ascii=False), encoding="utf-8")
        tmp.replace(p)  # atomic: a failed write never leaves an empty state file

    def load(self, run_id: str) -> tuple[RunState, ApprovalQueue]:
        st = RunState(**json.loads(self._path(run_id).read_text(encoding="utf-8")))
        q = self.queue(st.run_id)
        q.load(st.approvals)
        return st, q

    def list_runs(self) -> list[RunState]:
        if not self.runs_dir.exists():
            return []
        out = []
        for p in sorted(self.runs_dir.glob("*/state.json"), key=lambda p: p.stat().st_mtime, reverse=True):
            out.append(RunState(**json.loads(p.read_text(encoding="utf-8"))))
        return out

    def queue(self, run_id: str) -> ApprovalQueue:
        return ApprovalQueue(self.log, run_id, {
            "publish_landing_local": self._publish_landing_local,
            "send_outreach_mock": self._send_outreach_mock,
        })

    # ---------- executors (only reachable through an approved item) ----------
    def _publish_landing_local(self, item: ApprovalItem) -> str:
        run_id = item.title.split(":")[-1].strip()
        d = self.sites_dir / run_id
        d.mkdir(parents=True, exist_ok=True)
        (d / "index.html").write_text(item.content, encoding="utf-8")
        return (f"Published locally at {self.settings.public_base_url}/lp/{run_id} "
                "(public hosting is MOCKED: nothing was deployed to the internet)")

    def _send_outreach_mock(self, item: ApprovalItem) -> str:
        return "MOCKED: message marked approved for the founder to send personally; the system sent nothing"

    # ---------- helpers ----------
    def ctx(self, st: RunState) -> AgentContext:
        return AgentContext(self.llm, self.log, self.settings.prompts_dir, st.run_id)

    def write_output(self, st: RunState, name: str, content: str) -> str:
        stem, ext = name.rsplit(".", 1)
        fname = f"{stem}-{st.slug}.{ext}"
        self.settings.outputs_dir.mkdir(parents=True, exist_ok=True)
        (self.settings.outputs_dir / fname).write_text(content, encoding="utf-8")
        if fname not in st.outputs:
            st.outputs.append(fname)
        return fname

    def docs(self, st: RunState) -> list[Doc]:
        return [Doc(**d) for d in st.docs]

    # ---------- public API ----------
    def start(self, brief: FounderBrief) -> RunState:
        st = self.create(brief)
        return self.advance(st.run_id) if st.stage == "p1_running" else st

    def create(self, brief: FounderBrief) -> RunState:
        """Screen the brief and save a new run without running any agent yet."""
        run_id = uuid.uuid4().hex[:8]
        st = RunState(run_id=run_id, slug=slugify(brief.idea.split(".")[0]), brief=brief.model_dump())
        q = self.queue(run_id)
        self.log.append(agent="orchestrator", action="start_run", run_id=run_id, detail=brief.idea[:200])
        v = guard.check_request(brief.all_text())
        if not v.allowed:
            self.log.append(agent="guard", action="screen_brief", run_id=run_id, outcome="stop", detail=v.reason)
            g = GateResult("policy_gate", 1, "stop", [v.reason or "blocked by policy"])
            g.founder_decision = "stop"
            g.founder_note = "Automatic: this product type or request is outside what the system will help with."
            st.gates.append(g.to_dict())
            self.write_output(st, "phase1_gate_policy.md", g.md())
            st.stage = "stopped"
            self.save(st, q)
            return st
        st.stage = "p1_running"
        self.save(st, q)
        return st

    def advance(self, run_id: str) -> RunState:
        st, q = self.load(run_id)
        try:
            if st.stage == "p1_running":
                self._phase1(st, q)
            elif st.stage == "p2_running":
                self._phase2(st, q)
            elif st.stage == "p3_6_stubbed":
                self._stubs(st)
        except Exception as e:  # surface, never hide
            st.error = f"{type(e).__name__}: {e}"
            self.log.append(agent="orchestrator", action="step_failed", run_id=st.run_id, outcome="error", detail=st.error)
        self.save(st, q)
        return st

    # ---------- phase 1: Discover ----------
    def _phase1(self, st: RunState, q: ApprovalQueue) -> None:
        brief = FounderBrief(**st.brief)
        ctx = self.ctx(st)
        st.error = None
        st.iterations += 1
        if not st.docs:
            self.researcher.errors = []
            st.docs = [d.__dict__ for d in ResearcherAgent(ctx).gather(brief, self.researcher)]
        docs = self.docs(st)

        if not st.opportunities:
            opps = ScoutAgent(ctx).find_opportunities(brief, docs)
            st.opportunities = [o.model_dump() for o in opps.opportunities]
        opps = [Opportunity(**o) for o in st.opportunities]
        ledger = Ledger()
        md = [f"# Phase 1, step 1: Find opportunities", "", f"Founder brief:\n\n```\n{brief.as_text()}\n```", ""]
        for i, o in enumerate(opps):
            claims = ledger.add(resolve(o.claims, docs))
            md += [f"## {i + 1}. {o.name} (score {o.score}/5)", "",
                   f"- Problem: {o.problem}", f"- Customer: {o.customer}", f"- Digital product: {o.digital_product}",
                   f"- Alternatives today: {', '.join(o.current_alternatives)}",
                   f"- Scores: pain {o.scores.pain}, founder fit {o.scores.founder_fit}, feasibility {o.scores.feasibility}, "
                   f"reach {o.scores.reach}, differentiation {o.scores.differentiation} (model judgement)",
                   f"- Biggest risk: {o.biggest_risk}", "", "Claims:", *[f"- {c.md()}" for c in claims], ""]
        md += ["## Sources retrieved", *[f"- [{d.id}] {d.url}" for d in docs]]
        if self.researcher.errors:
            md += ["", "Research tools that failed (results may be thinner): " + "; ".join(self.researcher.errors)]
        self.write_output(st, "phase1_step1_opportunities.md", "\n".join(md) + "\n")

        # choose best not yet tried
        order = sorted(range(len(opps)), key=lambda i: opps[i].score, reverse=True)
        st.chosen = next((i for i in order if i not in st.tried), order[0])
        opp = opps[st.chosen]

        market = MarketAnalystAgent(ctx).define_market(brief, opp, docs)
        st.market = market.model_dump()
        mclaims = ledger.add(resolve(market.claims, docs))
        self.write_output(st, "phase1_step2_market.md", "\n".join([
            f"# Phase 1, step 2: Define the market for '{opp.name}'", "",
            f"- Ideal customer: {market.ideal_customer}", f"- Segments: {', '.join(market.segments)}",
            f"- Where they gather: {', '.join(market.where_they_gather)}", f"- Alternatives: {', '.join(market.alternatives)}",
            "", "## Claims", *[f"- {c.md()}" for c in mclaims], "", "## Unknowns (to learn in interviews)",
            *[f"- {u}" for u in market.unknowns]]) + "\n")

        plan = InterviewerAgent(ctx).plan_interviews(opp, market, brief.founder_name)
        st.interview_plan = plan.model_dump()
        self.write_output(st, "phase1_step3_interview_plan.md", _interview_md(plan))
        try:
            q.submit("send", f"Interview outreach message for {opp.name}", plan.outreach_message, "send_outreach_mock", 1)
        except PermissionError:
            pass  # logged by the queue; founder sees the block in the output

        st.ledger = ledger.to_list()
        pain_urls = {d.url for d in docs if d.id in {s.strip("[]") for s in opp.pain_source_ids}}
        excluded = guard.check_product(f"{opp.name} {opp.digital_product} {opp.problem}")
        g = discover_gate(sourced_claims=len(ledger.sourced), total_claims=len(ledger.claims),
                          pain_sources=len(pain_urls), best_score=opp.score,
                          excluded_reason=None if excluded.allowed else excluded.reason)
        st.gates.append(g.to_dict())
        self.log.append(agent="gate", action="evidence_gate", sources=ledger.urls(), run_id=st.run_id,
                        outcome=g.recommendation, phase=1)
        self.write_output(st, "phase1_gate_decision.md", g.md())
        st.stage = "p1_gate_wait"

    # ---------- phase 2: Validate ----------
    def _phase2(self, st: RunState, q: ApprovalQueue) -> None:
        brief = FounderBrief(**st.brief)
        ctx = self.ctx(st)
        st.error = None
        docs = self.docs(st)
        opp = Opportunity(**st.opportunities[st.chosen])
        market = Market(**st.market)
        canvas = StrategistAgent(ctx).lean_canvas(brief, opp, market, docs)
        st.canvas = canvas.model_dump()
        led = Ledger.from_list(st.ledger)
        cclaims = led.add(resolve(canvas.claims, docs))
        st.ledger = led.to_list()
        self.write_output(st, "phase2_step1_lean_canvas.md", _canvas_md(opp.name, canvas, cclaims))

        copy = MarketerAgent(ctx).landing_copy(canvas, opp.name)
        html, removed = render_landing(opp.name, copy, st.run_id)
        st.landing = copy.model_dump() | {"removed_by_guard": removed}
        self.write_output(st, "phase2_step2_landing_page.html", html)
        if removed:
            self.log.append(agent="guard", action="scrub_landing_copy", run_id=st.run_id, outcome="scrubbed",
                            detail=", ".join(removed))
        q.submit("publish", f"Publish waitlist landing page: {st.run_id}", html, "publish_landing_local", 2)

        plan = AnalystAgent(ctx).demand_test(brief, canvas)
        st.demand_plan = plan.model_dump()
        self.write_output(st, "phase2_step3_demand_test.md", "\n".join([
            "# Phase 2, step 3: Demand test plan (targets proposed BEFORE the test)", "",
            f"- Hypothesis: {plan.hypothesis}",
            f"- Waitlist sign-ups target: {plan.waitlist_signups_target} in {plan.window_days} days",
            f"- Interviews target: {plan.interviews_target}",
            f"- Share confirming the problem: {plan.pain_confirm_rate_target:.0%}",
            f"- Channels: {', '.join(plan.channels)}", f"- Rationale: {plan.rationale}", "",
            "Sign-ups are counted by the app from real form submissions. Interview results are entered by the founder.",
            "The system never creates sign-ups."]) + "\n")
        st.stage = "p2_targets_wait"

    def _stubs(self, st: RunState) -> None:
        for p in STUB_PHASES:
            self.write_output(st, f"phase{p.phase}_step1_{slugify(p.name, 20)}-STUBBED.md", stub_report(p))
            self.log.append(agent="orchestrator", action=f"phase{p.phase}_stubbed", run_id=st.run_id, outcome="stubbed")
        st.stage = "done"

    # ---------- founder actions ----------
    def founder_gate_decision(self, run_id: str, decision: str, note: str | None = None) -> RunState:
        if decision not in OUTCOMES:
            raise ValueError(f"decision must be one of {OUTCOMES}")
        st, q = self.load(run_id)
        if st.stage not in ("p1_gate_wait", "p2_gate_wait"):
            raise ValueError(f"no gate is waiting (stage={st.stage})")
        from app.gates import Check
        g_full = st.gates[-1]
        g_full["founder_decision"] = decision
        g_full["founder_note"] = note
        gr = GateResult(**{**g_full, "checks": [Check(**c) for c in g_full["checks"]]})
        self.log.append(agent="founder", action=f"{gr.gate}_decision", approved_by="founder", run_id=run_id,
                        outcome=decision, recommendation=gr.recommendation,
                        founder_override=decision != gr.recommendation, detail=note)
        phase = gr.phase
        self.write_output(st, f"phase{phase}_gate_decision.md", gr.md())
        if decision == "stop":
            st.stage = "stopped"
        elif phase == 1:
            if decision == "go":
                st.stage = "p2_running"
            elif decision == "repeat":
                st.opportunities, st.tried, st.docs = [], [], []
                st.stage = "p1_running"
            else:  # pivot to the next-best opportunity
                st.tried.append(st.chosen)
                st.stage = "p1_running"
        else:
            if decision == "go":
                st.stage = "p3_6_stubbed"
            elif decision == "repeat":
                st.stage = "p2_collecting"
            else:
                st.tried.append(st.chosen)
                st.stage = "p1_running"
        self.save(st, q)
        if st.stage in ("p1_running", "p2_running", "p3_6_stubbed"):
            return self.advance(run_id)
        return st

    def founder_lock_targets(self, run_id: str, approve: bool, note: str | None = None) -> RunState:
        st, q = self.load(run_id)
        if st.stage != "p2_targets_wait":
            raise ValueError(f"targets are not waiting (stage={st.stage})")
        p = DemandTestPlan(**st.demand_plan)
        if approve:
            st.targets = DemandTargets(p.waitlist_signups_target, p.window_days, p.interviews_target,
                                       p.pain_confirm_rate_target).__dict__
            st.stage = "p2_collecting"
        self.log.append(agent="founder", action="lock_demand_targets" if approve else "reject_demand_targets",
                        approved_by="founder" if approve else None, run_id=run_id,
                        outcome="locked" if approve else "rejected", detail=note)
        if not approve:
            st.stage = "p2_running"
            self.save(st, q)
            return self.advance(run_id)
        self.save(st, q)
        return st

    def signups(self, run_id: str) -> int:
        p = self.sites_dir / run_id / "waitlist.csv"
        return max(0, len(p.read_text(encoding="utf-8").splitlines()) - 1) if p.exists() else 0

    def add_signup(self, run_id: str, email: str) -> None:
        """Called only by the public landing-page form submitted by a real visitor."""
        p = self.sites_dir / run_id / "waitlist.csv"
        if not (self.sites_dir / run_id / "index.html").exists():
            raise PermissionError("landing page is not published")
        if not p.exists():
            p.write_text("email\n", encoding="utf-8")
        existing = set(p.read_text(encoding="utf-8").splitlines()[1:])
        if email not in existing:
            with p.open("a", encoding="utf-8") as f:
                f.write(email + "\n")

    def founder_record_results(self, run_id: str, interviews_done: int, pain_confirmed: int) -> RunState:
        st, q = self.load(run_id)
        if st.stage != "p2_collecting":
            raise ValueError(f"not collecting evidence (stage={st.stage})")
        if pain_confirmed > interviews_done or interviews_done < 0:
            raise ValueError("pain_confirmed cannot exceed interviews_done")
        signups = self.signups(run_id)
        st.results = {"signups": signups, "interviews_done": interviews_done, "pain_confirmed": pain_confirmed}
        self.log.append(agent="founder", action="record_interview_results", approved_by="founder", run_id=run_id,
                        detail=f"{interviews_done} interviews, {pain_confirmed} confirmed pain; {signups} sign-ups counted by app")
        g = demand_gate(DemandTargets(**st.targets), **st.results)
        st.gates.append(g.to_dict())
        self.log.append(agent="gate", action="demand_gate", run_id=run_id, outcome=g.recommendation, phase=2)
        self.write_output(st, "phase2_gate_decision.md", g.md())
        st.stage = "p2_gate_wait"
        self.save(st, q)
        return st

    def approve(self, run_id: str, item_id: str, approve: bool, note: str | None = None) -> RunState:
        st, q = self.load(run_id)
        q.decide(item_id, approve, note)
        self.save(st, q)
        return st


def _interview_md(p: InterviewPlan) -> str:
    return "\n".join([
        "# Phase 1, step 3: Customer interviews (Mom Test)", "", f"Goal: {p.goal}", "", "## Who to talk to",
        *[f"- {c}" for c in p.screening_criteria], "", "## Questions (past behaviour, not opinions)",
        *[f"{i + 1}. {qq}" for i, qq in enumerate(p.questions)], "", "## Avoid", *[f"- {a}" for a in p.avoid], "",
        f"Problem counts as confirmed if: {p.pain_confirmed_if}", "",
        "## Outreach draft (queued for founder approval; the founder sends it personally)", "",
        p.outreach_message]) + "\n"


def _canvas_md(name: str, c: LeanCanvas, claims) -> str:
    def bl(xs):
        return "<br>".join(xs)
    return "\n".join([
        f"# Phase 2, step 1: Lean Canvas for '{name}'", "",
        "| Box | Content |", "|---|---|",
        f"| Problem | {bl(c.problem)} |", f"| Customer segments | {bl(c.customer_segments)} |",
        f"| Unique value proposition | {c.unique_value_proposition} |", f"| Solution | {bl(c.solution)} |",
        f"| Channels | {bl(c.channels)} |", f"| Revenue streams | {bl(c.revenue_streams)} |",
        f"| Cost structure | {bl(c.cost_structure)} |", f"| Key metrics | {bl(c.key_metrics)} |",
        f"| Unfair advantage | {c.unfair_advantage} |", "",
        "## Riskiest assumptions (tested in Validate)", *[f"{i + 1}. {a}" for i, a in enumerate(c.riskiest_assumptions)],
        "", "## Claims", *[f"- {x.md()}" for x in claims]]) + "\n"
