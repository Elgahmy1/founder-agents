"""Sandbox for model-written MVP code (Phase 3, step 4).

Two layers, both in code:
1. Static check (AST) before anything runs: only an allowlist of pure standard-library imports; no file, process,
   network or introspection calls (open, exec, eval, __import__, getattr, dunder attributes ...).
2. Execution in a separate, isolated Python process (`python -I`), empty environment, temporary working
   directory, wall-clock timeout, and on POSIX also CPU, memory, file-size and open-file limits.

This is a process sandbox, not a virtual machine: it is meant for small, pure functions that implement the
core user story, checked against the acceptance criteria. Nothing it produces is published or deployed.
"""
from __future__ import annotations

import ast
import json
import os
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

ALLOWED_IMPORTS = {"re", "json", "math", "datetime", "collections", "dataclasses", "typing", "itertools",
                   "string", "textwrap", "statistics", "functools", "enum", "heapq", "bisect", "random", "unicodedata",
                   "difflib", "decimal", "fractions", "operator", "copy", "__future__"}
BANNED_NAMES = {"open", "exec", "eval", "compile", "__import__", "input", "globals", "locals", "vars", "getattr",
                "setattr", "delattr", "breakpoint", "exit", "quit", "memoryview", "help", "dir", "type", "object"}
TIMEOUT_S = 10

_HARNESS = r'''
import json, sys, traceback
src = open("core.py", encoding="utf-8").read()
checks = json.load(open("checks.json", encoding="utf-8"))
results = []
ns = {"__name__": "core"}
try:
    exec(compile(src, "core.py", "exec"), ns)
except Exception as e:
    print(json.dumps({"load_error": f"{type(e).__name__}: {e}", "results": []})); sys.exit(0)
for c in checks:
    local = dict(ns)
    try:
        exec(compile(c, "check", "exec"), local)
        results.append({"passed": True, "error": None})
    except AssertionError as e:
        results.append({"passed": False, "error": f"AssertionError: {e}"[:300]})
    except Exception as e:
        results.append({"passed": False, "error": f"{type(e).__name__}: {e}"[:300]})
print(json.dumps({"load_error": None, "results": results}))
'''


def static_problems(code: str) -> list[str]:
    """Reasons the code may not run, or [] if it passes the static check."""
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        return [f"syntax error: {e.msg} (line {e.lineno})"]
    problems: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                if a.name.split(".")[0] not in ALLOWED_IMPORTS:
                    problems.append(f"import of '{a.name}' is not allowed")
        elif isinstance(node, ast.ImportFrom):
            if (node.module or "").split(".")[0] not in ALLOWED_IMPORTS:
                problems.append(f"import from '{node.module}' is not allowed")
        elif isinstance(node, ast.Name) and node.id in BANNED_NAMES:
            problems.append(f"use of '{node.id}' is not allowed")
        elif isinstance(node, ast.Attribute) and node.attr.startswith("__"):
            problems.append(f"dunder attribute '{node.attr}' is not allowed")
        elif isinstance(node, (ast.Global, ast.Nonlocal)):
            problems.append("global/nonlocal is not allowed")
    return sorted(set(problems))


@dataclass
class SandboxResult:
    static_problems: list[str] = field(default_factory=list)
    load_error: str | None = None
    results: list[dict] = field(default_factory=list)
    timed_out: bool = False

    @property
    def passed(self) -> int:
        return sum(1 for r in self.results if r["passed"])

    @property
    def ok(self) -> bool:
        return (not self.static_problems and not self.load_error and not self.timed_out
                and bool(self.results) and self.passed == len(self.results))


def _limits():  # POSIX only: runs in the child before exec
    import resource
    resource.setrlimit(resource.RLIMIT_CPU, (5, 5))
    resource.setrlimit(resource.RLIMIT_AS, (512 * 2**20, 512 * 2**20))
    resource.setrlimit(resource.RLIMIT_FSIZE, (1 * 2**20, 1 * 2**20))


def _top_level_names(code: str) -> set[str]:
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return set()
    names: set[str] = set()
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
        elif isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            names |= {t.id for t in targets if isinstance(t, ast.Name)}
    return names


def strip_self_imports(check: str, code: str) -> str:
    """Checks run in the module's own namespace, so a check that imports the module's
    functions under an invented module name (`from summary_core import summarize`) would
    only trip the import allowlist. Such top-level lines are removed; nothing else changes."""
    try:
        tree = ast.parse(check)
    except SyntaxError:
        return check
    defined = _top_level_names(code)
    drop: set[int] = set()
    for node in tree.body:
        if (isinstance(node, ast.ImportFrom) and (node.module or "").split(".")[0] not in ALLOWED_IMPORTS
                and all(a.name in defined and (a.asname in (None, a.name)) for a in node.names)):
            drop |= set(range(node.lineno, (node.end_lineno or node.lineno) + 1))
    if not drop:
        return check
    return "\n".join(line for i, line in enumerate(check.splitlines(), 1) if i not in drop)


def run(code: str, checks: list[str]) -> SandboxResult:
    checks = [strip_self_imports(c, code) for c in checks]
    problems = static_problems(code)
    for i, c in enumerate(checks, 1):
        problems += [f"check {i}: {p}" for p in static_problems(c)]
    if problems:
        return SandboxResult(static_problems=problems)
    with tempfile.TemporaryDirectory(prefix="fa-sandbox-") as d:
        Path(d, "core.py").write_text(code, encoding="utf-8")
        Path(d, "checks.json").write_text(json.dumps(checks), encoding="utf-8")
        Path(d, "harness.py").write_text(_HARNESS, encoding="utf-8")
        env = {"PYTHONIOENCODING": "utf-8"}
        if os.name == "nt":  # Windows needs these to start Python at all
            env.update({k: os.environ[k] for k in ("SYSTEMROOT", "TEMP", "TMP") if k in os.environ})
        try:
            p = subprocess.run([sys.executable, "-I", "harness.py"], cwd=d, env=env, capture_output=True, text=True,
                               timeout=TIMEOUT_S, preexec_fn=_limits if os.name == "posix" else None)
        except subprocess.TimeoutExpired:
            return SandboxResult(timed_out=True)
        if p.returncode and p.returncode < 0:
            return SandboxResult(load_error=f"stopped by the sandbox limits (CPU, memory or file size; signal {-p.returncode})")
        try:
            out = json.loads(p.stdout.strip().splitlines()[-1])
        except (ValueError, IndexError):
            return SandboxResult(load_error=(p.stderr or "no output")[-300:])
        return SandboxResult(load_error=out["load_error"], results=out["results"])
