"""Phase 6 usage analytics, counted by the app itself.

Each published page counts its own views: the store page, the landing page and
the MVP app (page views and runs). Only a page name and a UTC date are stored, per
run, in data/analytics/<run>.json: no cookies, IP addresses, user agents or
anything else about the visitor. Views opened from the founder's dashboard are
not counted. Pages are served on this computer while public hosting is MOCKED,
so the counts only include visits that reached this server.
"""
from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path

PAGES = ("store", "landing", "mvp_view", "mvp_run")
_lock = threading.Lock()


def from_dashboard(referer: str | None) -> bool:
    """A view opened from the founder's own dashboard (/runs/...) is the founder checking, not a visitor."""
    return bool(referer) and "/runs/" in referer


class PageCounter:
    def __init__(self, data_dir: Path, run_id: str):
        self.path = Path(data_dir) / "analytics" / f"{Path(run_id).name}.json"

    def _read(self) -> dict:
        if self.path.exists():
            return json.loads(self.path.read_text(encoding="utf-8"))
        return {}

    def hit(self, page: str) -> None:
        if page not in PAGES:
            raise ValueError(page)
        day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        with _lock:
            data = self._read()
            data.setdefault(page, {})
            data[page][day] = data[page].get(day, 0) + 1
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_suffix(".tmp")
            tmp.write_text(json.dumps(data, indent=1, sort_keys=True), encoding="utf-8")
            tmp.replace(self.path)

    def totals(self) -> dict[str, int]:
        data = self._read()
        return {p: sum(data.get(p, {}).values()) for p in PAGES}

    def since(self, snapshot: dict | None) -> dict[str, int]:
        """Counts since a snapshot of totals (taken at the launch decision)."""
        now, base = self.totals(), snapshot or {}
        return {p: max(0, now[p] - int(base.get(p, 0))) for p in PAGES}
