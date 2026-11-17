"""Append-only decision log: one entry per agent action.

Format follows the organizers' spec: a JSON array where every entry has
timestamp, agent, action, sources, model, cost, approved_by. Extra keys
(run_id, outcome, detail, prev_hash, hash) are allowed. Each entry carries a
hash of the previous one so edits after the fact are detectable.
"""
from __future__ import annotations

import hashlib
import json
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REQUIRED_KEYS = ("timestamp", "agent", "action", "sources", "model", "cost", "approved_by")
_lock = threading.RLock()


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _digest(entry: dict[str, Any]) -> str:
    body = {k: v for k, v in entry.items() if k != "hash"}
    return hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest()[:16]


class DecisionLog:
    def __init__(self, path: Path):
        self.path = Path(path)

    def read(self) -> list[dict[str, Any]]:
        for i in range(20):
            try:
                if not self.path.exists():
                    return []
                text = self.path.read_text(encoding="utf-8")
                return json.loads(text) if text.strip() else []
            except (PermissionError, json.JSONDecodeError):
                if i == 19:
                    raise
                time.sleep(0.05 * (i + 1))
        return []

    def append(
        self,
        *,
        agent: str,
        action: str,
        sources: list[str] | None = None,
        model: str | None = None,
        cost: float = 0,
        approved_by: str | None = None,
        **extra: Any,
    ) -> dict[str, Any]:
        if approved_by not in (None, "founder"):
            raise ValueError("approved_by must be 'founder' or None")
        with _lock:
            entries = self.read()
            entry: dict[str, Any] = {
                "timestamp": _now(),
                "agent": agent,
                "action": action,
                "sources": list(dict.fromkeys(sources or [])),
                "model": model,
                "cost": cost,
                "approved_by": approved_by,
                **extra,
                "prev_hash": entries[-1]["hash"] if entries else None,
            }
            entry["hash"] = _digest(entry)
            entries.append(entry)
            self.path.parent.mkdir(parents=True, exist_ok=True)
            text = json.dumps(entries, indent=1, ensure_ascii=False) + "\n"
            tmp = self.path.with_name(self.path.name + ".tmp")
            tmp.write_text(text, encoding="utf-8")
            for i in range(20):
                try:
                    tmp.replace(self.path)
                    break
                except PermissionError:  # Windows: file is being read right now
                    time.sleep(0.05 * (i + 1))
                except OSError:  # e.g. the file is a Docker bind mount
                    break
            if tmp.exists():
                self.path.write_text(text, encoding="utf-8")
                tmp.unlink(missing_ok=True)
            return entry


def validate(entries: list[dict[str, Any]]) -> list[str]:
    """Return a list of problems; empty means the log is valid."""
    problems: list[str] = []
    prev = None
    for i, e in enumerate(entries):
        for k in REQUIRED_KEYS:
            if k not in e:
                problems.append(f"entry {i}: missing key '{k}'")
        if not isinstance(e.get("action"), str):
            problems.append(f"entry {i}: action must be a string")
        if not isinstance(e.get("sources"), list):
            problems.append(f"entry {i}: sources must be a list")
        if e.get("model") is not None and not isinstance(e.get("model"), str):
            problems.append(f"entry {i}: model must be a string or null")
        if not isinstance(e.get("cost"), (int, float)):
            problems.append(f"entry {i}: cost must be a number")
        if e.get("approved_by") not in (None, "founder"):
            problems.append(f"entry {i}: approved_by must be 'founder' or null")
        if "hash" in e:
            if e.get("prev_hash") != prev:
                problems.append(f"entry {i}: hash chain broken")
            if _digest(e) != e["hash"]:
                problems.append(f"entry {i}: entry was modified after logging")
            prev = e["hash"]
    return problems


if __name__ == "__main__":
    import sys

    from app.config import load_settings

    path = Path(sys.argv[1]) if len(sys.argv) > 1 else load_settings().decision_log_path
    issues = validate(DecisionLog(path).read())
    print("decision log valid" if not issues else "\n".join(issues))
    sys.exit(1 if issues else 0)
