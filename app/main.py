"""Web UI (FastAPI, server-rendered). Every outward action goes through the
founder's approve/reject buttons, which call ApprovalQueue.decide()."""
from __future__ import annotations

import html
import threading
from pathlib import Path

from fastapi import FastAPI, Form, HTTPException
from fastapi.responses import HTMLResponse, PlainTextResponse, RedirectResponse

from app import guard
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
    ("Phase 3 Build", "STUBBED"),
    ("Phase 4 Commercial setup", "STUBBED"),
    ("Phase 5 Launch, payments and delivery", "MOCKED / STUBBED"),
    ("Phase 6 Operate and learn", "STUBBED"),
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
"""


def page(title: str, body: str, refresh: bool = False) -> HTMLResponse:
    meta = '<meta http-equiv="refresh" content="4">' if refresh else ""
    return HTMLResponse(f"""<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">{meta}<title>{html.escape(title)}</title>
<style>{CSS}</style></head><body><p><a href="/">Founder Agents</a> · model <code>{html.escape(llm.model)}</code>
{'' if llm.health() else '<span class="tag stop">model not reachable: check Ollama</span>'}</p>{body}</body></html>""")


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
<label>Values (comma separated)</label><input name="values">
<label>Sources you already have (one URL per line, optional)</label><textarea name="source_urls" rows="2"></textarea>
<button>Start Discover</button></form></div>
<div class="card"><h2>Runs</h2><table>{rows or '<tr><td class=mut>No runs yet</td></tr>'}</table></div>
<div class="card"><h2>What works and what is mocked</h2><table>{status}</table></div>""")


def _split(s: str) -> list[str]:
    return [x.strip() for x in s.replace("\n", ",").split(",") if x.strip()]


@app.post("/runs")
def create_run(founder_name: str = Form("Founder"), idea: str = Form(...), skills: str = Form(""),
               budget_usd: float = Form(0), hours_per_week: float = Form(10), target_market: str = Form(...),
               values: str = Form(""), source_urls: str = Form("")):
    brief = FounderBrief(founder_name=founder_name, idea=idea, skills=_split(skills), budget_usd=budget_usd,
                         hours_per_week=hours_per_week, target_market=target_market, values=_split(values),
                         source_urls=[u for u in _split(source_urls) if u.startswith("http")])
    st = orch.create(brief)
    if st.stage == "p1_running":
        _bg(st.run_id, "Phase 1 agents working", orch.advance, st.run_id)
    return RedirectResponse(f"/runs/{st.run_id}", status_code=303)


def _gate_panel(st: RunState) -> str:
    if not st.gates:
        return ""
    g = st.gates[-1]
    rows = "".join(f"<tr><td>{html.escape(c['name'])}</td><td>{html.escape(c['target'])}</td><td>{html.escape(c['actual'])}</td>"
                   f"<td>{'PASS' if c['passed'] else 'FAIL'}</td></tr>" for c in g["checks"])
    reasons = "".join(f"<li>{html.escape(r)}</li>" for r in g["reasons"])
    decide = ""
    if st.stage in ("p1_gate_wait", "p2_gate_wait"):
        decide = f"""<form method="post" action="/runs/{st.run_id}/gate"><label>Your decision</label>
<select name="decision">{''.join(f'<option value="{o}" {"selected" if o == g["recommendation"] else ""}>{o}</option>' for o in ("go", "repeat", "pivot", "stop"))}</select>
<label>Note (optional)</label><input name="note"><button>Record decision</button></form>"""
    fd = f"<p>Founder decision: <b class='{g.get('founder_decision')}'>{g.get('founder_decision')}</b></p>" if g.get("founder_decision") else ""
    return f"""<div class="card"><h2>Phase {g['phase']} gate: {g['gate']}</h2>
<p>System recommendation: <b class="{g['recommendation']}">{g['recommendation'].upper()}</b> <span class=mut>(thresholds set in advance)</span></p>
<table><tr><th>Check</th><th>Target</th><th>Actual</th><th></th></tr>{rows}</table><ul>{reasons}</ul>{fd}{decide}</div>"""


@app.get("/runs/{run_id}", response_class=HTMLResponse)
def view_run(run_id: str):
    try:
        st, q = orch.load(run_id)
    except FileNotFoundError:
        raise HTTPException(404)
    busy = _busy.get(run_id)
    body = [f"<h1>{html.escape(st.brief['idea'][:120])}</h1><p>Stage: <b>{st.stage}</b>"
            + (f" · <span class='tag repeat'>{html.escape(busy)}… (auto-refreshing)</span>" if busy else "") + "</p>"]
    if st.error and not busy:
        body.append(f"<div class='card'><b class=stop>Error:</b> {html.escape(st.error)}"
                    f"<form method=post action='/runs/{run_id}/retry'><button>Retry step</button></form></div>")
    pend = q.pending()
    if pend and not busy:
        items = "".join(f"""<div class="card"><b>{i.kind.upper()}</b>: {html.escape(i.title)}
<pre>{html.escape(i.content[:3000])}</pre><form method="post" action="/runs/{run_id}/approvals/{i.id}">
<input name="note" placeholder="Note (optional)"><button name="approve" value="1">Approve</button>
<button class="rej" name="approve" value="0">Reject</button></form></div>""" for i in pend)
        body.append(f"<div class='card'><h2>Waiting for your approval ({len(pend)})</h2>{items}</div>")
    done = [i for i in q.items if i.status != "pending"]
    if done:
        body.append("<div class='card'><h2>Approval history</h2><table>" + "".join(
            f"<tr><td>{i.kind}</td><td>{html.escape(i.title)}</td><td>{i.status}</td><td>{html.escape(i.result or '')}</td></tr>"
            for i in done) + "</table></div>")
    body.append(_gate_panel(st) if not busy else "")
    if st.stage == "p2_targets_wait" and st.demand_plan and not busy:
        p = st.demand_plan
        body.append(f"""<div class="card"><h2>Lock demand-test targets before the test</h2>
<p>{p['waitlist_signups_target']} waitlist sign-ups in {p['window_days']} days · {p['interviews_target']} interviews ·
{p['pain_confirm_rate_target']:.0%} confirm the problem</p><p class=mut>{html.escape(p['rationale'])}</p>
<form method="post" action="/runs/{run_id}/targets"><button name="approve" value="1">Lock these targets</button>
<button class="rej" name="approve" value="0">Reject and re-plan</button></form></div>""")
    if st.stage == "p2_collecting" and not busy:
        body.append(f"""<div class="card"><h2>Record real results</h2>
<p>Waitlist sign-ups counted by the app: <b>{orch.signups(run_id)}</b> (from <a href="/lp/{run_id}">the landing page</a>)</p>
<form method="post" action="/runs/{run_id}/results"><label>Interviews completed</label><input type="number" name="interviews_done" min="0" required>
<label>Interviewees who confirmed the problem</label><input type="number" name="pain_confirmed" min="0" required>
<button>Run demand gate</button></form></div>""")
    if st.outputs:
        body.append("<div class='card'><h2>Outputs</h2><ul>" + "".join(
            f"<li><a href='/outputs/{o}'>{o}</a>{' ' + tag('STUBBED') if 'STUBBED' in o else ''}</li>" for o in st.outputs) + "</ul></div>")
    if st.ledger:
        n_s = sum(1 for c in st.ledger if c["status"] == "SOURCED")
        body.append(f"<div class='card'><h2>Evidence ledger</h2><p>{n_s} sourced · {len(st.ledger) - n_s} ASSUMPTION</p></div>")
    body.append(f"""<div class="card"><h2>Ask the team</h2><form method="post" action="/runs/{run_id}/ask">
<textarea name="request" rows="2" placeholder="e.g. how should I find my first 10 interviewees?"></textarea><button>Ask</button></form></div>""")
    u = st.usage
    body.append(f"<p class=mut>Model calls: {u.get('calls', 0)} · tokens: {u.get('prompt_tokens', 0) + u.get('completion_tokens', 0)} · cost: $0.00 ({'free tier, no billing' if settings.provider == 'openai' else 'local model'})</p>")
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
    _bg(run_id, f"Applying decision '{decision}'", orch.founder_gate_decision, run_id, decision, note or None)
    return RedirectResponse(f"/runs/{run_id}", status_code=303)


@app.post("/runs/{run_id}/targets")
def targets(run_id: str, approve: str = Form(...)):
    _bg(run_id, "Updating targets", orch.founder_lock_targets, run_id, approve == "1")
    return RedirectResponse(f"/runs/{run_id}", status_code=303)


@app.post("/runs/{run_id}/results")
def results(run_id: str, interviews_done: int = Form(...), pain_confirmed: int = Form(...)):
    try:
        orch.founder_record_results(run_id, interviews_done, pain_confirmed)
    except ValueError as e:
        if "not collecting" in str(e):
            return RedirectResponse(f"/runs/{run_id}", status_code=303)
        raise HTTPException(400, str(e))
    return RedirectResponse(f"/runs/{run_id}", status_code=303)


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
        answer = f"Declined: {v.reason} Happy to help with an honest alternative."
    else:
        ctxt = f"Idea: {st.brief['idea']}\nStage: {st.stage}\nGates: {[g['recommendation'] for g in st.gates]}"
        a = AdvisorAgent(orch.ctx(st)).answer(ctxt, request).answer
        a2, removed = guard.scrub_output(a)
        answer = a2 + ("\n\n(Some lines were removed by the safety guard.)" if removed else "")
    return page("Answer", f"<div class=card><h2>Your request</h2><p>{html.escape(request)}</p><h2>Answer</h2>"
                          f"<pre>{html.escape(answer)}</pre><a href='/runs/{run_id}'>Back to run</a></div>")


@app.get("/outputs/{name}", response_class=PlainTextResponse)
def output(name: str):
    p = (settings.outputs_dir / name).resolve()
    if p.parent != settings.outputs_dir.resolve() or not p.exists():
        raise HTTPException(404)
    return PlainTextResponse(p.read_text(encoding="utf-8"))


@app.get("/lp/{run_id}", response_class=HTMLResponse)
def landing(run_id: str):
    p = settings.data_dir / "sites" / Path(run_id).name / "index.html"
    if not p.exists():
        raise HTTPException(404, "Not published: the founder has not approved this page.")
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


@app.get("/api/decision-log/validate")
def validate_log():
    issues = validate(orch.log.read())
    return {"valid": not issues, "issues": issues, "entries": len(orch.log.read())}


@app.get("/healthz")
def healthz():
    return {"ok": True, "model": llm.model, "model_ready": llm.health()}
