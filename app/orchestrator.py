"""Orchestrator: an explicit state machine over the six phases.

The orchestrator runs agent steps until it reaches something only the
founder can decide (a gate decision, demand targets, interview results),
then stops and waits. Phases 1-2 are built; phases 3-6 are STUBBED.

Stages:
  new -> p1_running -> p1_gate_wait -> p2_running -> p2_targets_wait
      -> p2_collecting -> p2_gate_wait -> p3_running -> p3_gate_wait -> p4_running -> p4_gate_wait -> p5_6_stubbed -> done
  any gate can end in: stopped
"""
from __future__ import annotations

import json
import re
import threading
import time
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
from app.agents.builder import BuilderAgent, MvpSpec
from app.agents.policy_drafter import PolicyDrafterAgent, PolicyDrafts
from app.agents.pricer import PricerAgent, PricingPlan
from app.agents.scout import Opportunities, Opportunity, ScoutAgent
from app.agents.strategist import LeanCanvas, StrategistAgent
from app.agents.stubs import STUB_PHASES, stub_report
from app.approval import ApprovalItem, ApprovalQueue
from app.brief import FounderBrief
from app.config import Settings
from app.decision_log import DecisionLog
from app.evidence import Ledger, RawClaim, resolve
from app.gates import OUTCOMES, DemandTargets, GateResult, build_gate, commercial_gate, demand_gate, discover_gate
from app.prototype import prototype_is_safe, render_prototype
from app.landing import render_landing
from app.llm import LLM
from app.research import Doc, Researcher


_io_lock = threading.RLock()


def _atomic_write(p: Path, text: str) -> None:
    """Write via a temp file; retry the swap because Windows refuses to
    replace a file another request is reading at that instant."""
    tmp = p.with_name(p.name + f".{threading.get_ident()}.tmp")
    tmp.write_text(text, encoding="utf-8")
    for i in range(20):
        try:
            tmp.replace(p)
            return
        except PermissionError:
            time.sleep(0.05 * (i + 1))
    p.write_text(text, encoding="utf-8")
    tmp.unlink(missing_ok=True)


def _read_json(p: Path):
    for i in range(20):
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except (PermissionError, json.JSONDecodeError):
            if i == 19:
                raise
            time.sleep(0.05 * (i + 1))


P1_STEPS = ["Researcher: searching free sources", "Scout: finding and scoring opportunities",
            "Market analyst: defining the market", "Interviewer: writing the Mom Test plan",
            "Gate: checking evidence against targets"]
P2_STEPS = ["Strategist: drafting the Lean Canvas", "Marketer: writing landing-page copy",
            "Analyst: proposing demand-test targets"]
P3_STEPS = ["Builder: scoping the MVP (user stories, features, screens)", "Builder: rendering the clickable prototype",
            "QA: checking acceptance criteria, scope and safety", "Gate: build gate"]
P4_STEPS = ["Pricer: tiers from comparable products", "Policy drafter: terms, privacy and refund drafts",
            "Gate: commercial gate"]


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
    mvp: dict | None = None
    build_feedback: str | None = None
    pricing: dict | None = None
    policies: dict | None = None
    commercial_feedback: str | None = None
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
        self._run_locks: dict[str, threading.RLock] = {}
        self.progress: dict[str, dict] = {}  # run_id -> {"steps": [...], "current": i}

    def _step(self, st: RunState, steps: list[str], i: int) -> None:
        self.progress[st.run_id] = {"steps": steps, "current": i}

    def lock(self, run_id: str) -> threading.RLock:
        """One writer per run: agent steps and founder actions never interleave,
        so a background step cannot overwrite an approval made meanwhile."""
        with _io_lock:
            return self._run_locks.setdefault(run_id, threading.RLock())

    # ---------- persistence ----------
    def _path(self, run_id: str) -> Path:
        return self.runs_dir / run_id / "state.json"

    def save(self, st: RunState, q: ApprovalQueue) -> None:
        st.approvals = q.to_list()
        st.usage.setdefault("cost_usd", 0.0)  # per-run totals are added by each agent call (Agent.ask)
        p = self._path(st.run_id)
        p.parent.mkdir(parents=True, exist_ok=True)
        with _io_lock:
            _atomic_write(p, json.dumps(st.__dict__, indent=1, ensure_ascii=False))

    def load(self, run_id: str) -> tuple[RunState, ApprovalQueue]:
        st = RunState(**_read_json(self._path(run_id)))
        q = self.queue(st.run_id)
        q.load(st.approvals)
        return st, q

    def list_runs(self) -> list[RunState]:
        if not self.runs_dir.exists():
            return []
        out = []
        for p in sorted(self.runs_dir.glob("*/state.json"), key=lambda p: p.stat().st_mtime, reverse=True):
            try:
                out.append(RunState(**_read_json(p)))
            except (OSError, ValueError):
                continue  # skip an unreadable run instead of breaking the home page
        return out

    def queue(self, run_id: str) -> ApprovalQueue:
        return ApprovalQueue(self.log, run_id, {
            "publish_landing_local": self._publish_landing_local,
            "send_outreach_mock": self._send_outreach_mock,
            "publish_prototype_local": self._publish_prototype_local,
            "sign_commercial": self._sign_commercial,
        })

    # ---------- executors (only reachable through an approved item) ----------
    def _publish_landing_local(self, item: ApprovalItem) -> str:
        run_id = item.title.split(":")[-1].strip()
        d = self.sites_dir / run_id
        d.mkdir(parents=True, exist_ok=True)
        (d / "index.html").write_text(item.content, encoding="utf-8")
        return (f"Published locally at {self.settings.public_base_url}/lp/{run_id} "
                "(public hosting is MOCKED: nothing was deployed to the internet)")

    def _publish_prototype_local(self, item: ApprovalItem) -> str:
        run_id = item.title.split(":")[-1].strip()
        d = self.sites_dir / run_id
        d.mkdir(parents=True, exist_ok=True)
        (d / "prototype.html").write_text(item.content, encoding="utf-8")
        return (f"Prototype available at {self.settings.public_base_url}/proto/{run_id} on this computer "
                "(public hosting is MOCKED)")

    def _sign_commercial(self, item: ApprovalItem) -> str:
        return ("Signed off by the founder (recorded in the decision log). Nothing was published: policies and prices "
                "go live only with the store page in Phase 5 (STUBBED). Review with a lawyer before launch.")

    def _send_outreach_mock(self, item: ApprovalItem) -> str:
        return "MOCKED: message marked approved for the founder to send personally; the system sent nothing"

    # ---------- helpers ----------
    def ctx(self, st: RunState) -> AgentContext:
        return AgentContext(self.llm, self.log, self.settings.prompts_dir, st.run_id, st.usage)

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
        with self.lock(run_id):
            return self._advance(run_id)

    def _advance(self, run_id: str) -> RunState:
        st, q = self.load(run_id)
        try:
            if st.stage == "p1_running":
                self._phase1(st, q)
            elif st.stage == "p2_running":
                self._phase2(st, q)
            elif st.stage == "p3_running":
                self._phase3(st, q)
            elif st.stage == "p4_running":
                self._phase4(st, q)
            elif st.stage in ("p5_6_stubbed", "p4_6_stubbed", "p3_6_stubbed"):
                self._stubs(st)
        except Exception as e:  # surface, never hide
            st.error = f"{type(e).__name__}: {e}"
            self.log.append(agent="orchestrator", action="step_failed", run_id=st.run_id, outcome="error", detail=st.error)
        self.progress.pop(st.run_id, None)
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
            self._step(st, P1_STEPS, 0)
            st.docs = [d.__dict__ for d in ResearcherAgent(ctx).gather(brief, self.researcher)]
        docs = self.docs(st)

        if not st.opportunities:
            self._step(st, P1_STEPS, 1)
            opps = ScoutAgent(ctx).find_opportunities(brief, docs)
            st.opportunities = [o.model_dump() for o in opps.opportunities]
        opps = [Opportunity(**o) for o in st.opportunities]
        # The model may drift into excluded territory even from an allowed brief:
        # screen every opportunity in code and never choose an excluded one.
        excluded_opps: dict[int, str] = {}
        for i, o in enumerate(opps):
            v = guard.check_product(f"{o.name} {o.digital_product} {o.problem} {o.customer}")
            if not v.allowed:
                excluded_opps[i] = v.reason or "excluded by policy"
                self.log.append(agent="guard", action="exclude_opportunity", run_id=st.run_id,
                                outcome="excluded", rule=v.rule, detail=o.name)
        ledger = Ledger()
        md = [f"# Phase 1, step 1: Find opportunities", "", f"Founder brief:\n\n```\n{brief.as_text()}\n```", ""]
        for i, o in enumerate(opps):
            if i in excluded_opps:
                md += [f"## {i + 1}. {o.name}: EXCLUDED by policy", "", f"- {excluded_opps[i]} Not scored or pursued.", ""]
                continue
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

        allowed = [i for i in range(len(opps)) if i not in excluded_opps]
        if not allowed:
            reason = next(iter(excluded_opps.values()))
            g = GateResult("policy_gate", 1, "stop", [f"Every opportunity found falls outside policy. {reason}"])
            g.founder_decision = "stop"
            g.founder_note = "Automatic: this product type is outside what the system will help with."
            st.gates.append(g.to_dict())
            self.log.append(agent="gate", action="policy_gate", run_id=st.run_id, outcome="stop", phase=1)
            self.write_output(st, "phase1_gate_policy.md", g.md())
            st.stage = "stopped"
            return
        # choose best allowed opportunity not yet tried
        order = sorted(allowed, key=lambda i: opps[i].score, reverse=True)
        st.chosen = next((i for i in order if i not in st.tried), order[0])
        opp = opps[st.chosen]

        self._step(st, P1_STEPS, 2)
        market = MarketAnalystAgent(ctx).define_market(brief, opp, docs)
        st.market = market.model_dump()
        mclaims = ledger.add(resolve(market.claims, docs))
        self.write_output(st, "phase1_step2_market.md", "\n".join([
            f"# Phase 1, step 2: Define the market for '{opp.name}'", "",
            f"- Ideal customer: {market.ideal_customer}", f"- Segments: {', '.join(market.segments)}",
            f"- Where they gather: {', '.join(market.where_they_gather)}", f"- Alternatives: {', '.join(market.alternatives)}",
            "", "## Claims", *[f"- {c.md()}" for c in mclaims], "", "## Unknowns (to learn in interviews)",
            *[f"- {u}" for u in market.unknowns]]) + "\n")

        self._step(st, P1_STEPS, 3)
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
        self._step(st, P1_STEPS, 4)
        g = discover_gate(sourced_claims=len(ledger.sourced), total_claims=len(ledger.claims),
                          pain_sources=len(pain_urls), best_score=opp.score,
                          excluded_reason=None if excluded.allowed else excluded.reason,
                          attempt=1 + sum(1 for x in st.gates if x["gate"] == "evidence_gate"))
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
        self._step(st, P2_STEPS, 0)
        canvas = StrategistAgent(ctx).lean_canvas(brief, opp, market, docs)
        st.canvas = canvas.model_dump()
        led = Ledger.from_list(st.ledger)
        cclaims = led.add(resolve(canvas.claims, docs))
        st.ledger = led.to_list()
        self.write_output(st, "phase2_step1_lean_canvas.md", _canvas_md(opp.name, canvas, cclaims))

        self._step(st, P2_STEPS, 1)
        copy = MarketerAgent(ctx).landing_copy(canvas, opp.name)
        html, removed = render_landing(opp.name, copy, st.run_id)
        st.landing = copy.model_dump() | {"removed_by_guard": removed}
        self.write_output(st, "phase2_step2_landing_page.html", html)
        if removed:
            self.log.append(agent="guard", action="scrub_landing_copy", run_id=st.run_id, outcome="scrubbed",
                            detail=", ".join(removed))
        q.submit("publish", f"Publish waitlist landing page: {st.run_id}", html, "publish_landing_local", 2)

        self._step(st, P2_STEPS, 2)
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

    # ---------- phase 3: Build (MVP spec + clickable prototype) ----------
    def _phase3(self, st: RunState, q: ApprovalQueue) -> None:
        brief = FounderBrief(**st.brief)
        ctx = self.ctx(st)
        st.error = None
        opp = Opportunity(**st.opportunities[st.chosen])
        canvas = LeanCanvas(**st.canvas)
        self._step(st, P3_STEPS, 0)
        spec = BuilderAgent(ctx).mvp_spec(brief, opp, canvas, st.build_feedback)
        st.mvp = spec.model_dump()
        self.write_output(st, "phase3_step1_mvp_spec.md", _mvp_md(spec, brief))

        self._step(st, P3_STEPS, 1)
        page, removed = render_prototype(spec)
        self.write_output(st, "phase3_step2_prototype.html", page)
        if removed:
            self.log.append(agent="guard", action="scrub_prototype", run_id=st.run_id, outcome="scrubbed",
                            detail=", ".join(removed))

        self._step(st, P3_STEPS, 2)
        story_ids = {u.id for u in spec.user_stories}
        untestable = [u.id for u in spec.user_stories if not any(_testable(a) for a in u.acceptance)]
        untraced = [f.name for f in spec.must_have if not (set(f.story_ids) & story_ids)]
        total = round(sum(f.estimate_hours for f in spec.must_have), 1)
        safety = prototype_is_safe(page)
        self.write_output(st, "phase3_step3_acceptance_tests.md", _acceptance_md(spec, untestable, untraced, safety))
        self.log.append(agent="qa_tester", action="check_mvp", run_id=st.run_id, outcome="checked",
                        detail=f"{len(untestable)} untestable stories, {len(untraced)} untraced features, {total}h, "
                               f"{len(safety)} safety problems")

        self._step(st, P3_STEPS, 3)
        g = build_gate(stories=len(spec.user_stories), untestable_stories=untestable, untraced_features=untraced,
                       must_have=len(spec.must_have), total_hours=total, hours_per_week=brief.hours_per_week,
                       safety_problems=safety, guard_removed=removed,
                       attempt=1 + sum(1 for x in st.gates if x["gate"] == "build_gate"))
        st.gates.append(g.to_dict())
        self.log.append(agent="gate", action="build_gate", run_id=st.run_id, outcome=g.recommendation, phase=3)
        self.write_output(st, "phase3_gate_decision.md", g.md())
        q.supersede("publish_prototype_local")
        if not safety:
            q.submit("publish", f"Publish clickable prototype for review: {st.run_id}", page, "publish_prototype_local", 3)
        st.stage = "p3_gate_wait"

    # ---------- phase 4: Commercial setup (price + policy drafts) ----------
    def _phase4(self, st: RunState, q: ApprovalQueue) -> None:
        brief = FounderBrief(**st.brief)
        ctx = self.ctx(st)
        st.error = None
        docs = self.docs(st)
        canvas = LeanCanvas(**st.canvas)
        spec = MvpSpec(**st.mvp)
        primary = spec.user_stories[0].id
        core = [f.name for f in spec.must_have if primary in f.story_ids] or [spec.must_have[0].name]
        self._step(st, P4_STEPS, 0)
        plan = PricerAgent(ctx).price(brief, canvas, spec, docs, st.commercial_feedback,
                                      (st.market or {}).get("alternatives", []), core)
        st.pricing = plan.model_dump()
        led = Ledger.from_list(st.ledger)
        pclaims = led.add(resolve(plan.claims, docs))
        comps = [resolve([RawClaim(text=f"{c.product}: {c.pricing_note}", source_ids=c.source_ids)], docs)[0]
                 for c in plan.comparables]
        st.ledger = led.to_list()
        pricing_md = _pricing_md(plan, pclaims, comps, core)
        self.write_output(st, "phase4_step1_pricing.md", pricing_md)

        self._step(st, P4_STEPS, 1)
        pol = PolicyDrafterAgent(ctx).draft(brief, spec, plan)
        for p in (pol.terms, pol.privacy, pol.refund):  # never invent a contact address for the founder
            p.sections = [EMAIL.sub("[founder contact email]", x) for x in p.sections]
        st.policies = pol.model_dump()
        self.write_output(st, "phase4_step2_policies.md", _policies_md(pol))

        self._step(st, P4_STEPS, 2)
        # The same checks the approval queue applies on submit, so the gate and the queue never disagree.
        items = [("Approve pricing", pricing_md, guard.check_output)] + [
            (f"Sign off {k} policy draft", _policy_md(getattr(pol, k)), guard.check_policy) for k in ("terms", "privacy", "refund")]
        flags = [f"{t}: {v.rule}" for t, text, chk in items if not (v := chk(text)).allowed]
        free = [t for t in plan.tiers if t.price_usd_per_month == 0]
        free_text = " ".join(" ".join(t.includes) for t in free)
        free_core = bool(free) and all(c.lower() in free_text.lower() or _overlap(c, free_text) for c in core)
        paid = [t for t in plan.tiers if t.price_usd_per_month > 0]
        complete = [k for k, p in (("terms", pol.terms), ("privacy", pol.privacy), ("refund", pol.refund))
                    if len(p.sections) >= 3]
        g = commercial_gate(
            free_tier_with_core=free_core, comparables=len(plan.comparables),
            sourced_comparables=sum(1 for c in comps if c.status == "SOURCED"),
            paid_tiers_without_basis=0 if (not paid or comps) else len(paid),
            policies_complete=complete, policies_missing=[k for k in ("terms", "privacy", "refund") if k not in complete],
            guard_flags=flags, privacy_covers_data=bool(pol.data_collected),
            attempt=1 + sum(1 for x in st.gates if x["gate"] == "commercial_gate"))
        q.supersede("sign_commercial")
        if not flags:
            for t, text, chk in items:
                q.submit("sign", f"{t}: {st.run_id}", text, "sign_commercial", 4, check=chk)
        st.gates.append(g.to_dict())
        self.log.append(agent="gate", action="commercial_gate", run_id=st.run_id, outcome=g.recommendation, phase=4)
        self.write_output(st, "phase4_gate_decision.md", g.md())
        st.stage = "p4_gate_wait"

    def _stubs(self, st: RunState) -> None:
        for p in STUB_PHASES:
            self.write_output(st, f"phase{p.phase}_step1_{slugify(p.name, 20)}-STUBBED.md", stub_report(p))
            self.log.append(agent="orchestrator", action=f"phase{p.phase}_stubbed", run_id=st.run_id, outcome="stubbed")
        st.stage = "done"

    # ---------- founder actions ----------
    def founder_gate_decision(self, run_id: str, decision: str, note: str | None = None) -> RunState:
        with self.lock(run_id):
            return self._founder_gate_decision(run_id, decision=decision, note=note)

    def _founder_gate_decision(self, run_id: str, decision: str, note: str | None = None) -> RunState:
        if decision not in OUTCOMES:
            raise ValueError(f"decision must be one of {OUTCOMES}")
        st, q = self.load(run_id)
        if st.stage not in ("p1_gate_wait", "p2_gate_wait", "p3_gate_wait", "p4_gate_wait"):
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
        elif phase == 2:
            if decision == "go":
                st.stage = "p3_running"
            elif decision == "repeat":
                st.stage = "p2_collecting"
            else:
                st.tried.append(st.chosen)
                st.stage = "p1_running"
        elif phase == 4:
            if decision == "go":
                signs = [i for i in q.items if i.executor == "sign_commercial" and i.status != "superseded"]
                if not signs or any(i.status != "executed" for i in signs):
                    raise ValueError("GO needs the founder to approve the pricing and sign off all three policy drafts first")
                st.stage = "p5_6_stubbed"
            else:  # repeat or pivot: redraft with the failed checks
                failed = [c for c in gr.checks if not c.passed]
                st.commercial_feedback = "\n".join([f"- {c.name}: target {c.target}, got {c.actual}" for c in failed]
                                                   + ([f"- Founder note: {note}"] if note else []))
                st.stage = "p4_running"
        else:  # phase 3 build gate
            if decision == "go":
                st.stage = "p4_running"
            else:  # repeat: rebuild with the failed checks; pivot: rebuild a smaller MVP
                failed = [c for c in gr.checks if not c.passed]
                st.build_feedback = "\n".join(
                    [f"- {c.name}: target {c.target}, got {c.actual}" for c in failed]
                    + (["- Cut scope: a smaller MVP with fewer must-have features."] if decision == "pivot" else [])
                    + ([f"- Founder note: {note}"] if note else []))
                st.stage = "p3_running"
        self.save(st, q)
        if st.stage in ("p1_running", "p2_running", "p3_running", "p4_running", "p5_6_stubbed"):
            return self.advance(run_id)
        return st

    def founder_continue(self, run_id: str) -> RunState:
        """Runs that finished while a later phase was still STUBBED can continue into the
        phase that is built now, but only past gates the founder passed with GO."""
        with self.lock(run_id):
            st, q = self.load(run_id)
            passed = {g["gate"] for g in st.gates if g.get("founder_decision") == "go"}
            if st.stage != "done":
                raise ValueError("only a finished run can continue")
            if not st.mvp and "demand_gate" in passed:
                st.stage, phase = "p3_running", 3
            elif st.mvp and not st.pricing and "build_gate" in passed:
                st.stage, phase = "p4_running", 4
            else:
                raise ValueError("nothing to continue: the next phase needs a gate the founder passed with GO")
            self.log.append(agent="founder", action=f"start_phase{phase}", approved_by="founder", run_id=run_id,
                            outcome="go", phase=phase)
            self.save(st, q)
            return self._advance(run_id)

    founder_start_build = founder_continue

    def founder_lock_targets(self, run_id: str, approve: bool, note: str | None = None) -> RunState:
        with self.lock(run_id):
            return self._founder_lock_targets(run_id, approve=approve, note=note)

    def _founder_lock_targets(self, run_id: str, approve: bool, note: str | None = None) -> RunState:
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
        with self.lock(run_id):
            return self._founder_record_results(run_id, interviews_done=interviews_done, pain_confirmed=pain_confirmed)

    def _founder_record_results(self, run_id: str, interviews_done: int, pain_confirmed: int) -> RunState:
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
        with self.lock(run_id):
            return self._approve(run_id, item_id=item_id, approve=approve, note=note)

    def _approve(self, run_id: str, item_id: str, approve: bool, note: str | None = None) -> RunState:
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


_TESTABLE = re.compile(r"\b(given|when|then|shows?|displays?|returns?|saves?|within|at least|contains?|lists?|appears?|can see|is able to|\d)\b", re.I)


def _testable(criterion: str) -> bool:
    return len(criterion.split()) >= 4 and bool(_TESTABLE.search(criterion))


def _mvp_md(spec: MvpSpec, brief: FounderBrief) -> str:
    total = sum(f.estimate_hours for f in spec.must_have)
    return "\n".join([
        f"# Phase 3, step 1: MVP spec for '{spec.product_name}'", "", spec.one_line, "",
        f"Build budget: {brief.hours_per_week:g} h/week x 4 weeks = {brief.hours_per_week * 4:g} h. Estimated: {total:g} h (model estimate).",
        "", "## User stories",
        *[f"- **{u.id}** As {u.as_a}, I want {u.i_want}, so that {u.so_that}.\n" + "\n".join(f"  - [ ] {a}" for a in u.acceptance)
          for u in spec.user_stories],
        "", "## Must-have features", "| Feature | Stories | Hours | Description |", "|---|---|---|---|",
        *[f"| {f.name} | {', '.join(f.story_ids)} | {f.estimate_hours:g} | {f.description} |" for f in spec.must_have],
        "", "## Out of scope for the MVP", *[f"- {x}" for x in spec.out_of_scope],
        "", "## Tech stack (free, open source)", *[f"- {x}" for x in spec.tech_stack],
        "", "## Risks", *[f"- {x}" for x in spec.risks],
        "", "Code generation in a sandbox is STUBBED: this phase produces the spec, a clickable prototype and acceptance tests."]) + "\n"


def _acceptance_md(spec: MvpSpec, untestable: list[str], untraced: list[str], safety: list[str]) -> str:
    rows = [f"| {u.id} | {a} | {'testable' if _testable(a) else 'NOT testable'} |" for u in spec.user_stories for a in u.acceptance]
    return "\n".join([
        "# Phase 3, step 3: Acceptance tests and QA checks", "",
        "Each criterion below becomes a test the founder (or a later automated build) runs against the MVP.", "",
        "| Story | Acceptance criterion | Check |", "|---|---|---|", *rows, "",
        "## QA results (computed in code)",
        f"- Stories without a testable criterion: {', '.join(untestable) or 'none'}",
        f"- Features not traced to a story: {', '.join(untraced) or 'none'}",
        f"- Prototype safety problems: {', '.join(safety) or 'none'}"]) + "\n"


def _overlap(a: str, b: str) -> bool:
    words = {w for w in re.findall(r"[a-z]{4,}", a.lower())}
    return bool(words & set(re.findall(r"[a-z]{4,}", b.lower())))


EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")


def _pricing_md(plan: PricingPlan, claims, comps, core: list[str]) -> str:
    return "\n".join([
        "# Phase 4, step 1: Pricing proposal (no payment is configured or taken)", "",
        f"Core features that must stay free (they serve the primary user story): {', '.join(core)}", "",
        "| Tier | USD / month | Includes | For |", "|---|---|---|---|",
        *[f"| {t.name} | {t.price_usd_per_month:g} | {', '.join(t.includes)} | {t.who_for} |" for t in plan.tiers],
        "", "## Comparable products", *[f"- {c.md()}" for c in comps],
        "", f"Rationale: {plan.rationale}", "", f"How to test willingness to pay without taking money: {plan.price_test}",
        "", "## Claims", *[f"- {c.md()}" for c in claims]]) + "\n"


def _policy_md(p) -> str:
    return "\n\n".join([f"## {p.title} (DRAFT: review with a lawyer before launch; not legal advice)", *p.sections])


def _policies_md(pol: PolicyDrafts) -> str:
    return "\n".join([
        "# Phase 4, step 2: Policy drafts (DRAFT, for the founder to review and sign off)", "",
        "Data the MVP handles: " + ", ".join(pol.data_collected), "",
        _policy_md(pol.terms), "", _policy_md(pol.privacy), "", _policy_md(pol.refund)]) + "\n"


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
