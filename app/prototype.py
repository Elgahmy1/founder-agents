"""Renders the clickable prototype from the builder's MvpSpec.

The template is ours: no scripts, no external resources, no forms that submit
anywhere, no password or payment fields. Model text is escaped and each line
is run through the output guard; offending lines are dropped and reported.
Navigation between screens uses in-page anchors and CSS :target only.
"""
from __future__ import annotations

import html
import re

from app import guard
from app.agents.builder import MvpSpec

SENSITIVE_FIELD = re.compile(r"\b(password|passcode|pin|card|cvv|cvc|iban|bank|account number|ssn|national id)\b", re.I)


def _safe(text: str, removed: list[str]) -> str:
    v = guard.check_output(text)
    if not v.allowed:
        removed.append(v.rule or "unknown")
        return ""
    return html.escape(text)


def render_prototype(spec: MvpSpec) -> tuple[str, list[str]]:
    removed: list[str] = []
    nav = "".join(f"<a href='#s{i}'>{i + 1}. {html.escape(s.title)}</a>" for i, s in enumerate(spec.screens))
    screens = []
    for i, s in enumerate(spec.screens):
        fields = []
        for label in s.inputs:
            if SENSITIVE_FIELD.search(label):
                removed.append("sensitive_field")
                continue
            lab = _safe(label, removed)
            if lab:
                fields.append(f"<label>{lab}<input disabled placeholder='{lab}'></label>")
        nxt = f"#s{i + 1}" if i + 1 < len(spec.screens) else "#s0"
        screens.append(
            f"<section id='s{i}'><h2>{i + 1}. {_safe(s.title, removed)}</h2><p class='mut'>{_safe(s.purpose, removed)}</p>"
            f"{''.join(fields)}<a class='btn' href='#r{i}'>{_safe(s.action, removed) or 'Continue'}</a>"
            f"<div id='r{i}' class='res'><b>SAMPLE output (illustrative, not real data)</b><p>{_safe(s.sample_output, removed)}</p>"
            f"<a href='{nxt}'>Next screen</a></div></section>")
    page = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(spec.product_name)}: prototype</title>
<style>
body{{font-family:system-ui,sans-serif;max-width:720px;margin:0 auto;padding:16px;color:#1d1d1f;background:#fafafa}}
.banner{{background:#fff4e0;border:1px solid #e0a650;border-radius:8px;padding:8px 12px;font-size:.9rem}}
nav{{display:flex;flex-wrap:wrap;gap:8px;margin:12px 0}} nav a{{font-size:.9rem}}
section{{background:#fff;border:1px solid #e2e2e8;border-radius:10px;padding:16px;margin:12px 0}}
label{{display:block;margin:8px 0;font-weight:600;font-size:.9rem}} input{{display:block;width:100%;box-sizing:border-box;padding:8px;margin-top:4px;border:1px solid #bbb;border-radius:6px}}
.btn{{display:inline-block;margin-top:10px;padding:8px 14px;border-radius:6px;background:#3b3bd6;color:#fff;text-decoration:none;font-weight:600}}
.res{{display:none;margin-top:12px;border-top:1px dashed #bbb;padding-top:8px}} .res:target{{display:block}} .mut{{color:#666}}
</style></head><body>
<p class="banner">Clickable prototype for founder review. Nothing here is live: no data is saved and nothing is sent.</p>
<h1>{_safe(spec.product_name, removed) or 'Prototype'}</h1><p>{_safe(spec.one_line, removed)}</p>
<nav>{nav}</nav>
{''.join(screens)}
</body></html>
"""
    return page, removed


def prototype_is_safe(page: str) -> list[str]:
    """Structural checks on the rendered page (used by the build gate)."""
    problems = []
    if re.search(r"<script|javascript:|\son[a-z]+\s*=", page, re.I):
        problems.append("script or inline handler")
    if re.search(r"<form|type=['\"]?password", page, re.I):
        problems.append("form or password field")
    if re.search(r"(src|href)\s*=\s*['\"]?https?://", page, re.I):
        problems.append("external resource or link")
    return problems
