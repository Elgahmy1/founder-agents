"""Read-only replay of the runs recorded in the committed decision_log.json.

Lets anyone see a real run end to end (phases, gates, the founder's decisions,
approvals, outputs and every logged action) the moment the app starts, before
any model is downloaded. Nothing is re-run and no model is called: every row
comes from the log, and every file link from outputs/.
"""
from __future__ import annotations

import html
import re
from collections import defaultdict
from pathlib import Path

GATES = {1: "evidence_gate", 2: "demand_gate", 3: "build_gate", 4: "commercial_gate", 5: "launch_gate", 6: "learn_gate"}
PHASES = {1: "Discover", 2: "Validate", 3: "Build", 4: "Commercial setup", 5: "Launch", 6: "Operate and learn"}


def _slug(idea: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", idea.split(".")[0].lower()).strip("-")[:24].strip("-")
    return s or "run"


def runs(entries: list[dict]) -> dict[str, dict]:
    out: dict[str, dict] = defaultdict(lambda: {"idea": "", "entries": [], "gates": [], "decisions": [], "calls": 0,
                                                "tokens": 0, "cost": 0.0, "phase": 0, "approvals": 0, "policy_stop": None})
    for e in entries:
        rid = e.get("run_id")
        if not rid:
            continue
        r = out[rid]
        r["entries"].append(e)
        r["cost"] += float(e.get("cost") or 0)
        if e["action"] == "start_run":
            r["idea"] = e.get("detail") or ""
        if e.get("model"):
            r["calls"] += 1
            r["tokens"] += int(e.get("tokens") or 0)
        if isinstance(e.get("phase"), int):
            r["phase"] = max(r["phase"], e["phase"])
        if e["agent"] == "gate":
            r["gates"].append(e)
        if e["agent"] == "founder" and e["action"].endswith("_gate_decision"):
            r["decisions"].append(e)
        if e["agent"] == "founder" and e["action"].startswith("approve_"):
            r["approvals"] += 1
        if e["action"] == "screen_brief" and e.get("outcome") == "stop":
            r["policy_stop"] = e.get("detail") or "stopped by the policy screen"
    for r in out.values():
        r["slug"] = _slug(r["idea"])
        r["ended"] = ("stop (policy screen)" if r["policy_stop"] else
                      r["decisions"][-1].get("outcome") if r["decisions"] else "waiting at a gate")
    return dict(out)


def run_outputs(slug: str, outputs_dir: Path) -> list[str]:
    return sorted(p.name for p in Path(outputs_dir).glob(f"phase*-{slug}.*"))


def runs_table(rs: dict[str, dict]) -> str:
    rows = "".join(
        f"<tr><td><a href='/replay/{html.escape(rid)}'>{html.escape(r['idea'][:90])}</a></td>"
        f"<td>{r['phase'] or '-'}</td><td>{len(r['decisions'])}</td><td>{html.escape(str(r['ended']).upper())}</td></tr>"
        for rid, r in sorted(rs.items(), key=lambda kv: kv[1]["entries"][0]["timestamp"]))
    return (f"<table><tr><th>Idea</th><th>Phase reached</th><th>Founder gate decisions</th><th>Ended</th></tr>{rows}</table>")


def render_run(rid: str, r: dict, outputs: list[str], log_valid: bool) -> str:
    def cell(x) -> str:
        return html.escape("" if x is None else str(x))
    # pair each gate recommendation with the founder decision that followed it (a recomputed gate has none)
    pairs, open_gate = {}, {}
    for e in r["entries"]:
        if e["agent"] == "gate":
            open_gate[e["action"]] = id(e)
        elif e in r["decisions"]:
            gid = open_gate.pop(e["action"].removesuffix("_decision"), None)
            if gid is not None:
                pairs[gid] = e
    gate_rows = []
    for g in r["gates"]:
        d = pairs.get(id(g))
        gate_rows.append(
            f"<tr><td>{cell(g.get('phase'))} {cell(PHASES.get(g.get('phase'), ''))}</td><td>{cell(g['action'].replace('_', ' '))}</td>"
            f"<td><b class='{cell(g.get('outcome'))}'>{cell(str(g.get('outcome')).upper())}</b></td>"
            f"<td>{'<b class=' + chr(39) + cell(d.get('outcome')) + chr(39) + '>' + cell(str(d.get('outcome')).upper()) + '</b>' if d else '<span class=mut>recomputed before a decision</span>'}"
            f"{' <span class=' + chr(39) + 'tag repeat' + chr(39) + '>override</span>' if d and d.get('founder_override') else ''}</td>"
            f"<td>{cell(g['timestamp'][11:16])}</td></tr>")
    stepper = "".join(
        f"<div class='ph {'done' if p <= r['phase'] else 'off'}'><span>{p}</span>{PHASES[p]}</div>" for p in range(1, 7))
    files = "".join(f"<li><a href='/outputs/{html.escape(o)}' target='_blank'>{html.escape(o)}</a></li>" for o in outputs)
    timeline = "".join(
        f"<tr><td>{cell(e['timestamp'][11:19])}</td><td>{cell(e.get('phase'))}</td><td>{cell(e['agent'])}</td>"
        f"<td>{cell(e['action'])}</td><td>{cell(e.get('outcome'))}</td><td>{cell(e.get('model') or '-')}</td>"
        f"<td>{len(e.get('sources') or [])}</td><td>{cell(e.get('approved_by') or '')}</td>"
        f"<td class=mut>{cell((e.get('detail') or '')[:140])}</td></tr>" for e in r["entries"])
    return f"""<div class="card"><div class="kicker">Replay of a real run from decision_log.json</div>
<h1>{cell(r['idea'][:160])}</h1>
<p class="mut">Run <code>{cell(rid)}</code>, {cell(r['entries'][0]['timestamp'][:16].replace('T', ' '))} to
{cell(r['entries'][-1]['timestamp'][11:16])} UTC. Read-only: nothing is re-run and no model is called. Every row below is a
logged agent action; the decision log's hash chain is <b class="{'go' if log_valid else 'stop'}">{'valid' if log_valid else 'BROKEN'}</b>.</p>
<div class="stepper">{stepper}</div>
<p>{r['calls']} model calls · {r['tokens']:,} tokens · ${r['cost']:.2f} · {len(r['decisions'])} founder gate decisions ·
{r['approvals']} founder approvals · ended: <b class="{cell(str(r['ended']).split()[0])}">{cell(str(r['ended']).upper())}</b></p>
{f"<p class='stop'>{cell(r['policy_stop'])}</p>" if r['policy_stop'] else ''}</div>
<div class="card"><h2>Gates: system recommendation and founder decision</h2>
<table><tr><th>Phase</th><th>Gate</th><th>System recommended</th><th>Founder decided</th><th>UTC</th></tr>{''.join(gate_rows)
or '<tr><td class=mut colspan=5>No gate reached</td></tr>'}</table></div>
<div class="card"><h2>Outputs ({len(outputs)})</h2><ul class="files">{files or '<li class=mut>No committed outputs for this run</li>'}</ul></div>
<div class="card"><h2>Every logged action ({len(r['entries'])})</h2><div style="overflow-x:auto"><table>
<tr><th>UTC</th><th>Phase</th><th>Agent</th><th>Action</th><th>Outcome</th><th>Model</th><th>Sources</th><th>Approved by</th><th>Detail</th></tr>
{timeline}</table></div></div>"""
