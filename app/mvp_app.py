"""Phase 3, step 5: the MVP app.

Wraps the core code that passed its acceptance checks (phase3_step4_code) in a
small working web app: our own template (no scripts, no external resources, no
password or payment fields) with one form. Each submission runs the generated
function in the sandbox (`sandbox.call`) and shows the result. No model call.
Storage, accounts and public hosting are not part of the MVP app.
"""
from __future__ import annotations

import ast
import html
import json
import re

from app import guard

RESULT_MARK = "<!--RESULT-->"


def parse_code_output(md: str) -> tuple[str, list[str], bool]:
    """(module code, checks, all checks passed) from a phase3_step4_code output file."""
    if "## core.py" not in md or "## Checks" not in md:
        raise ValueError("not a phase3_step4_code output")
    core, checks_md = md.split("## core.py", 1)[1].split("## Checks", 1)
    m = re.search(r"```python\n(.*?)```", core, re.S)
    if not m:
        raise ValueError("no code block")
    r = re.search(r"\*\*Result: (\d+)/(\d+) acceptance checks passed", md)
    ok = bool(r) and r.group(1) == r.group(2) and int(r.group(2)) > 0
    return m.group(1), re.findall(r"```python\n(.*?)```", checks_md, re.S), ok


def entry_function(code: str) -> tuple[str, list[str]] | None:
    """The first public top-level function callable with one text argument: (name, parameter names)."""
    found = entry_functions(code)
    return found[0] if found else None


def entry_functions(code: str, limit: int = 6) -> list[tuple[str, list[str]]]:
    """Every public top-level function callable with one text argument, in file order (at most `limit`)."""
    out: list[tuple[str, list[str]]] = []
    for node in ast.parse(code).body:
        if not isinstance(node, ast.FunctionDef) or node.name.startswith("_"):
            continue
        a = node.args
        params = [p.arg for p in a.posonlyargs + a.args]
        required = len(params) - len(a.defaults)
        kw_required = [p.arg for p, d in zip(a.kwonlyargs, a.kw_defaults) if d is None]
        if params and required <= 1 and not kw_required:
            out.append((node.name, params))
    return out[:limit]


def _esc(text: str, removed: list[str]) -> str:
    v = guard.check_output(text)
    if not v.allowed:
        removed.append(v.rule or "unknown")
        return ""
    return html.escape(text)


def render_mvp_page(*, run_id: str, product_name: str, one_line: str, story: dict,
                    funcs: list[tuple[str, list[str]]], checks_passed: str) -> tuple[str, list[str]]:
    removed: list[str] = []
    name = _esc(product_name, removed) or "MVP"
    tagline = _esc(one_line, removed)
    want = _esc(f"As {story.get('as_a', '')}, I want {story.get('i_want', '')}, so that {story.get('so_that', '')}.", removed)
    page = f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{name}</title><style>
:root{{--bg:#f7f7f9;--fg:#1d1d1f;--mut:#666;--card:#fff;--line:#e2e2e8;--acc:#3b3bd6}}
@media (prefers-color-scheme: dark){{:root{{--bg:#141418;--fg:#ececf1;--mut:#a0a0aa;--card:#1d1d23;--line:#2e2e36;--acc:#8f8fff}}}}
body{{font-family:system-ui,sans-serif;background:var(--bg);color:var(--fg);max-width:760px;margin:0 auto;padding:16px}}
.card{{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:16px;margin:14px 0}}
textarea{{width:100%;box-sizing:border-box;padding:8px;border:1px solid var(--line);border-radius:6px;background:var(--bg);color:var(--fg);font:inherit}}
button{{padding:8px 14px;border:0;border-radius:6px;background:var(--acc);color:#fff;font-weight:600;cursor:pointer;margin-top:8px}}
pre{{white-space:pre-wrap;word-wrap:break-word}} .mut{{color:var(--mut);font-size:.9em}}
</style></head><body>
<h1>{name}</h1><p class="mut">Product vision: {tagline}</p>
<div class="card"><p><b>What this MVP does today:</b> paste text, press Run, and it shows the result of
{" and ".join(f"<code>{html.escape(f)}</code>" for f, _ in funcs)} on your text.</p><p class="mut">{want}</p>
<form method="post" action="/mvp/{html.escape(run_id)}">
<label for="text">Paste your text</label>
<textarea id="text" name="text" rows="10" maxlength="20000" required></textarea>
<button>Run</button></form></div>
{RESULT_MARK}
<p class="mut">MVP built by Founder Agents from code that passed {html.escape(checks_passed)} acceptance checks.
Each request runs {", ".join(f"<code>{html.escape(f)}({html.escape(p[0])})</code>" for f, p in funcs)} in an isolated sandbox with no file, network or process access.
Nothing you paste is stored. Accounts, storage and public hosting are not part of this MVP.</p>
</body></html>
"""
    return page, removed


def run_functions(code: str, names: list[str], text: str, call) -> list[tuple[str, dict]]:
    """Runs the published functions in order. The first gets the founder's text. A later function whose input
    has a different name than the first one's (for example `summary` after `text`) gets the previous function's
    text result, so a step that works on a summary receives the summary, not the raw input."""
    params = {name: p for name, p in entry_functions(code)}
    first = params.get(names[0], [""])[0] if names else ""
    results: list[tuple[str, dict]] = []
    prev: str | None = None
    for name in names:
        own = params.get(name, [""])[0]
        arg = prev if (results and prev is not None and own != first) else text
        res = call(code, name, arg)
        results.append((name, res))
        if res.get("ok") and isinstance(res.get("result"), str):
            prev = res["result"]
    return results


def result_html(results: list[tuple[str, dict]]) -> str:
    parts = []
    for func, res in results:
        if not res.get("ok"):
            body = f"<b>Error:</b> {html.escape(str(res.get('error')))}"
        else:
            out = res.get("result")
            if isinstance(out, list) and all(isinstance(x, str) for x in out):
                text = "\n".join(f"- {x}" for x in out)
            else:
                text = out if isinstance(out, str) else json.dumps(out, indent=1, ensure_ascii=False, default=str)
            body = f"<pre>{html.escape(text)}</pre>"
        parts.append(f"<h3><code>{html.escape(func)}</code></h3>{body}")
    return "<div class='card'><h2>Result</h2>" + "".join(parts) + "</div>"
