"""AI co-founder support chat, available once a run has its final result (done, or ended by a gate).

- Scoped to one run: the context and the history are built and stored per run_id only.
- Grounded: the context is a compact summary of this run's brief, gates, evidence ledger and agent outputs
  (capped so it fits a local 8B model's window); the prompt makes the assistant label facts from the run,
  ASSUMPTIONS and suggestions, and forbids invented names, URLs, quotes and numbers.
- Safe: every message goes through the guard first (refusals show the rule and never reach a model), every answer
  through the output scrubber; the chat never changes gates, approvals or run state.
- History: data/support/<run_id>.json, UTF-8, written atomically, last 40 messages.
"""
from __future__ import annotations

import json
import os
import re
import tempfile
from pathlib import Path

from pydantic import BaseModel

from app import guard
from app.agents.base import Agent

FINAL = ("done", "stopped")
MAX_CONTEXT = 7000  # characters (~2k tokens): fits qwen3:8b and free-tier limits with room for history and answer
MAX_HISTORY = 40


def finished(st) -> bool:
    return st.stage in FINAL and bool(st.gates)


def _cut(s, n=240) -> str:
    s = re.sub(r"\s+", " ", str(s or "")).strip()
    return s if len(s) <= n else s[: n - 1] + "…"


def context(st) -> str:
    """Most decision-relevant facts first, so truncation drops detail, never the outcome."""
    b = st.brief
    out = [f"IDEA: {_cut(b['idea'], 300)}",
           f"FOUNDER: skills {', '.join(b.get('skills', []))}; budget ${b.get('budget_usd', 0):g}; {b.get('hours_per_week', 0):g} h/week; "
           f"market {b.get('target_market', '')}; location {b.get('location') or 'not given'}",
           "GATES: " + " | ".join(
               f"P{g['phase']} {g['gate']}: system {g['recommendation'].upper()}"
               + (f", founder {g['founder_decision'].upper()}" if g.get("founder_decision") else "")
               + (f" (reason: {_cut(g.get('founder_note'), 120)})" if g.get("founder_note") else "") for g in st.gates)]
    final = st.gates[-1]
    out.append(f"FINAL RESULT: {final['recommendation'].upper()} at {final['gate']}; why: {_cut('; '.join(final.get('reasons', [])), 400)}")
    v = getattr(st, "verdict", None)
    if v:
        out.append(f"CO-FOUNDER VERDICT: {v['verdict']}; killer risk: {_cut(v['killer_risk'])}; fixes: "
                   + "; ".join(_cut(i['change'], 100) for i in v.get('improvements', [])[:3])
                   + (f"; best window: {v['best_window']}" if v.get("best_window") else ""))
    if getattr(st, "area", None):
        out.append(f"AREA CHECK: fit {st.area.get('fit', '?')}; {_cut(st.area.get('positioning'), 200)}")
    if st.opportunities and st.chosen is not None:
        o = st.opportunities[st.chosen]
        out.append(f"CHOSEN OPPORTUNITY: {o['name']} (score {o.get('score', 0):.1f}); strongest alternative: "
                   f"{_cut(o.get('strongest_alternative'), 120)}")
    if st.ledger:
        n_s = sum(1 for c in st.ledger if c["status"] == "SOURCED")
        from app.evidence import assumption_ids
        ids = assumption_ids(st.ledger)
        out.append(f"EVIDENCE: {n_s} SOURCED claims, {len(ids)} ASSUMPTIONS; open assumptions: "
                   + "; ".join(f"{i} {_cut(t, 90)}" for i, t in ids[:5]))
    if st.canvas:
        out.append(f"LEAN CANVAS: value {_cut(st.canvas.get('unique_value_proposition'), 150)}; riskiest: "
                   + "; ".join(_cut(a, 90) for a in st.canvas.get("riskiest_assumptions", [])[:3]))
    quotes = [e["quote"] for i in getattr(st, "interviews", []) or [] for e in i["analysis"].get("evidence", [])]
    if quotes:
        out.append("VERIFIED INTERVIEW QUOTES: " + " | ".join(f'"{_cut(q, 120)}"' for q in quotes[:4]))
    if st.results:
        out.append(f"DEMAND TEST: {st.results}")
    if st.mvp:
        out.append(f"MVP: {st.mvp.get('product_name')}: {_cut(st.mvp.get('one_line'), 150)}; stories "
                   + "; ".join(f"{u['id']} {_cut(u['i_want'], 70)}" for u in st.mvp.get("user_stories", [])[:4]))
    if st.code:
        out.append(f"MVP CODE: {st.code.get('passed')}/{st.code.get('total')} acceptance checks passed; criteria needing "
                   "storage/UI/hosting are DEFERRED (STUBBED)")
    if getattr(st, "pricing", None):
        out.append(f"PRICING: {_cut(json.dumps(st.pricing, ensure_ascii=False), 300)}")
    if getattr(st, "operate", None):
        op = st.operate
        out.append(f"LAUNCH RESULTS: {op.get('visits')} visits, {op.get('signups')} sign-ups, {op.get('paid_orders')} paid orders "
                   "(checkout MOCKED)")
    if getattr(st, "funding", None):
        out.append("POSSIBLE FUNDERS (fit = criteria met, not a probability): "
                   + "; ".join(f"{r['name']} {r['fit']}%" + ("" if r["verified"] else " UNVERIFIED") for r in st.funding["funders"][:3]))
    text = "\n".join(out)
    return text if len(text) <= MAX_CONTEXT else text[:MAX_CONTEXT - 20] + "\n[context truncated]"


def chips(st) -> list[str]:
    final = st.gates[-1]
    dec = (final.get("founder_decision") or final["recommendation"]).upper()
    first = (f"Why did the run end with {dec}?" if dec == final["recommendation"].upper() else
             f"Why did the run end with {dec} when the system recommended {final['recommendation'].upper()}?")
    c = [first,
         "What should I do next, this week, with my budget and hours?"]
    if getattr(st, "verdict", None):
        c.append("How could I reduce the killer risk?")
    if st.code or st.mvp:
        c.append("What is still DEFERRED in the MVP and how would I build it?")
    else:
        c.append("Which assumptions are still unproven?")
    return c[:4]


class SupportReply(BaseModel):
    answer: str


class SupportAgent(Agent):
    role = "support_chat"

    def reply(self, run_context: str, history: list[dict], message: str) -> SupportReply:
        past = "\n".join(f"{m['role'].upper()}: {_cut(m['text'], 600)}" for m in history[-6:])
        user = (f"THIS RUN (the only facts you may state as facts)\n{run_context}\n\nCONVERSATION SO FAR\n{past or '(none)'}"
                f"\n\nFOUNDER MESSAGE\n{message}")
        return self.ask("support_chat_answer", user, SupportReply)


class History:
    def __init__(self, data_dir: Path):
        self.dir = Path(data_dir) / "support"

    def path(self, run_id: str) -> Path:
        if not re.fullmatch(r"[a-zA-Z0-9_-]{1,40}", run_id):
            raise ValueError("bad run id")
        return self.dir / f"{run_id}.json"

    def load(self, run_id: str) -> list[dict]:
        p = self.path(run_id)
        return json.loads(p.read_text(encoding="utf-8")) if p.exists() else []

    def save(self, run_id: str, messages: list[dict]) -> None:
        p = self.path(run_id)
        p.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=p.parent, suffix=".tmp")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(messages[-MAX_HISTORY:], f, ensure_ascii=False)
        os.replace(tmp, p)

    def clear(self, run_id: str) -> None:
        self.save(run_id, [])


def answer(orch, st, history: History, message: str) -> dict:
    """One turn. Guard first; the run state is only read."""
    msgs = history.load(st.run_id)
    message = (message or "").strip()[:2000]
    v = guard.check_request(message)
    if not v.allowed:
        orch.log.append(agent="guard", action="refuse_request", run_id=st.run_id, outcome="refused", rule=v.rule,
                        detail="support chat")
        reply = f"Declined (rule: {v.rule}): {v.reason} Nothing was sent to a model. I can help with an honest alternative."
    else:
        text = SupportAgent(orch.ctx(st)).reply(context(st), msgs, message).answer
        text, removed = guard.scrub_output(text)
        reply = text + ("\n\n(Some lines were removed by the safety guard.)" if removed else "")
    msgs += [{"role": "founder", "text": message}, {"role": "assistant", "text": reply, "refused": not v.allowed}]
    history.save(st.run_id, msgs)
    return {"reply": reply, "refused": not v.allowed, "rule": v.rule}
