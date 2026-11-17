"""Renders the store page from the launcher's copy and the founder-approved pricing.

Our template: no scripts, external resources or payment fields. Prices come
from Phase 4 data, not the model. The paid plan button is disabled because
checkout is MOCKED; the free plan links to the waitlist form already approved
in Phase 2. Every model line passes the output guard.
"""
from __future__ import annotations

import html
import re

from app import guard
from app.agents.launcher import LaunchKit
from app.agents.pricer import PricingPlan


def _safe(text: str, removed: list[str]) -> str:
    v = guard.check_output(text)
    if not v.allowed:
        removed.append(v.rule or "unknown")
        return ""
    return html.escape(text)


PLAN_TALK = re.compile(r"\b(free (tier|plan|version)|pro\b|premium|tiers?|plans?|quota|limit\w*|per month|/ ?month|priority|unlimited|upgrade|price\w*|pricing|\$\d)", re.I)


def render_store(product: str, kit: LaunchKit, pricing: PricingPlan, run_id: str) -> tuple[str, list[str]]:
    removed: list[str] = []
    gets = "".join(f"<li>{x}</li>" for x in (_safe(g, removed) for g in kit.what_you_get) if x)
    tiers = []
    for t in pricing.tiers:
        price = "Free" if t.price_usd_per_month == 0 else f"{t.price_usd_per_month:g} USD / month"
        inc = "".join(f"<li>{html.escape(i)}</li>" for i in t.includes)
        btn = (f"<a class='btn' href='/lp/{run_id}'>Start free</a>" if t.price_usd_per_month == 0 else
               "<span class='btn off'>Not on sale yet: payments are MOCKED in this prototype</span>")
        tiers.append(f"<div class='tier'><h3>{html.escape(t.name)}</h3><p class='price'>{price}</p><ul>{inc}</ul>{btn}</div>")
    faq_items = []
    for f in kit.faq:
        if PLAN_TALK.search(f"{f.question} {f.answer}"):
            removed.append("faq_described_plans")  # plans come only from the approved pricing below
            continue
        q, a = _safe(f.question, removed), _safe(f.answer, removed)
        if q and a:
            faq_items.append(f"<dt>{q}</dt><dd>{a}</dd>")
    plans = "; ".join(f"{html.escape(t.name)}: {'free' if t.price_usd_per_month == 0 else f'{t.price_usd_per_month:g} USD / month'}"
                      f" ({html.escape(', '.join(t.includes))})" for t in pricing.tiers)
    faq_items.insert(0, f"<dt>What does each plan include?</dt><dd>{plans}. These are the plans the founder approved.</dd>")
    faq = "".join(faq_items)
    page = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(product)}</title>
<style>
body{{font-family:system-ui,sans-serif;max-width:860px;margin:0 auto;padding:16px;color:#1d1d1f;background:#fafafa}}
h1{{font-size:2rem;line-height:1.2}} .sub{{font-size:1.1rem;color:#444}}
.tiers{{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:12px;margin:20px 0}}
.tier{{background:#fff;border:1px solid #e2e2e8;border-radius:10px;padding:16px}} .price{{font-size:1.3rem;font-weight:700}}
.btn{{display:inline-block;margin-top:8px;padding:8px 14px;border-radius:6px;background:#3b3bd6;color:#fff;text-decoration:none;font-weight:600}}
.btn.off{{background:#bbb;color:#333;font-weight:500;font-size:.85rem}} dt{{font-weight:700;margin-top:10px}} dd{{margin:4px 0 0 0;color:#444}}
.note{{font-size:.85rem;color:#666;border-top:1px solid #ddd;padding-top:12px;margin-top:24px}}
</style></head><body>
<h1>{_safe(kit.headline, removed) or html.escape(product)}</h1>
<p class="sub">{_safe(kit.subheadline, removed)}</p>
<ul>{gets}</ul>
<div class="tiers">{''.join(tiers)}</div>
<h2>Questions</h2><dl>{faq}</dl>
<p class="note">New product, early version. The core is free. Terms, privacy and refund policies are drafts signed off by the founder.
No payment is taken on this page.</p>
</body></html>
"""
    return page, removed
