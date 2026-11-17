"""Web UI (FastAPI, server-rendered). Every outward action goes through the
founder's approve/reject buttons, which call ApprovalQueue.decide()."""
from __future__ import annotations

import html
import threading
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, PlainTextResponse, RedirectResponse

from app import analytics, guard, mvp_app, replay, sandbox, transcribe
import json
from app.agents.advisor import AdvisorAgent
from app.brief import FounderBrief
from app.config import load_settings
from app.decision_log import validate
from app.llm import make_llm
from app.orchestrator import Orchestrator, RunState

settings = load_settings()
llm = make_llm(settings)
orch = Orchestrator(settings, llm)
app = FastAPI(title="Founder Agents")
_busy: dict[str, str] = {}

STATUS = [
    ("Phase 1 Discover: research, opportunities, market, Mom Test plan, evidence gate", "Working"),
    ("Phase 2 Validate: Lean Canvas, landing page, demand targets, demand gate", "Working"),
    ("Landing page public hosting (served locally only)", "MOCKED"),
    ("Sending outreach messages (founder sends personally)", "MOCKED"),
    ("Phase 3 Build: MVP spec, clickable prototype, acceptance tests, build gate", "Working"),
    ("Phase 3 core code generated and tested in a sandbox; MVP app served locally", "Working"),
    ("Phase 3 MVP app: storage, accounts and public hosting", "STUBBED"),
    ("Phase 4 Commercial setup: pricing with a free core tier, policy drafts, founder sign-off, commercial gate", "Working"),
    ("Phase 5 Launch: store page, launch post drafts, launch targets, launch gate", "Working"),
    ("Phase 5 checkout, public hosting and posting", "MOCKED"),
    ("Phase 6 Operate and learn: results vs locked targets, support reply drafts, learn gate, learning memo", "Working"),
    ("Phase 6 usage analytics: store visits, landing and MVP app views and MVP app runs counted by the app (no cookies or IPs)", "Working"),
]

CSS = """
:root{--bg:#f7f7f9;--fg:#1d1d1f;--mut:#666;--card:#fff;--line:#e2e2e8;--acc:#3b3bd6;--ok:#0a7a3d;--warn:#a15c00;--bad:#b3261e}
@media (prefers-color-scheme: dark){:root{--bg:#141418;--fg:#ececf1;--mut:#a0a0aa;--card:#1d1d23;--line:#2e2e36;--acc:#8f8fff;--ok:#4cc38a;--warn:#e0a650;--bad:#ff7b72}}
body{font-family:system-ui,sans-serif;background:var(--bg);color:var(--fg);max-width:980px;margin:0 auto;padding:16px}
a{color:var(--acc)} .card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:16px;margin:14px 0}
input,textarea,select{width:100%;box-sizing:border-box;padding:8px;border:1px solid var(--line);border-radius:6px;background:var(--bg);color:var(--fg);font:inherit}
button{padding:8px 14px;border:0;border-radius:6px;background:var(--acc);color:#fff;font-weight:600;cursor:pointer;margin:4px 4px 0 0}
button.rej{background:var(--bad)} .tag{display:inline-block;font-size:.75rem;font-weight:700;padding:2px 8px;border-radius:99px;border:1px solid currentColor}
.Working{color:var(--ok)} .MOCKED,.STUBBED,.MOCKED-STUBBED{color:var(--warn)} .go{color:var(--ok)} .stop{color:var(--bad)} .repeat,.pivot{color:var(--warn)}
table{border-collapse:collapse;width:100%} td,th{border-bottom:1px solid var(--line);padding:6px;text-align:left;vertical-align:top}
pre{white-space:pre-wrap;background:var(--bg);padding:10px;border-radius:6px;max-height:320px;overflow:auto}
label{display:block;margin-top:8px;font-weight:600;font-size:.9rem} .mut{color:var(--mut);font-size:.9rem}
.stepper{display:grid;grid-template-columns:repeat(6,1fr);gap:6px;margin:12px 0}
.ph{border:1px solid var(--line);border-radius:8px;padding:8px;background:var(--card);font-size:.85rem;display:flex;flex-direction:column;gap:2px}
.ph span{font-weight:800;color:var(--mut)} .ph small{color:var(--warn);font-weight:700;font-size:.7rem}
.ph.done{border-color:var(--ok)} .ph.done span{color:var(--ok)} .ph.cur{border:2px solid var(--acc)} .ph.cur span{color:var(--acc)}
.ph.stopped{border:2px solid var(--bad)} .ph.stopped span{color:var(--bad)} .ph.off,.ph.stub{opacity:.55}
.next{border:2px solid var(--acc)} .next.end{border-color:var(--line)} .kicker{text-transform:uppercase;font-size:.75rem;font-weight:800;letter-spacing:.04em;color:var(--acc)}
.next h2{margin:.3rem 0 .6rem} .row{display:flex;gap:6px;flex-wrap:wrap}
.opts{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:8px;margin-top:8px}
button.opt{display:flex;flex-direction:column;align-items:flex-start;text-align:left;background:var(--bg);color:var(--fg);border:1px solid var(--line);padding:10px;margin:0}
button.opt small{font-weight:400;color:var(--mut);margin-top:4px} button.opt.rec{border:2px solid var(--acc)}
button.opt.go b{color:var(--ok)} button.opt.stop b{color:var(--bad)} button.opt.repeat b,button.opt.pivot b{color:var(--warn)}
button:disabled{opacity:.5;cursor:wait}
.work{display:flex;gap:14px;align-items:flex-start;border:2px solid var(--warn)}
.spin{width:28px;height:28px;border:3px solid var(--line);border-top-color:var(--acc);border-radius:50%;animation:sp 1s linear infinite;flex:none}
.spin-sm{display:inline-block;width:12px;height:12px;border:2px solid var(--line);border-top-color:var(--acc);border-radius:50%;animation:sp 1s linear infinite;vertical-align:-2px}
@keyframes sp{to{transform:rotate(360deg)}}
.bar{height:10px;background:var(--line);border-radius:99px;overflow:hidden;margin:10px 0} .bar i{display:block;height:100%;background:var(--acc);transition:width .4s}
.bar.ev i{background:var(--ok)} .steps{list-style:none;padding:0;margin:0} .steps li{padding:3px 0;color:var(--mut)}
.steps li.ok{color:var(--ok)} .steps li.now{color:var(--fg);font-weight:700} .files li{margin:3px 0}
@media (max-width:640px){.stepper{grid-template-columns:repeat(3,1fr)}}
"""


def page(title: str, body: str, refresh: bool = False) -> HTMLResponse:
    meta = '<meta http-equiv="refresh" content="2">' if refresh else ""
    return HTMLResponse(f"""<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">{meta}<title>{html.escape(title)}</title>
<style>{CSS}</style></head><body><p><a href="/">Founder Agents</a> · model <code>{html.escape(llm.model)}</code>
{'' if llm.health() else '<span class="tag stop">model not reachable: check Ollama</span>'}</p>{body}
<script>document.querySelectorAll('form.once').forEach(f=>f.addEventListener('submit',e=>{{
const b=e.submitter;if(b&&b.name){{const h=document.createElement('input');h.type='hidden';h.name=b.name;h.value=b.value;f.appendChild(h);}}
setTimeout(()=>f.querySelectorAll('button').forEach(x=>x.disabled=true),0);}}));</script></body></html>""")


def tag(s: str) -> str:
    return f'<span class="tag {s.replace(" / ", "-")}">{html.escape(s)}</span>'


def _bg(run_id: str, label: str, fn, *args) -> None:
    if run_id in _busy:  # one background job per run; extra clicks are ignored
        return

    def work():
        try:
            fn(*args)
        finally:
            _busy.pop(run_id, None)
    _busy[run_id] = label
    threading.Thread(target=work, daemon=True).start()


@app.get("/", response_class=HTMLResponse)
def home():
    rows = "".join(
        f"<tr><td><a href='/runs/{r.run_id}'>{html.escape(r.brief['idea'][:80])}</a></td><td>{r.stage}</td></tr>"
        for r in orch.list_runs())
    status = "".join(f"<tr><td>{html.escape(s)}</td><td>{tag(t)}</td></tr>" for s, t in STATUS)
    return page("Founder Agents", f"""
<h1>Founder Agents</h1><p class="mut">An open-source team of agents that tests a founder's idea with sourced evidence,
and can recommend stopping. You approve everything that is published, sent, spent or signed.</p>
<div class="card"><h2>New founder brief</h2><form method="post" action="/runs">
<label>Your name</label><input name="founder_name" value="Founder">
<label>Starting idea</label><textarea name="idea" rows="3" required></textarea>
<label>Skills (comma separated)</label><input name="skills">
<label>Budget (USD)</label><input name="budget_usd" type="number" value="200">
<label>Hours per week</label><input name="hours_per_week" type="number" value="10">
<label>Target market</label><input name="target_market" required>
<label>Where will you sell? (country or city, optional: the agents check local fit, resources and competitors there)</label><input name="location" placeholder="e.g. Egypt, Cairo">
<label>Values (comma separated)</label><input name="values">
<label>Sources you already have (one URL per line, optional)</label><textarea name="source_urls" rows="2"></textarea>
<button>Start Discover</button></form></div>
<div class="card"><h2>Runs</h2><table>{rows or '<tr><td class=mut>No runs yet</td></tr>'}</table></div>
<div class="card"><h2>Recorded runs (replay, no model needed)</h2><p class="mut">Real runs committed in
<code>decision_log.json</code> and <code>outputs/</code>, shown read-only: open one to see every phase, gate, founder
decision and logged action. Useful while the local model is still downloading.</p>{replay.runs_table(replay.runs(orch.log.read()))}</div>
<div class="card"><h2>What works and what is mocked</h2><table>{status}</table></div>""")


def _split(s: str) -> list[str]:
    return [x.strip() for x in s.replace("\n", ",").split(",") if x.strip()]


@app.post("/runs")
def create_run(founder_name: str = Form("Founder"), idea: str = Form(...), skills: str = Form(""),
               budget_usd: float = Form(0), hours_per_week: float = Form(10), target_market: str = Form(...), location: str = Form(""),
               values: str = Form(""), source_urls: str = Form("")):
    brief = FounderBrief(founder_name=founder_name, idea=idea, skills=_split(skills), budget_usd=budget_usd,
                         hours_per_week=hours_per_week, target_market=target_market, location=location.strip(), values=_split(values),
                         source_urls=[u for u in _split(source_urls) if u.startswith("http")])
    st = orch.create(brief)
    if st.stage == "p1_running":
        _bg(st.run_id, "Phase 1 agents working", orch.advance, st.run_id)
    return RedirectResponse(f"/runs/{st.run_id}", status_code=303)


PHASES = [(1, "Discover", "Working"), (2, "Validate", "Working"), (3, "Build", "Working"),
          (4, "Commercial setup", "Working"), (5, "Launch", "Working"), (6, "Operate & learn", "Working")]
STAGE_PHASE = {"new": 1, "p1_running": 1, "p1_gate_wait": 1, "p2_running": 2, "p2_targets_wait": 2,
               "p2_collecting": 2, "p2_gate_wait": 2, "p3_running": 3, "p3_gate_wait": 3, "p3_6_stubbed": 3,
               "p4_6_stubbed": 4, "p4_running": 4, "p4_gate_wait": 4, "p5_6_stubbed": 5,
               "p5_running": 5, "p5_gate_wait": 5, "p6_stubbed": 6,
               "p6_collecting": 6, "p6_running": 6, "p6_gate_wait": 6, "done": 6, "stopped": 0}
OUTCOME_HELP = {
    "go": "Move on to the next phase.",
    "repeat": "Run this phase again (new research or a longer test).",
    "pivot": "Go back and try the next-best opportunity.",
    "stop": "End here. Stopping on weak evidence is a valid result.",
}


def _stepper(st: RunState) -> str:
    cur = STAGE_PHASE.get(st.stage, 1)
    stopped_at = st.gates[-1]["phase"] if st.stage == "stopped" and st.gates else None
    cells = []
    for n, name, status in PHASES:
        if stopped_at is not None:
            cls = "done" if n < stopped_at else ("stopped" if n == stopped_at else "off")
        elif st.stage == "done":
            cls = "done" if n <= (6 if st.operate else 5 if st.launch else 4 if st.pricing else 3 if st.mvp else 2) else "stub"
        else:
            cls = "done" if n < cur else ("cur" if n == cur else ("stub" if status != "Working" else "off"))
        label = "" if status == "Working" else f"<small>{status}</small>"
        cells.append(f"<div class='ph {cls}'><span>{n}</span><b>{name}</b>{label}</div>")
    return "<div class='stepper'>" + "".join(cells) + "</div>"


def _working(run_id: str, busy: str) -> str:
    pr = orch.progress.get(run_id)
    if not pr:
        return (f"<div class='card work'><div class='spin'></div><div><b>{html.escape(busy)}…</b>"
                "<p class=mut>The agents are thinking. This page updates by itself.</p></div></div>")
    steps, cur = pr["steps"], pr["current"]
    pct = int(100 * cur / len(steps))
    items = "".join(
        f"<li class='{'ok' if i < cur else ('now' if i == cur else '')}'>"
        f"{'✓' if i < cur else ('<span class=spin-sm></span>' if i == cur else '○')} {html.escape(t)}</li>"
        for i, t in enumerate(steps))
    return (f"<div class='card work'><div style='flex:1'><b>The agents are working ({cur + 1} of {len(steps)})</b>"
            f"<div class='bar'><i style='width:{max(pct, 4)}%'></i></div><ul class='steps'>{items}</ul>"
            "<p class=mut>This page updates by itself. You don't need to click anything.</p></div></div>")


def _gate_table(g: dict) -> str:
    rows = "".join(f"<tr><td>{html.escape(c['name'])}</td><td>{html.escape(c['target'])}</td><td>{html.escape(c['actual'])}</td>"
                   f"<td class='{'go' if c['passed'] else 'stop'}'><b>{'PASS' if c['passed'] else 'FAIL'}</b></td></tr>" for c in g["checks"])
    reasons = "".join(f"<li>{html.escape(r)}</li>" for r in g["reasons"])
    table = f"<table><tr><th>Check</th><th>Target (set in advance)</th><th>Actual</th><th></th></tr>{rows}</table>" if rows else ""
    return f"{table}<ul>{reasons}</ul>"


def _next_step(st: RunState, q, run_id: str) -> str:
    """The one card that tells the founder what to do now, in plain words."""
    pend = q.pending()
    if pend:
        i = pend[0]
        verb = {"publish": "publish", "send": "send", "spend": "spend", "sign": "sign"}[i.kind]
        why = ("Approving only marks it ready for <b>you</b> to send yourself; the system sends nothing (MOCKED)."
               if i.kind == "send" else "Approving puts the page live on this computer only; public hosting is MOCKED.")
        if i.kind == "sign":
            why = ("Approving records your sign-off in the decision log. Nothing is published or charged; "
                   "these are drafts to review with a lawyer before launch.")
        if i.executor == "post_launch_mock":
            why = "Approving only marks the post ready for <b>you</b> to post from your own account; the system posts nothing (MOCKED)."
        if i.executor == "publish_store_local":
            why = "Approving puts the store page live on this computer only. Checkout and public hosting are MOCKED."
        if i.executor == "lock_launch_targets":
            why = "Locking the targets now means the launch result can't be spun later."
        if i.kind == "publish" and "prototype" in i.title:
            why = (f"Approving lets you click through the prototype at <a href='/proto/{run_id}' target='_blank'>/proto/{run_id}</a>"
                   " on this computer. Nothing is deployed (public hosting is MOCKED).")
        shown = i.content
        if i.executor == "publish_mvp_local":
            b = json.loads(i.content)
            why = (f"Approving runs the MVP app at <a href='/mvp/{run_id}' target='_blank'>/mvp/{run_id}</a> on this computer. "
                   f"Each request runs <code>{html.escape(', '.join(b.get('funcs') or [b['func']]))}</code> below in the sandbox; nothing is stored. "
                   "Public hosting is MOCKED.")
            shown = b["code"]
        return f"""<div class="card next"><div class="kicker">Your approval is needed ({len(pend)} waiting)</div>
<h2>Do you want to {verb} this? {html.escape(i.title.split(':')[0])}</h2><p class=mut>{why}</p>
<pre>{html.escape(shown[:3000])}</pre><form method="post" action="/runs/{run_id}/approvals/{i.id}" class="once">
<input name="note" placeholder="Note (optional)"><div class="row"><button name="approve" value="1">Approve</button>
<button class="rej" name="approve" value="0">Reject</button></div></form></div>"""
    if st.stage == "p6_collecting":
        t = st.launch["targets"]
        u = orch.launch_usage(st)
        return f"""<div class="card next"><div class="kicker">Your input is needed: real launch results</div>
<h2>Enter what really happened in the {t['window_days']}-day launch window</h2>
<p>Targets you locked before launch: {t['store_visits']} store visits, {t['free_signups']} free sign-ups, {t['paid_orders']} paid orders.
These are counted by the app since launch (never typed in): <b>{max(0, orch.signups(run_id) - st.launch.get('signups_at_launch', 0))}</b> free sign-ups,
<b>{u['store']}</b> store visits, <b>{u['mvp_run']}</b> MVP app runs. Only a page name and a date are stored: no cookies or IP addresses;
views you open from this dashboard are not counted.</p>
<form method="post" action="/runs/{run_id}/operate" class="once"><label>Store visits from your own analytics (optional; leave empty to use the app's count)</label>
<input type="number" name="visits" min="0"><label>Paid orders recorded in your own payment provider (checkout is MOCKED here, so usually 0)</label>
<input type="number" name="paid_orders" min="0" value="0" required>
<label>Real user feedback, one item per line (optional)</label><textarea name="feedback" rows="4"></textarea>
<button>Run the learn gate</button></form>{_sales_import_html(st, run_id)}</div>"""
    if st.stage in ("p1_gate_wait", "p2_gate_wait", "p3_gate_wait", "p4_gate_wait", "p5_gate_wait", "p6_gate_wait"):
        g = st.gates[-1]
        rec = g["recommendation"]
        unsigned = st.stage == "p4_gate_wait" and any(
            i.executor == "sign_commercial" and i.status not in ("executed", "superseded") for i in q.items)
        if st.stage == "p4_gate_wait" and not any(i.executor == "sign_commercial" and i.status != "superseded" for i in q.items):
            unsigned = True
        if st.stage == "p5_gate_wait":
            need = [i for i in q.items if i.executor in ("publish_store_local", "lock_launch_targets") and i.status != "superseded"]
            unsigned = len(need) < 2 or any(i.status != "executed" for i in need)
        btns = "".join(
            f"<button name='decision' value='{o}' class='opt {o}{' rec' if o == rec else ''}'><b>{o.upper()}"
            f"{' (recommended)' if o == rec else ''}</b><small>{OUTCOME_HELP[o]}</small></button>"
            for o in ("go", "repeat", "pivot", "stop") if not (o == "go" and unsigned))
        if unsigned:
            btns += ("<p class=mut>GO needs your approval of the store page and your lock on the launch targets.</p>"
                     if st.stage == "p5_gate_wait" else
                     "<p class=mut>GO needs your approval of the pricing and your sign-off on all three policy drafts.</p>")
        return f"""<div class="card next"><div class="kicker">Your decision is needed: Phase {g['phase']} gate</div>
<h2>The system recommends <span class="{rec}">{rec.upper()}</span></h2>{_gate_table(g)}{_assumptions_html(st)}{_verdict_html(st) if g['phase'] == 1 else ''}{_fork_html(g, run_id)}
<form method="post" action="/runs/{run_id}/gate" class="once"><input name="note" placeholder="Why? (required if you overrule the recommendation; saved in the log)">
<div class="opts">{btns}</div></form><p class=mut>You can overrule the system. If you do, the log records both the recommendation and your decision.</p></div>"""
    if st.stage == "p2_targets_wait" and st.demand_plan:
        p = st.demand_plan
        return f"""<div class="card next"><div class="kicker">Your decision is needed: lock the targets before testing</div>
<h2>Success means: {p['waitlist_signups_target']} sign-ups in {p['window_days']} days, {p['interviews_target']} interviews,
{p['pain_confirm_rate_target']:.0%} confirm the problem</h2><p class=mut>{html.escape(p['rationale'])}</p>
<p>Locking them now means the result can't be spun later.</p>
<form method="post" action="/runs/{run_id}/targets" class="once"><div class="row"><button name="approve" value="1">Lock these targets</button>
<button class="rej" name="approve" value="0">Reject and re-plan</button></div></form></div>"""
    if st.stage == "p2_collecting":
        return f"""<div class="card next"><div class="kicker">Your input is needed: real results</div>
<h2>Run the test, then enter what really happened</h2>
<p>Share <a href="/lp/{run_id}" target="_blank">your landing page</a> and talk to customers using the interview plan.
Sign-ups so far (counted by the app, never typed in): <b>{orch.signups(run_id)}</b></p>
{_interviews_html(st, run_id)}
<form method="post" action="/runs/{run_id}/results" class="once"><label>Interviews completed</label><input type="number" name="interviews_done" min="0" required value="{len(st.interviews) if st.interviews else ''}">
<label>How many confirmed the problem</label><input type="number" name="pain_confirmed" min="0" required value="{sum(1 for i in st.interviews if i['analysis']['problem_confirmed']) if st.interviews else ''}">
<button>Run the demand gate</button></form></div>"""
    if st.stage == "stopped":
        g = st.gates[-1] if st.gates else None
        return ("<div class='card next end'><div class='kicker'>Run ended</div><h2 class='stop'>STOP</h2>"
                + (_gate_table(g) if g else "") + "<p>Stopping saved your time and money. Everything is in the decision log.</p></div>")
    if st.stage == "done":
        built = ("All six phases" if st.operate else
                 "Discover, Validate, Build, Commercial setup and Launch" if st.launch else
                 "Discover, Validate, Build and Commercial setup" if st.pricing else
                 "Discover, Validate and Build" if st.mvp else "Discover and Validate")
        rest = "" if st.operate else "6" if st.launch else "5-6" if st.pricing else "4-6" if st.mvp else "3-6"
        proto = (f" <a href='/proto/{run_id}' target='_blank'>Open the prototype</a>."
                 if (settings.data_dir / "sites" / run_id / "prototype.html").exists() else "")
        passed = {g["gate"] for g in st.gates if g.get("founder_decision") == "go"}
        nxt = (3, "Build") if (not st.mvp and "demand_gate" in passed) else \
              (4, "Commercial setup") if (st.mvp and not st.pricing and "build_gate" in passed) else \
              (5, "Launch") if (st.pricing and not st.launch and "commercial_gate" in passed) else \
              (6, "Operate and learn") if (st.launch and not st.operate and "launch_gate" in passed) else None
        build_btn = (f"<form method='post' action='/runs/{run_id}/build' class='once'><p>This run finished before Phase {nxt[0]} "
                     f"was available. You passed the gate before it, so it can continue now.</p>"
                     f"<button>Run Phase {nxt[0]} {nxt[1]}</button></form>" if nxt else "")
        return (f"<div class='card next end'><div class='kicker'>Run finished</div><h2 class='go'>{built} complete</h2>"
                + (f"<p>Phases {rest} are STUBBED in this prototype: their reports below describe what would happen next.{proto}</p>" if rest else
                   f"<p>The founder chose to persevere: keep operating and re-run the learn gate each window.{proto}</p>") + f"{build_btn}</div>")
    return ""


@app.get("/runs/{run_id}", response_class=HTMLResponse)
def view_run(run_id: str):
    try:
        st, q = orch.load(run_id)
    except FileNotFoundError:
        raise HTTPException(404)
    busy = _busy.get(run_id)
    body = [f"<h1>{html.escape(st.brief['idea'][:120])}</h1>", _stepper(st)]
    if busy:
        body.append(_working(run_id, busy))
    elif st.error:
        body.append(f"<div class='card next'><div class='kicker stop'>Something went wrong</div><p>{html.escape(st.error)}</p>"
                    f"<form method=post action='/runs/{run_id}/retry' class='once'><button>Try this step again</button></form></div>")
    else:
        body.append(_next_step(st, q, run_id))
    past = [g for g in st.gates[:-1]] if not busy and st.stage in ("p1_gate_wait", "p2_gate_wait", "p3_gate_wait") else st.gates
    if past and not (not busy and st.stage == "stopped"):
        body.append("<div class='card'><h2>Gate history</h2>" + "".join(
            f"<p><b>Phase {g['phase']} {g['gate']}</b>: system said <b class='{g['recommendation']}'>{g['recommendation'].upper()}</b>"
            + (f", you chose <b class='{g['founder_decision']}'>{g['founder_decision'].upper()}</b>"
               + (" <span class='tag repeat'>override</span>" if g['founder_decision'] != g['recommendation'] else "")
               if g.get('founder_decision') else "") + "</p>" for g in past) + "</div>")
    tech = []
    if st.outputs:
        tech.append("<h3>What the agents produced</h3><ul class='files'>" + "".join(
            f"<li><a href='/outputs/{o}' target='_blank'>{o}</a>{' ' + tag('STUBBED') if 'STUBBED' in o else ''}</li>"
            for o in st.outputs) + "</ul>")
    if st.ledger:
        n_s = sum(1 for c in st.ledger if c["status"] == "SOURCED")
        n = len(st.ledger)
        body.append(f"<div class='card'><h2>Evidence</h2><div class='bar ev'><i style='width:{int(100 * n_s / n)}%'></i></div>"
                    f"<p>{n_s} claims backed by a real source · {n - n_s} labelled ASSUMPTION</p></div>")
    done = [i for i in q.items if i.status != "pending"]
    if done:
        tech.append("<h3>Approval history</h3><table>" + "".join(
            f"<tr><td>{i.kind}</td><td>{html.escape(i.title)}</td><td>{i.status}</td><td>{html.escape(i.result or '')}</td></tr>"
            for i in done) + "</table>")
    if st.mvp and not busy:
        c = st.code
        res = (f"Last run: <b class='{'go' if c['ok'] else 'stop'}'>{c['passed']}/{c['total']} acceptance checks passed</b> "
               "(see phase3_step4_code above). " if c else "")
        body.append("<div class='card'><h2>MVP core code (Phase 3, sandbox)</h2>"
                    f"<p>{res}The coder agent writes the core functions and a check for each acceptance criterion, "
                    "then runs them in a locked sandbox. Nothing is published.</p>"
                    f"<form method=post action='/runs/{run_id}/code' class='once'><button>"
                    f"{'Generate again' if c else 'Generate and test the core code'}</button></form></div>")
        if c and c.get("ok"):
            live = (settings.data_dir / "sites" / run_id / "mvp.json").exists()
            m = st.mvp_app
            body.append("<div class='card'><h2>MVP app (Phase 3)</h2>"
                        + (f"<p><b class='go'>Running:</b> <a href='/mvp/{run_id}' target='_blank'>open the MVP app</a>. "
                           f"Each request runs <code>{html.escape(m['func'])}</code> in the sandbox.</p>" if live and m else
                           "<p>Waiting for your approval above to publish it on this computer.</p>" if m else "")
                        + "<p>Turns the tested code into a small web app with one form. Publishing it needs your approval.</p>"
                        f"<form method=post action='/runs/{run_id}/mvp' class='once'><button>"
                        f"{'Rebuild the MVP app' if m else 'Build the MVP app'}</button></form></div>")
    body.append(f"""<div class="card"><h2>Ask the team</h2><form method="post" action="/runs/{run_id}/ask" class="once">
<textarea name="request" rows="2" placeholder="e.g. how should I find my first 10 interviewees?"></textarea><button>Ask</button></form></div>""")
    u = st.usage
    tech.append(f"<p><a href='/runs/{run_id}/export'>Download the full run report (Markdown)</a>: brief, gates, your "
                "decisions, approvals, decision log and outputs in one file.</p>")
    tech.append(f"<p class=mut>Model calls: {u.get('calls', 0)} · tokens: {u.get('prompt_tokens', 0) + u.get('completion_tokens', 0)} · cost: $0.00 ({'free tier, no billing' if settings.provider == 'openai' else 'local model'})</p>")
    body.append("<details class='card'><summary><b>Details</b> (files, approvals, report, cost)</summary>" + "".join(tech) + "</details>")
    return page(st.brief["idea"][:40], "".join(body), refresh=bool(busy))


@app.post("/runs/{run_id}/approvals/{item_id}")
def decide(run_id: str, item_id: str, approve: str = Form(...), note: str = Form("")):
    if run_id not in _busy:
        try:
            orch.approve(run_id, item_id, approve == "1", note or None)
        except (KeyError, ValueError):
            pass  # stale or already-decided item: the refreshed page shows the current state
    return RedirectResponse(f"/runs/{run_id}", status_code=303)


@app.post("/runs/{run_id}/gate")
def gate(run_id: str, decision: str = Form(...), note: str = Form("")):
    st, _ = orch.load(run_id)
    rec = st.gates[-1]["recommendation"] if st.gates else decision
    if decision != rec and not note.strip():
        return page("Reason needed", f"<div class=card><h2>Reason needed</h2><p>The system recommended "
                                 f"<b>{html.escape(rec)}</b> and you chose <b>{html.escape(decision)}</b>. You can overrule it, "
                                 "but write why: the reason is saved in the decision log and in the gate output, next to the "
                                 f"recommendation.</p><a href='/runs/{run_id}'>Back to the gate</a></div>")
    _bg(run_id, f"Applying decision '{decision}'", orch.founder_gate_decision, run_id, decision, note or None)
    return RedirectResponse(f"/runs/{run_id}", status_code=303)


@app.post("/runs/{run_id}/targets")
def targets(run_id: str, approve: str = Form(...)):
    _bg(run_id, "Updating targets", orch.founder_lock_targets, run_id, approve == "1")
    return RedirectResponse(f"/runs/{run_id}", status_code=303)


def _fork_html(g: dict, run_id: str) -> str:
    if g["recommendation"] not in ("pivot", "repeat", "stop"):
        return ""
    return (f"<details><summary>Try a narrower version in a new run (this run stays as it is)</summary>"
            f"<form method=post action='/runs/{run_id}/fork' class=once><label>Edited idea (leave empty to rerun the same brief "
            "with the sources already retrieved)</label><input name=idea><button>Fork a new run</button></form></details>")


def _sales_import_html(st, run_id: str) -> str:
    s = st.imported_sales
    got = (f"<p><b>Imported from {html.escape(s['source'])}:</b> {s['orders']} completed orders, {s['activations']} activations, "
           f"{s['not_completed']} not completed [FOUNDER-REPORTED METRIC]. Enter the orders above.</p>") if s else ""
    return (got + f"<details><summary>Import your own order or activation records (CSV)</summary>"
            f"<form method=post action='/runs/{run_id}/import-sales' enctype='multipart/form-data' class=once>"
            "<label>CSV with columns type (order or activation), status (paid, completed...), optional order_id. Only counts are read: "
            "no amounts, card data or logins.</label><input type=file name=file accept='.csv' required><button>Import</button></form></details>")


def _assumptions_html(st) -> str:
    from app.evidence import assumption_ids
    ids = assumption_ids(st.ledger or [])
    if not ids:
        return ""
    items = "".join(f"<li><b>{i}</b> {html.escape(t)}</li>" for i, t in ids[:5])
    more = f"<li class=mut>... and {len(ids) - 5} more (see the gate output)</li>" if len(ids) > 5 else ""
    return (f"<details><summary><b>{len(ids)} unproven assumption(s)</b> a GO would build on</summary><ul>{items}{more}</ul></details>")


def _verdict_html(st) -> str:
    """Phase 1 gate card: the co-founder's honest verdict and its suggestions."""
    v = getattr(st, "verdict", None)
    if not v:
        return ""
    cls = {"strong": "go", "promising": "repeat", "weak": "pivot", "do_not_pursue": "stop"}[v["verdict"]]
    ideas = "".join(f"<li><b>{html.escape(i['change'])}</b>: {html.escape(i['why'])} <i>Test: {html.escape(i['cheapest_test'])}</i></li>"
                    for i in v["improvements"])
    return (f"<div class=card><h3>Your co-founder's verdict: <span class='{cls}'>{v['verdict'].replace('_', ' ').upper()}</span></h3>"
            f"<p>{html.escape(v['one_line'])}</p>" + (f"<p class=mut>{html.escape(v['cap_note'])}</p>" if v.get("cap_note") else "")
            + f"<p><b>Most likely to kill it:</b> {html.escape(v['killer_risk'])}</p><p><b>How to make it stronger:</b></p><ul>{ideas}</ul>"
            + (f"<p><b>Best time:</b> {html.escape(v.get('best_window', ''))}: {html.escape(v.get('timing_why', ''))}"
               f" <i>Avoid: {html.escape(v.get('avoid_window') or 'none')}</i></p>" if v.get("best_window") else "")
            + f"<p class=mut>What would change my mind: {html.escape(v['change_my_mind'])}</p>" + _funding_html(st) + "</div>")


def _funding_html(st) -> str:
    f = getattr(st, "funding", None)
    if not f or not f.get("funders"):
        return ""
    rows = "".join(
        f"<tr><td>{html.escape(r['name'])}{'' if r['verified'] else ' <span class=tag>UNVERIFIED</span>'}</td>"
        f"<td>{r['kind'].replace('_', ' ')}</td><td><b>{str(r['fit']) + '%' if r['fit'] is not None else '?'}</b></td>"
        f"<td>{html.escape(r['history'])}</td><td>{html.escape('; '.join(r['criteria_missed']) or '-')}</td>"
        f"<td>{html.escape(r['contact']) if r['contact'] else 'their official site'}</td></tr>" for r in f["funders"])
    return ("<h3>Who could fund or sponsor this</h3><p class=mut>Fit = share of their criteria you meet today (not a chance of "
            "being funded). No banks or loans. A draft email is in phase1_step5_funding.</p>"
            "<table><tr><th>Funder</th><th>Type</th><th>Fit</th><th>History</th><th>Still missing</th><th>Apply</th></tr>"
            + rows + "</table>")


def _interviews_html(st, run_id: str) -> str:
    """Phase 2: analysed interviews and the form to add one (typed notes or a recording)."""
    rows = "".join(
        f"<li><b>Interview {n}</b> ({html.escape(i['source'])}): "
        + ("<span class='go'>problem confirmed</span>" if i["analysis"]["problem_confirmed"] else "<span class='stop'>not confirmed</span>")
        + f" &middot; {html.escape(i['analysis']['why'])}</li>" for n, i in enumerate(st.interviews, 1))
    audio = ("<label>...or upload the recording (any language; transcribed with an open-weight Whisper model on the free tier, "
             "not stored)</label><input type=file name=audio accept='audio/*'>") if transcribe.available(settings) else \
            "<p class=mut>Audio upload needs the free-tier endpoint (STUBBED with local Ollama): paste the transcript instead.</p>"
    return (f"<div class=card><h3>Customer interviews, analysed by your co-founder agent</h3>"
            + (f"<ol>{rows}</ol><p class=mut>Full analysis with verified quotes: phase2_step4_interviews.</p>" if rows else "")
            + f"<form method=post action='/runs/{run_id}/interview' enctype='multipart/form-data' class=once>"
            "<label>Paste the transcript or your notes of one interview (Arabic or English)</label>"
            "<textarea name=transcript rows=6></textarea>" + audio
            + "<label><input type=checkbox name=consent value=1 required> The interviewee agreed to take part and to be quoted anonymously</label>"
            "<button>Analyse this interview</button></form>"
            + (f"<p><b>Sign-ups imported from your own form:</b> {len(st.imported_waitlist['hashes'])} unique "
               "[FOUNDER-REPORTED METRIC]</p>" if st.imported_waitlist else "")
            + f"<details><summary>Collect sign-ups on your own hosting</summary><form method=get action='/runs/{run_id}/landing-export'>"
            "<label>Your form endpoint (mailto:you@example.com, or an https:// Google Form / Formspree URL you own)</label>"
            "<input name=action required><button>Download the landing page as one static file</button></form>"
            f"<form method=post action='/runs/{run_id}/import-waitlist' enctype='multipart/form-data' class=once>"
            "<label>Then import the sign-ups CSV your form collected (only email hashes are kept, duplicates dropped)</label>"
            "<input type=file name=file accept='.csv' required><button>Import sign-ups</button></form></details></div>")


@app.post("/runs/{run_id}/interview", response_class=HTMLResponse)
async def interview(run_id: str, transcript: str = Form(""), consent: str = Form(""), audio: UploadFile | None = File(None)):
    if consent != "1":
        raise HTTPException(400, "the interviewee's consent is required")
    source, text = "typed notes", transcript
    try:
        data = await audio.read() if audio is not None and audio.filename else b""
        if data and not text.strip():
            text = transcribe.transcribe(settings, data, audio.filename)
            source = "recording"
            orch.log.append(agent="transcriber", action="transcribe_recording", model=transcribe.model_name(), cost=0,
                            run_id=run_id, detail=f"{len(text.split())} words; the recording was not stored")
        orch.founder_add_interview(run_id, text, source)
    except (ValueError, transcribe.TranscriptionUnavailable) as e:
        return page("Interview not analysed", f"<div class=card><p>{html.escape(str(e))}</p><a href='/runs/{run_id}'>Back</a></div>")
    return RedirectResponse(f"/runs/{run_id}", status_code=303)


@app.post("/runs/{run_id}/import-waitlist", response_class=HTMLResponse)
async def import_waitlist(run_id: str, file: UploadFile = File(...)):
    try:
        orch.founder_import_waitlist(run_id, (await file.read()).decode("utf-8", "replace"), file.filename or "CSV")
    except ValueError as e:
        return page("Not imported", f"<div class=card><p>{html.escape(str(e))}</p><a href='/runs/{run_id}'>Back</a></div>")
    return RedirectResponse(f"/runs/{run_id}", status_code=303)


@app.post("/runs/{run_id}/import-sales", response_class=HTMLResponse)
async def import_sales(run_id: str, file: UploadFile = File(...)):
    try:
        orch.founder_import_sales(run_id, (await file.read()).decode("utf-8", "replace"), file.filename or "CSV")
    except ValueError as e:
        return page("Not imported", f"<div class=card><p>{html.escape(str(e))}</p><a href='/runs/{run_id}'>Back</a></div>")
    return RedirectResponse(f"/runs/{run_id}", status_code=303)


@app.get("/runs/{run_id}/landing-export")
def landing_export(run_id: str, action: str):
    from app.imports import export_landing
    st, _ = orch.load(run_id)
    src = settings.outputs_dir / f"phase2_step2_landing_page-{st.slug}.html"
    if not src.exists():
        raise HTTPException(404)
    try:
        out = export_landing(src.read_text(encoding="utf-8"), run_id, action)
    except ValueError as e:
        raise HTTPException(400, str(e))
    orch.log.append(agent="founder", action="export_landing_static", approved_by="founder", run_id=run_id, phase=2,
                    detail="static landing page downloaded by the founder; the founder hosts it, sign-ups go to their own endpoint")
    return HTMLResponse(out, headers={"Content-Disposition": f'attachment; filename="landing-{run_id}.html"'})


@app.post("/runs/{run_id}/fork")
def fork(run_id: str, idea: str = Form("")):
    st = orch.fork(run_id, idea or None)
    if st.stage == "p1_running":
        _bg(st.run_id, "Phase 1 agents working (forked run)", orch.advance, st.run_id)
    return RedirectResponse(f"/runs/{st.run_id}", status_code=303)


@app.get("/compare/{a}/{b}", response_class=HTMLResponse)
def compare(a: str, b: str):
    """Read-only side by side of two runs (for example a run and its fork)."""
    try:
        sa, sb = orch.load(a)[0], orch.load(b)[0]
    except Exception:
        raise HTTPException(404)

    def row(st):
        best = max((o.get("score", 0) for o in st.opportunities), default=0) if st.opportunities else 0
        v = st.verdict or {}
        quotes = sum(len(i["analysis"].get("evidence", [])) for i in st.interviews)
        u = st.usage or {}
        return [st.brief["idea"][:80], f"{best:.1f}" if best else "-", (st.area or {}).get("fit", "-").upper(),
                v.get("verdict", "-").replace("_", " ").upper(), v.get("killer_risk", "-"),
                " → ".join(f"P{g['phase']} {g['recommendation'].upper()}" for g in st.gates) or "-", str(quotes),
                str(u.get("prompt_tokens", 0) + u.get("completion_tokens", 0)), st.parent_run_id or "-"]
    labels = ["Idea", "Best opportunity score", "Local fit", "Co-founder verdict", "Killer risk", "Gates",
              "Verified interview quotes", "Tokens used", "Forked from"]
    ra, rb = row(sa), row(sb)
    body = "".join(f"<tr><th>{l}</th><td>{html.escape(x)}</td><td>{html.escape(y)}</td></tr>" for l, x, y in zip(labels, ra, rb))
    return page("Compare runs", f"<h1>Compare runs</h1><div class=card><table><tr><th></th><th><a href='/runs/{a}'>{a}</a></th>"
                f"<th><a href='/runs/{b}'>{b}</a></th></tr>{body}</table><p class=mut>Read-only.</p></div>")


@app.post("/runs/{run_id}/results")
def results(run_id: str, interviews_done: int = Form(...), pain_confirmed: int = Form(...)):
    try:
        orch.founder_record_results(run_id, interviews_done, pain_confirmed)
    except ValueError as e:
        if "not collecting" in str(e):
            return RedirectResponse(f"/runs/{run_id}", status_code=303)
        raise HTTPException(400, str(e))
    return RedirectResponse(f"/runs/{run_id}", status_code=303)


@app.post("/runs/{run_id}/build")
def build(run_id: str):
    def go():
        try:
            orch.founder_continue(run_id)
        except ValueError:
            pass  # not eligible; the page shows the current state
    _bg(run_id, "Running the next phase", go)
    return RedirectResponse(f"/runs/{run_id}", status_code=303)


@app.post("/runs/{run_id}/operate")
def operate(run_id: str, visits: str = Form(""), paid_orders: int = Form(0), feedback: str = Form("")):
    entered = int(visits) if visits.strip().isdigit() else None  # empty: use the app's own count

    def go():
        try:
            orch.founder_record_launch_results(run_id, entered, paid_orders, feedback.splitlines())
        except ValueError:
            pass
    _bg(run_id, "Comparing launch results with your targets", go)
    return RedirectResponse(f"/runs/{run_id}", status_code=303)


@app.post("/runs/{run_id}/code")
def generate_code(run_id: str):
    def go():
        try:
            orch.founder_generate_code(run_id)
        except ValueError:
            pass
    _bg(run_id, "Writing the core code and running its acceptance checks in the sandbox", go)
    return RedirectResponse(f"/runs/{run_id}", status_code=303)


@app.post("/runs/{run_id}/mvp")
def build_mvp(run_id: str):
    def go():
        try:
            orch.founder_build_mvp(run_id)
        except (ValueError, FileNotFoundError, PermissionError):
            pass
    _bg(run_id, "Re-running the acceptance checks and building the MVP app", go)
    return RedirectResponse(f"/runs/{run_id}", status_code=303)


def _count(request: Request, run_id: str, page_name: str) -> None:
    """Counts a view of a published page: page name and date only (no cookies, IPs or user agents)."""
    if not analytics.from_dashboard(request.headers.get("referer")):
        orch.analytics(run_id).hit(page_name)


def _mvp_bundle(run_id: str) -> dict:
    p = settings.data_dir / "sites" / Path(run_id).name / "mvp.json"
    if not p.exists():
        raise HTTPException(404, "Not published: the founder has not approved this MVP app.")
    return json.loads(p.read_text(encoding="utf-8"))


@app.get("/mvp/{run_id}", response_class=HTMLResponse)
def mvp_page(request: Request, run_id: str):
    b = _mvp_bundle(run_id)
    _count(request, run_id, "mvp_view")
    return HTMLResponse(b["page"])


@app.get("/mvp/{run_id}/guide", response_class=HTMLResponse)
def mvp_guide(run_id: str):
    b = _mvp_bundle(run_id)
    if not b.get("guide"):
        raise HTTPException(404, "This MVP app was published before user guides existed: rebuild it to get one.")
    return HTMLResponse(mvp_app.guide_html(b["guide"], "User guide"))


@app.post("/mvp/{run_id}", response_class=HTMLResponse)
def mvp_run(request: Request, run_id: str, text: str = Form(...)):
    b = _mvp_bundle(run_id)
    _count(request, run_id, "mvp_run")
    results = mvp_app.run_functions(b["code"], b.get("funcs") or [b["func"]], text, sandbox.call)
    return HTMLResponse(b["page"].replace(mvp_app.RESULT_MARK, mvp_app.result_html(results), 1))


@app.post("/runs/{run_id}/retry")
def retry(run_id: str):
    _bg(run_id, "Retrying", orch.advance, run_id)
    return RedirectResponse(f"/runs/{run_id}", status_code=303)


@app.post("/runs/{run_id}/ask", response_class=HTMLResponse)
def ask(run_id: str, request: str = Form(...)):
    st, _ = orch.load(run_id)
    v = guard.check_request(request)
    if not v.allowed:
        orch.log.append(agent="guard", action="refuse_request", run_id=run_id, outcome="refused", rule=v.rule)
        answer = f"Declined (rule: {v.rule}): {v.reason} Nothing was sent to a model. Happy to help with an honest alternative."
    else:
        ctxt = f"Idea: {st.brief['idea']}\nStage: {st.stage}\nGates: {[g['recommendation'] for g in st.gates]}"
        a = AdvisorAgent(orch.ctx(st)).answer(ctxt, request).answer
        a2, removed = guard.scrub_output(a)
        answer = a2 + ("\n\n(Some lines were removed by the safety guard.)" if removed else "")
    return page("Answer", f"<div class=card><h2>Your request</h2><p>{html.escape(request)}</p><h2>Answer</h2>"
                          f"<pre>{html.escape(answer)}</pre><a href='/runs/{run_id}'>Back to run</a></div>")


@app.get("/runs/{run_id}/export")
def export_run(run_id: str):
    """The founder's own copy of the run as one Markdown file. Built from saved state; no model call."""
    from app.report import build_run_report
    try:
        st, q = orch.load(run_id)
    except FileNotFoundError:
        raise HTTPException(404)
    md = build_run_report(st, q, orch.log.read(), settings.outputs_dir)
    return PlainTextResponse(md, media_type="text/markdown; charset=utf-8",
                             headers={"Content-Disposition": f"attachment; filename=founder-agents-{st.slug}-{run_id}.md"})


@app.get("/outputs/{name}", response_class=PlainTextResponse)
def output(name: str):
    p = (settings.outputs_dir / name).resolve()
    if p.parent != settings.outputs_dir.resolve() or not p.exists():
        raise HTTPException(404)
    return PlainTextResponse(p.read_text(encoding="utf-8"))


@app.get("/lp/{run_id}", response_class=HTMLResponse)
def landing(request: Request, run_id: str):
    p = settings.data_dir / "sites" / Path(run_id).name / "index.html"
    if not p.exists():
        raise HTTPException(404, "Not published: the founder has not approved this page.")
    _count(request, run_id, "landing")
    return HTMLResponse(p.read_text(encoding="utf-8"))


@app.get("/proto/{run_id}", response_class=HTMLResponse)
def prototype(run_id: str):
    p = settings.data_dir / "sites" / Path(run_id).name / "prototype.html"
    if not p.exists():
        raise HTTPException(404, "Not published: the founder has not approved this prototype.")
    return HTMLResponse(p.read_text(encoding="utf-8"))


@app.get("/store/{run_id}", response_class=HTMLResponse)
def store(request: Request, run_id: str):
    p = settings.data_dir / "sites" / Path(run_id).name / "store.html"
    if not p.exists():
        raise HTTPException(404, "Not published: the founder has not approved this store page.")
    _count(request, run_id, "store")
    return HTMLResponse(p.read_text(encoding="utf-8"))


@app.post("/lp/{run_id}/join", response_class=HTMLResponse)
def join(run_id: str, email: str = Form(...)):
    if "@" not in email or len(email) > 200:
        raise HTTPException(400)
    try:
        orch.add_signup(Path(run_id).name, email.strip().lower())
    except PermissionError:
        raise HTTPException(404)
    return HTMLResponse("<p style='font-family:system-ui;padding:40px'>Thanks, you're on the waitlist. "
                        "We'll only email you if this launches.</p>")


@app.get("/replay/{run_id}", response_class=HTMLResponse)
def replay_run(run_id: str):
    entries = orch.log.read()
    r = replay.runs(entries).get(run_id)
    if r is None:
        raise HTTPException(404, "No such run in decision_log.json.")
    return page(f"Replay {run_id}", replay.render_run(run_id, r, replay.run_outputs(r["slug"], settings.outputs_dir),
                                                       not validate(entries)))


@app.get("/api/decision-log/validate")
def validate_log():
    issues = validate(orch.log.read())
    return {"valid": not issues, "issues": issues, "entries": len(orch.log.read())}


@app.get("/healthz")
def healthz():
    return {"ok": True, "model": llm.model, "model_ready": llm.health()}
