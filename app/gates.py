"""Gates between phases.

Each gate produces a *recommendation* from pre-set thresholds (deterministic,
no model involved), then the founder makes the final call. The founder may
override, and the override is logged next to the recommendation so nobody
can later claim the evidence said something it did not.

Outcomes: go | repeat | pivot | stop.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field

OUTCOMES = ("go", "repeat", "pivot", "stop")


@dataclass
class Check:
    name: str
    target: str
    actual: str
    passed: bool


@dataclass
class GateResult:
    gate: str
    phase: int
    recommendation: str
    reasons: list[str]
    checks: list[Check] = field(default_factory=list)
    founder_decision: str | None = None
    founder_note: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)

    def md(self) -> str:
        rows = "\n".join(
            f"| {c.name} | {c.target} | {c.actual} | {'PASS' if c.passed else 'FAIL'} |" for c in self.checks
        )
        out = [
            f"# Phase {self.phase} gate: {self.gate}",
            "",
            f"**System recommendation: {self.recommendation.upper()}**",
            "",
            "Thresholds were fixed before the evidence was collected.",
            "",
            "| Check | Target (set in advance) | Actual | Result |",
            "|---|---|---|---|",
            rows,
            "",
            "## Why",
            *[f"- {r}" for r in self.reasons],
            "",
            "## Founder decision",
            f"- Decision: **{(self.founder_decision or 'pending').upper()}**",
        ]
        if self.founder_decision and self.founder_decision != self.recommendation:
            out.append(f"- Founder overrode the system recommendation ({self.recommendation}).")
        if self.founder_note:
            out.append(f"- Note: {self.founder_note}")
        return "\n".join(out) + "\n"


@dataclass(frozen=True)
class DiscoverThresholds:
    min_sourced_claims: int = 3
    min_sourced_ratio: float = 0.4
    min_pain_sources: int = 2
    min_opportunity_score: float = 3.0  # out of 5


def discover_gate(*, sourced_claims: int, total_claims: int, pain_sources: int,
                  best_score: float, excluded_reason: str | None,
                  t: DiscoverThresholds = DiscoverThresholds()) -> GateResult:
    ratio = sourced_claims / total_claims if total_claims else 0.0
    checks = [
        Check("Claims backed by a retrieved source", f">= {t.min_sourced_claims}", str(sourced_claims), sourced_claims >= t.min_sourced_claims),
        Check("Share of claims that are sourced", f">= {t.min_sourced_ratio:.0%}", f"{ratio:.0%}", ratio >= t.min_sourced_ratio),
        Check("Independent sources showing the pain", f">= {t.min_pain_sources}", str(pain_sources), pain_sources >= t.min_pain_sources),
        Check("Best opportunity score", f">= {t.min_opportunity_score}/5", f"{best_score:.1f}/5", best_score >= t.min_opportunity_score),
    ]
    if excluded_reason:
        return GateResult("evidence_gate", 1, "stop", [excluded_reason], checks)
    fails = [c for c in checks if not c.passed]
    evidence_fails = [c for c in fails if c.name != "Best opportunity score"]
    if not fails:
        rec, why = "go", ["All evidence thresholds met; proceed to Validate with the top opportunity."]
    elif len(fails) >= 3 or (pain_sources == 0 and best_score < t.min_opportunity_score):
        rec, why = "stop", ["Evidence is too weak to justify spending the founder's time and budget on validation."]
    elif not evidence_fails:
        rec, why = "pivot", ["The pain is documented but this angle scores poorly; pivot to a better-scoring opportunity."]
    else:
        rec, why = "repeat", ["Evidence is thin; repeat discovery with sharper queries or founder-supplied sources."]
    why += [f"Failed: {c.name} (target {c.target}, actual {c.actual})" for c in fails]
    return GateResult("evidence_gate", 1, rec, why, checks)


@dataclass(frozen=True)
class DemandTargets:
    """Set by the Validate agent and approved by the founder BEFORE the test runs."""
    waitlist_signups: int
    window_days: int
    interviews: int
    pain_confirm_rate: float  # share of interviewees who confirm the problem


def demand_gate(targets: DemandTargets, *, signups: int, interviews_done: int, pain_confirmed: int) -> GateResult:
    sig_ratio = signups / targets.waitlist_signups if targets.waitlist_signups else 0.0
    pain_rate = pain_confirmed / interviews_done if interviews_done else 0.0
    checks = [
        Check("Waitlist sign-ups (real, counted by the app)", f">= {targets.waitlist_signups} in {targets.window_days} days", str(signups), signups >= targets.waitlist_signups),
        Check("Customer interviews completed", f">= {targets.interviews}", str(interviews_done), interviews_done >= targets.interviews),
        Check("Interviewees confirming the problem", f">= {targets.pain_confirm_rate:.0%}", f"{pain_rate:.0%}", pain_rate >= targets.pain_confirm_rate),
    ]
    fails = [c for c in checks if not c.passed]
    if not fails:
        rec, why = "go", ["Demand targets met; proceed to Build."]
    elif interviews_done >= targets.interviews and pain_rate < targets.pain_confirm_rate / 2:
        rec, why = "stop", ["Interviews show customers do not feel this problem strongly; do not build this."]
    elif sig_ratio < 0.25 and pain_rate < targets.pain_confirm_rate:
        rec, why = "stop", ["Both the landing page and the interviews fell far short of the targets set in advance."]
    elif sig_ratio < 0.25:
        rec, why = "pivot", ["People confirm the problem but did not sign up; pivot the offer, audience or channel."]
    else:
        rec, why = "repeat", ["Close to target; extend the test window once, without changing the target."]
    why += [f"Failed: {c.name} (target {c.target}, actual {c.actual})" for c in fails]
    return GateResult("demand_gate", 2, rec, why, checks)
