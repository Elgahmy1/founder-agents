"""Closing the MOCKED loops with the founder's own real numbers, never with ours.

- `parse_waitlist_csv`: a CSV exported from wherever the founder's own form collects sign-ups (Google Forms,
  Formspree, a mailto inbox). Only emails count, duplicates are dropped, and only a SHA-256 of each email is kept
  (no emails are stored). The count is labelled [FOUNDER-REPORTED METRIC] wherever it is shown.
- `parse_sales_csv`: a CSV of orders or activations the founder recorded in their own tools. Rows are counted by
  status; amounts, card data and credentials are never read or stored, and no payment API is called.
- `export_landing`: the Phase 2 landing page as one standalone HTML file with no backend, whose form posts to an
  endpoint the founder owns (mailto: or an https form service). The founder hosts it; this system never does.
"""
from __future__ import annotations

import csv
import hashlib
import io
import re

EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
DONE = re.compile(r"^(paid|completed?|succeeded|success|active|activated|fulfilled|delivered)$", re.I)
LABEL = "[FOUNDER-REPORTED METRIC]"


def email_hash(e: str) -> str:
    return hashlib.sha256(e.strip().lower().encode()).hexdigest()


def parse_waitlist_csv(text: str) -> set[str]:
    """Hashes of the unique emails found in any column."""
    out: set[str] = set()
    for row in csv.reader(io.StringIO(text or "")):
        for cell in row:
            m = EMAIL.search(cell or "")
            if m:
                out.add(email_hash(m.group(0)))
    return out


def parse_sales_csv(text: str) -> dict:
    """Counts rows by kind and status. Needs a header; recognised columns: type/kind (order or activation) and status.
    Rows without a recognised done status are counted as not completed. Order ids are deduplicated if present."""
    rows = list(csv.DictReader(io.StringIO(text or "")))
    seen, orders, activations, other = set(), 0, 0, 0
    for r in rows:
        low = {k.strip().lower(): (v or "").strip() for k, v in r.items() if k}
        oid = low.get("order_id") or low.get("id") or ""
        if oid and oid in seen:
            continue
        seen.add(oid)
        kind = (low.get("type") or low.get("kind") or "order").lower()
        if not DONE.match(low.get("status", "")):
            other += 1
        elif kind.startswith("activ"):
            activations += 1
        else:
            orders += 1
    return {"orders": orders, "activations": activations, "not_completed": other, "rows": len(rows)}


def export_landing(html_text: str, run_id: str, action: str) -> str:
    """Point the landing page's form at the founder's own endpoint and drop everything that needs our server."""
    action = (action or "").strip()
    if not (action.startswith("mailto:") or re.match(r"^https://[\w.-]+\.[a-z]{2,}(/\S*)?$", action, re.I)):
        raise ValueError("the form endpoint must be a mailto: address or an https:// form URL you own")
    out = html_text.replace(f'action="/lp/{run_id}/join"', f'action="{action}"')
    if action.startswith("mailto:"):
        out = out.replace('method="post"', 'method="post" enctype="text/plain"')
    return out.replace("</body>", "<!-- Exported by Founder Agents: static, no backend. Sign-ups go to the founder's own endpoint. -->\n</body>")
