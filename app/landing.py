"""Renders the waitlist landing page from model-written copy.

The template is ours, so the page has no scripts, timers, testimonials,
traction numbers or payment fields. Each line of model copy is also run
through the output guard, and offending lines are dropped and logged.
"""
from __future__ import annotations

import html

from app import guard
from app.agents.marketer import LandingCopy


def _safe(text: str, removed: list[str]) -> str:
    v = guard.check_output(text)
    if not v.allowed:
        removed.append(v.rule or "unknown")
        return ""
    return html.escape(text)


def render_landing(product: str, c: LandingCopy, run_id: str) -> tuple[str, list[str]]:
    removed: list[str] = []
    bullets = [b for b in (_safe(x, removed) for x in c.bullets) if b]
    cta = _safe(c.call_to_action, removed) or "Join the waitlist"
    page = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(product)}</title>
<style>
body{{font-family:system-ui,sans-serif;max-width:640px;margin:40px auto;padding:0 16px;color:#1d1d1f;background:#fafafa}}
h1{{font-size:2rem;line-height:1.2}} .sub{{font-size:1.15rem;color:#444}} li{{margin:.4rem 0}}
form{{display:flex;gap:8px;margin:24px 0}} input{{flex:1;padding:10px;border:1px solid #bbb;border-radius:6px}}
button{{padding:10px 16px;border:0;border-radius:6px;background:#3b3bd6;color:#fff;font-weight:600}}
.note{{font-size:.85rem;color:#666;border-top:1px solid #ddd;padding-top:12px}}
</style></head><body>
<h1>{_safe(c.headline, removed) or html.escape(product)}</h1>
<p class="sub">{_safe(c.subheadline, removed)}</p>
<ul>{''.join(f'<li>{b}</li>' for b in bullets)}</ul>
<form method="post" action="/lp/{run_id}/join">
<input type="email" name="email" required placeholder="you@example.com" aria-label="Email">
<button type="submit">{cta}</button></form>
<p class="note">{_safe(c.honesty_note, removed) or 'This is an early-stage product being tested.'}
We only use your email to tell you if this product launches. No payment is taken.</p>
</body></html>
"""
    return page, removed
