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
<p><a href="/mvp/{html.escape(run_id)}/guide">User guide</a>: what this MVP does today, how to use it, and what it does not do yet.</p>
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


def function_docs(code: str) -> dict[str, str]:
    """First sentence of each public top-level function's docstring (written by the coder agent)."""
    out: dict[str, str] = {}
    for node in ast.parse(code).body:
        if isinstance(node, ast.FunctionDef) and not node.name.startswith("_"):
            doc = " ".join((ast.get_docstring(node) or "").split())
            out[node.name] = re.split(r"(?<=[.!?])\s", doc, maxsplit=1)[0] if doc else ""
    return out


def criteria_rows(md: str) -> list[tuple[str, str, str]]:
    """(story, acceptance criterion, result) rows of the table in a phase3_step4_code output."""
    rows = []
    for line in md.splitlines():
        m = re.match(r"^\| (US\d+) \| (.+?) \| (check \d+|-) \| (.+?) \|$", line.strip())
        if m:
            rows.append((m.group(1), m.group(2), m.group(4)))
    return rows


def _show(res: dict) -> str:
    if not res.get("ok"):
        return f"(error: {res.get('error')})"
    out = res.get("result")
    if isinstance(out, list):
        return "\n".join(f"  - {x}" for x in out)
    return "\n".join(f"  {line}" for line in str(out).splitlines())


def render_user_guide(*, run_id: str, product_name: str, one_line: str, stories: list[dict], out_of_scope: list[str],
                      funcs: list[tuple[str, list[str]]], docs: dict[str, str], rows: list[tuple[str, str, str]],
                      checks_passed: str, sample: str, example: list[tuple[str, dict]]) -> str:
    """Phase 3 user docs for the MVP app, built in code from the run's own artifacts (MVP spec, tested code,
    acceptance results and a real sandbox run); no model call, so it cannot describe features the MVP lacks."""
    passed = [r for r in rows if r[2] == "PASS"]
    deferred = [r for r in rows if r[2].startswith("DEFERRED")]
    chained = [f for f, p in funcs[1:] if p and funcs and p[0] != funcs[0][1][0]]
    lines = [f"# {product_name}: user guide (MVP)", "",
             f"Written by the pipeline when the MVP app was built (run `{run_id}`), from the MVP spec, the tested core code "
             f"({checks_passed} acceptance checks passed) and a real run of that code in the sandbox. No model wrote this guide.", "",
             "## What it does today", ""]
    for f, p in funcs:
        lines.append(f"- **{f}** (input: `{p[0]}`): {docs.get(f) or 'no description in the code.'}")
    lines += ["", f"Product vision (not built yet): {one_line}", "", "## How to use it", "",
              f"1. Open the MVP app at `/mvp/{run_id}` (on this computer; public hosting is MOCKED).",
              "2. Paste your text into the box (up to 20,000 characters).",
              "3. Press **Run**. The result shows one section per step, in this order: "
              + ", ".join(f"`{f}`" for f, _ in funcs) + "."]
    if chained:
        lines.append(f"4. {', '.join(f'`{f}`' for f in chained)} works on the result of the step before it, not on your raw text.")
    lines += ["", "## Example (real output of this MVP)", "",
              "Input: the product's own description and user stories, used as sample text.", "", "```text", sample, "```", ""]
    for f, res in example:
        lines += [f"`{f}`:", "", "```text", _show(res).rstrip(), "```", ""]
    lines += ["## What was tested", "", "| Story | Acceptance criterion | Result |", "|---|---|---|"]
    lines += [f"| {s} | {c} | {r} |" for s, c, r in rows]
    lines += ["", "## What it does not do yet", ""]
    lines += [f"- {c} ({s}): not built yet, so it is listed as DEFERRED, not claimed." for s, c, _ in deferred]
    lines += [f"- Out of scope for this MVP: {x}" for x in out_of_scope]
    lines += ["- Uploading files (PDF, slides), accounts, saving results and public hosting are STUBBED: paste plain text instead.",
              "- The steps are plain, deterministic code, not an AI model: results can be simple, and they are not checked for accuracy.", "",
              "## Your data", "",
              "Nothing you paste is stored. Each request runs the code in an isolated sandbox with no file, network or process access, "
              "and the page has no accounts, cookies, password or payment fields.", "",
              "## Who it is for", ""]
    lines += [f"- {s.get('id', '')}: as {s.get('as_a', '')}, I want {s.get('i_want', '')}, so that {s.get('so_that', '')}." for s in stories]
    lines += ["", f"Tested stories: {len({r[0] for r in passed})} of {len(stories)}; "
              f"acceptance criteria checked: {len(passed)}, deferred: {len(deferred)}.", ""]
    return "\n".join(lines)


def guide_html(md: str, title: str) -> str:
    """Small Markdown-to-HTML for the user guide (headings, lists, tables, code blocks); everything is escaped."""
    out, in_code, in_list, in_table = [], False, False, False
    def close():
        nonlocal in_list, in_table
        if in_list:
            out.append("</ul>"); in_list = False
        if in_table:
            out.append("</table>"); in_table = False
    def inline(t: str) -> str:
        t = html.escape(t)
        t = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", t)
        return re.sub(r"`(.+?)`", r"<code>\1</code>", t)
    for line in md.splitlines():
        if line.startswith("```"):
            close()
            out.append("</pre>" if in_code else "<pre>"); in_code = not in_code
            continue
        if in_code:
            out.append(html.escape(line)); continue
        if line.startswith("|"):
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if set("".join(cells)) <= set("-: "):
                continue
            if not in_table:
                close(); out.append("<table>"); in_table = True
                out.append("<tr>" + "".join(f"<th>{inline(c)}</th>" for c in cells) + "</tr>"); continue
            out.append("<tr>" + "".join(f"<td>{inline(c)}</td>" for c in cells) + "</tr>"); continue
        if line.startswith("- ") or re.match(r"^\d+\. ", line):
            if in_table:
                close()
            if not in_list:
                out.append("<ul>"); in_list = True
            item = re.sub(r"^(- |\d+\. )", "", line)
            out.append(f"<li>{inline(item)}</li>"); continue
        close()
        if line.startswith("## "):
            out.append(f"<h2>{inline(line[3:])}</h2>")
        elif line.startswith("# "):
            out.append(f"<h1>{inline(line[2:])}</h1>")
        elif line.strip():
            out.append(f"<p>{inline(line)}</p>")
    close()
    style = ("body{font-family:system-ui,sans-serif;max-width:760px;margin:0 auto;padding:16px;line-height:1.5}"
             "pre{background:#f2f2f5;padding:8px;white-space:pre-wrap}table{border-collapse:collapse}"
             "td,th{border:1px solid #ccc;padding:4px 6px;text-align:left;vertical-align:top}")
    return (f"<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\"><meta name=\"viewport\" "
            f"content=\"width=device-width,initial-scale=1\"><title>{html.escape(title)}</title><style>{style}</style>"
            f"</head><body>{''.join(out)}</body></html>")
