"""Stub phases. All six phases are built now (phase 6: app/agents/operator.py); this stays for runs saved by older versions. STUBBED in this prototype: each one records what it
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


STUB_PHASES: tuple[StubPhase, ...] = (
)


def stub_report(p: StubPhase) -> str:
    lines = [f"# Phase {p.phase}: {p.name} (STUBBED)", "",
             "This phase is STUBBED in the prototype. Nothing below was executed.", "",
             f"- Core step: {p.core_step}", f"- Agents: {', '.join(p.agents)}", "- Would do:"]
    lines += [f"  - {w}" for w in p.would_do]
    lines += [f"- Gate: {p.gate}"]
    return "\n".join(lines) + "\n"
