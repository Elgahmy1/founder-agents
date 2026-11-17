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
    max_attempts: int = 2  # one repeat/pivot is allowed; a second failing pass means stop


def discover_gate(*, sourced_claims: int, total_claims: int, pain_sources: int,
                  best_score: float, excluded_reason: str | None, attempt: int = 1,
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
    elif attempt >= t.max_attempts and pain_sources < t.min_pain_sources:
        rec, why = "stop", [f"Discovery attempt {attempt}: still fewer than {t.min_pain_sources} independent sources show people feel this problem. "
                            "One repeat is allowed; spending more of the founder's time on this idea is not justified."]
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


@dataclass(frozen=True)
class BuildThresholds:
    """Fixed before the builder runs."""
    weeks: int = 4                 # build budget = founder hours/week x weeks
    max_must_have: int = 6         # more than this is not an MVP
    min_stories: int = 2
    max_attempts: int = 2          # one rebuild allowed, then stop


def build_gate(*, stories: int, untestable_stories: list[str], untraced_features: list[str],
               must_have: int, total_hours: float, hours_per_week: float, safety_problems: list[str],
               guard_removed: list[str], attempt: int = 1, t: BuildThresholds = BuildThresholds()) -> GateResult:
    budget = hours_per_week * t.weeks
    checks = [
        Check("User stories", f">= {t.min_stories}", str(stories), stories >= t.min_stories),
        Check("Stories with testable acceptance criteria", "all", f"{stories - len(untestable_stories)}/{stories}",
              not untestable_stories),
        Check("Must-have features traced to a story", "all", f"{must_have - len(untraced_features)}/{must_have}",
              not untraced_features),
        Check("Must-have features (MVP size)", f"<= {t.max_must_have}", str(must_have), must_have <= t.max_must_have),
        Check("Estimated build hours", f"<= {budget:g} ({hours_per_week:g} h/week x {t.weeks})", f"{total_hours:g}",
              total_hours <= budget),
        Check("Prototype safety (no scripts, forms, passwords, external links)", "0 problems",
              ", ".join(safety_problems) or "0", not safety_problems),
        Check("Guard removed lines from prototype", "0", str(len(guard_removed)), not guard_removed),
    ]
    failed = [c for c in checks if not c.passed]
    over_scope = total_hours > budget or must_have > t.max_must_have
    reasons: list[str] = []
    if not failed:
        rec = "go"
        reasons.append("Scope fits the founder's hours, every feature traces to a story and every story can be tested.")
    elif safety_problems:
        rec = "repeat"
        reasons.append("The prototype failed a safety check; it must be rebuilt before anyone sees it.")
    elif over_scope and attempt >= t.max_attempts:
        rec = "stop"
        reasons.append(f"Build attempt {attempt}: scope still exceeds the founder's {budget:g} hours after a rebuild. "
                       "The MVP cannot be built within the stated time.")
    elif over_scope:
        rec = "pivot"
        reasons.append(f"Scope exceeds the {budget:g}-hour budget: cut to a smaller MVP rather than shrink estimates.")
    else:
        rec = "repeat"
        reasons.append("Fix the failed checks (testable criteria, traceability) and rebuild.")
    for c in failed:
        reasons.append(f"Failed: {c.name} (target {c.target}, actual {c.actual}).")
    return GateResult("build_gate", 3, rec, reasons, checks)


@dataclass(frozen=True)
class CommercialThresholds:
    """Fixed before the pricer runs."""
    min_comparables: int = 2
    min_policy_sections: int = 3
    max_attempts: int = 2


def commercial_gate(*, free_tier_with_core: bool, comparables: int, sourced_comparables: int,
                    paid_tiers_without_basis: int, policies_complete: list[str], policies_missing: list[str],
                    guard_flags: list[str], privacy_covers_data: bool, attempt: int = 1,
                    t: CommercialThresholds = CommercialThresholds()) -> GateResult:
    checks = [
        Check("Core, privacy and safety features in a free tier (no paywall)", "yes", "yes" if free_tier_with_core else "no",
              free_tier_with_core),
        Check("Comparable products listed (each price SOURCED or labelled ASSUMPTION)", f">= {t.min_comparables}", str(comparables), comparables >= t.min_comparables),
        Check("Price basis disclosed (SOURCED or labelled ASSUMPTION)", "all paid tiers",
              "all" if not paid_tiers_without_basis else f"{paid_tiers_without_basis} without basis",
              not paid_tiers_without_basis),
        Check("Policy drafts complete (terms, privacy, refund)", "3/3", f"{len(policies_complete)}/3", not policies_missing),
        Check("Privacy draft lists the data the MVP handles", "yes", "yes" if privacy_covers_data else "no", privacy_covers_data),
        Check("Guard flags in pricing and policies", "0", str(len(guard_flags)), not guard_flags),
    ]
    failed = [c for c in checks if not c.passed]
    reasons: list[str] = []
    if not failed:
        rec = "go"
        reasons.append("Core stays free, prices state their basis, and all three policy drafts are ready for the founder to sign.")
        if sourced_comparables == 0:
            reasons.append("No comparable price was found in a retrieved source: every price is an ASSUMPTION to test "
                           "with the price test before launch.")
    elif attempt >= t.max_attempts:
        rec = "stop"
        reasons.append(f"Commercial attempt {attempt}: the plan still fails required checks after a redraft.")
    else:
        rec = "repeat"
        reasons.append("Redraft: the failed checks below are sent back to the pricer and policy drafter.")
    for c in failed:
        reasons.append(f"Failed: {c.name} (target {c.target}, actual {c.actual}).")
    return GateResult("commercial_gate", 4, rec, reasons, checks)


@dataclass(frozen=True)
class LaunchThresholds:
    """Fixed before the launcher runs."""
    min_posts: int = 1
    max_attempts: int = 2


def launch_gate(*, store_safe: list[str], store_guard_removed: list[str], prices_match_approved: bool,
                posts_ok: int, posts_flagged: int, targets_set: bool, payment_test_passed: bool,
                policies_signed: bool, attempt: int = 1, t: LaunchThresholds = LaunchThresholds()) -> GateResult:
    checks = [
        Check("Store page safety (no scripts, forms, external links)", "0 problems", ", ".join(store_safe) or "0", not store_safe),
        Check("Guard flags on store page (removed lines or whole page)", "0", str(len(store_guard_removed)), not store_guard_removed),
        Check("Store prices equal the founder-approved pricing", "yes", "yes" if prices_match_approved else "no",
              prices_match_approved),
        Check("Launch posts that pass the guard", f">= {t.min_posts}", str(posts_ok), posts_ok >= t.min_posts),
        Check("Launch posts blocked by the guard", "0", str(posts_flagged), posts_flagged == 0),
        Check("Launch targets proposed before launch", "yes", "yes" if targets_set else "no", targets_set),
        Check("Policies signed off in Phase 4", "yes", "yes" if policies_signed else "no", policies_signed),
        Check("Sale-to-cash test (MOCKED): delivery, idempotency, refund, reconciliation", "PASS",
              "PASS" if payment_test_passed else "FAIL", payment_test_passed),
    ]
    failed = [c for c in checks if not c.passed]
    reasons: list[str] = []
    if not failed:
        rec = "go"
        reasons.append("The store page, launch posts, targets and the (MOCKED) sale-to-cash path are ready. "
                       "GO needs the founder to approve the page and lock the targets.")
    elif attempt >= t.max_attempts:
        rec = "stop"
        reasons.append(f"Launch attempt {attempt}: required launch checks still fail after a redraft.")
    else:
        rec = "repeat"
        reasons.append("Redraft the launch kit: the failed checks below are sent back to the launcher.")
    for c in failed:
        reasons.append(f"Failed: {c.name} (target {c.target}, actual {c.actual}).")
    return GateResult("launch_gate", 5, rec, reasons, checks)


def learn_gate(*, targets: dict, visits: int, signups: int, paid_orders: int, feedback_items: int,
               problem_mentions: int) -> GateResult:
    """Phase 6: results vs the launch targets the founder locked before launch."""
    tv, ts = max(1, targets["store_visits"]), max(1, targets["free_signups"])
    checks = [
        Check("Store visits in the window", f">= {tv}", str(visits), visits >= tv),
        Check("Free sign-ups (counted by the app from real form posts)", f">= {ts}", str(signups), signups >= ts),
        Check("Users who wrote feedback", ">= 3", str(feedback_items), feedback_items >= 3),
    ]
    reasons = [f"Paid orders: target {targets['paid_orders']}, recorded {paid_orders}. Checkout is MOCKED in this "
               "prototype, so paid orders are reported, not used for the recommendation."]
    share = signups / ts
    if all(c.passed for c in checks):
        rec = "go"
        reasons.insert(0, "Every launch target was met: persevere and keep operating.")
    elif share >= 0.5:
        rec = "repeat"
        reasons.insert(0, f"Sign-ups reached {share:.0%} of target: run another window with the same targets before deciding.")
    elif share >= 0.25 or problem_mentions >= 2:
        rec = "pivot"
        reasons.insert(0, "Some pull but well under target: go back to Discover with what users said.")
    else:
        rec = "stop"
        reasons.insert(0, f"Sign-ups reached {share:.0%} of target (under 25%) and feedback does not show the problem. "
                          "Stopping now saves the founder's time and money.")
    return GateResult("learn_gate", 6, rec, reasons, checks)
