"""Phases 4-6 agents (phase 3 Build is built: app/agents/builder.py). STUBBED in this prototype: each one records what it
would do and which gate it would hit, without calling a model or any
external service. See ARCHITECTURE.md for the full design."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class StubPhase:
    phase: int
    name: str
    core_step: str
    agents: tuple[str, ...]
    would_do: tuple[str, ...]
    gate: str


STUB_PHASES = (
    StubPhase(4, "Commercial setup", "Set the price and policies", ("pricer", "policy_drafter"),
              ("Propose price points from sourced comparables (or labelled assumptions)",
               "Draft terms, privacy and refund policies, marked DRAFT for founder or lawyer review"),
              "founder approves price and signs off policies"),
    StubPhase(5, "Launch", "Open the store; deliver automatically", ("launcher", "delivery"),
              ("Draft the store page and launch posts for founder approval",
               "Deliver the product automatically after a (MOCKED) payment event, idempotently"),
              "founder approves each post; payment_test_log passes"),
    StubPhase(6, "Operate and learn", "None", ("support", "metrics", "analyst"),
              ("Draft support replies for founder approval",
               "Track activation/retention against targets set at launch",
               "Write a persevere-or-pivot memo"),
              "metrics vs targets -> persevere / pivot / stop"),
)


def stub_report(p: StubPhase) -> str:
    lines = [f"# Phase {p.phase}: {p.name} (STUBBED)", "",
             "This phase is STUBBED in the prototype. Nothing below was executed.", "",
             f"- Core step: {p.core_step}", f"- Agents: {', '.join(p.agents)}", "- Would do:"]
    lines += [f"  - {w}" for w in p.would_do]
    lines += [f"- Gate: {p.gate}"]
    return "\n".join(lines) + "\n"
