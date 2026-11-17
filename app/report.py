"""Founder export: one Markdown file with everything a run did, built from saved state only (no model calls).

The founder can keep it, share it with a co-founder or mentor, or attach it to a pitch. It contains the brief,
every gate (recommendation, checks, founder decision and note), every approval item and its outcome,
the evidence split, model usage, this run's decision-log entries, and the text outputs themselves.
"""
from __future__ import annotations

from pathlib import Path

PHASES = {1: "Discover", 2: "Validate", 3: "Build", 4: "Commercial setup", 5: "Launch", 6: "Operate and learn"}


def _cell(v) -> str:
    return str(v if v is not None else "").replace("|", "/").replace("\n", " ")


def build_run_report(st, q, log_entries: list[dict], outputs_dir: Path) -> str:
    b = st.brief
    out = [f"# Founder Agents run report: {b.get('idea', '')}", "",
           f"Run `{st.run_id}`, current stage `{st.stage}`. Exported from saved run state; nothing here was generated "
           "for the export. MOCKED and STUBBED parts are labelled as in the app.", "",
           "## Brief", ""]
    out += [f"- **{k.replace('_', ' ')}:** {_cell(v)}" for k, v in b.items() if v not in (None, "", [])]

    out += ["", "## Gates", "", "| Phase | Gate | System recommended | Founder decided | Note |", "|---|---|---|---|---|"]
    for g in st.gates:
        dec = g.get("founder_decision") or "waiting"
        if g.get("founder_decision") and g["founder_decision"] != g["recommendation"]:
            dec += " (override)"
        out.append(f"| {g['phase']} {PHASES.get(g['phase'], '')} | {g['gate']} | {g['recommendation'].upper()} | "
                   f"{dec.upper()} | {_cell(g.get('founder_note'))} |")
    for g in st.gates:
        if g.get("checks"):
            out += ["", f"### Phase {g['phase']} {g['gate']} checks", "", "| Check | Target | Actual | Result |", "|---|---|---|---|"]
            out += [f"| {_cell(c['name'])} | {_cell(c['target'])} | {_cell(c['actual'])} | {'PASS' if c['passed'] else 'FAIL'} |"
                    for c in g["checks"]]
            out += [f"- {r}" for r in g.get("reasons", [])]

    out += ["", "## Approvals (publish, send, spend, sign)", "",
            "| Phase | Kind | Item | Status | Decided | Result |", "|---|---|---|---|---|---|"]
    out += [f"| {i.phase} | {i.kind} | {_cell(i.title)} | {i.status} | {_cell(i.decided_at)} | {_cell(i.result)} |" for i in q.items]
    if not q.items:
        out.append("| - | - | No approval items yet | - | - | - |")

    if st.ledger:
        n_s = sum(1 for c in st.ledger if c["status"] == "SOURCED")
        out += ["", "## Evidence", "", f"{n_s} of {len(st.ledger)} claims cite a source; the rest are labelled ASSUMPTION."]
    u = st.usage or {}
    out += ["", "## Model usage", "", f"{u.get('calls', 0)} model calls, "
            f"{u.get('prompt_tokens', 0) + u.get('completion_tokens', 0)} tokens, cost $0.00 (open-weight model, free tier or local)."]

    out += ["", "## Decision log for this run", "", "| Time (UTC) | Agent | Action | Outcome | Approved by |", "|---|---|---|---|---|"]
    out += [f"| {_cell(e.get('timestamp'))} | {_cell(e.get('agent'))} | {_cell(e.get('action'))} | "
            f"{_cell(e.get('outcome') or e.get('recommendation'))} | {_cell(e.get('approved_by'))} |"
            for e in log_entries if e.get("run_id") == st.run_id]

    out += ["", "## Outputs", ""]
    for name in st.outputs:
        p = outputs_dir / name
        if not p.exists():
            out.append(f"- `{name}` (file missing)")
        elif p.suffix != ".md":
            out.append(f"- `{name}` (HTML page: open it in the app)")
    for name in st.outputs:
        p = outputs_dir / name
        if p.exists() and p.suffix == ".md":
            text = p.read_text(encoding="utf-8").replace("\n# ", "\n### ").replace("\n## ", "\n#### ")
            out += ["", f"### `{name}`", "", text.lstrip("# ").strip() if text.startswith("# ") else text.strip()]
    return "\n".join(out) + "\n"
