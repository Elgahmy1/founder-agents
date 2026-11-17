"""Phase 5 sale to cash on the real MVP app, with a MOCKED payment provider.

Test-mode only: there is no provider, sandbox, card field or money. A test
checkout creates an order; the mock provider's `payment_succeeded` event goes
through the same webhook handler a real provider would call. Delivery then
issues an access key for the run's MVP app (Pro plan), and a refund event
revokes it. Every event id is processed at most once, so a webhook retry never
delivers twice. Reconciliation matches orders, payments, fees and payouts.

State is event-sourced in data/sales/<run>.json: the ledger and access are
rebuilt by replaying the stored events through `delivery.Delivery`. Access
keys are shown to the buyer once and stored only as SHA-256 hashes. Test
orders are never counted as paid orders or revenue.
"""
from __future__ import annotations

import hashlib
import json
import secrets
import threading
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from app.delivery import Delivery
from app.payments import MockLedger, MockPaymentEvent
from app.reconcile import reconcile

MOCKED = True
FEE_RATE = 0.05  # MOCKED provider fee, so reconciliation has fees to match
FREE_INPUT_CHARS = 5000
PRO_INPUT_CHARS = 20000
_lock = threading.Lock()


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _hash(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


class SalesBook:
    def __init__(self, data_dir: Path, run_id: str):
        self.run_id = Path(run_id).name
        self.path = Path(data_dir) / "sales" / f"{self.run_id}.json"

    # ---------- storage ----------
    def _read(self) -> dict:
        if self.path.exists():
            return json.loads(self.path.read_text(encoding="utf-8"))
        return {"orders": {}, "events": [], "keys": {}, "payouts": []}

    def _write(self, data: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=1), encoding="utf-8")
        tmp.replace(self.path)

    @staticmethod
    def _replay(data: dict) -> tuple[MockLedger, Delivery]:
        ledger = MockLedger()
        for oid, o in data["orders"].items():
            ledger.create_order(oid, o["product"], o["amount_cents"])
        d = Delivery(ledger)
        for ev in data["events"]:
            d.handle(MockPaymentEvent(**ev["event"]))
        ledger.payouts.extend(data["payouts"])
        return ledger, d

    # ---------- checkout and webhooks ----------
    def create_test_order(self, product: str, tier: str, amount_cents: int) -> str:
        if amount_cents <= 0:
            raise ValueError("only a paid plan needs a checkout; the free plan is open to everyone")
        with _lock:
            data = self._read()
            oid = f"ord_test_{secrets.token_hex(4)}"
            data["orders"][oid] = {"product": product, "tier": tier, "amount_cents": amount_cents,
                                   "created": _now(), "test_mode": True}
            self._write(data)
        return oid

    def mock_provider_event(self, order_id: str, kind: str) -> MockPaymentEvent:
        """What the MOCKED provider would send for this order (a new event id each time)."""
        data = self._read()
        o = data["orders"].get(order_id)
        if o is None:
            raise KeyError(order_id)
        fee = max(1, round(o["amount_cents"] * FEE_RATE)) if kind == "payment_succeeded" else 0
        return MockPaymentEvent(f"evt_test_{secrets.token_hex(5)}", order_id, kind, o["amount_cents"], fee)

    def handle_event(self, ev: MockPaymentEvent) -> tuple[str, str | None]:
        """The webhook handler. Returns (outcome, access key or None). Idempotent per event id."""
        with _lock:
            data = self._read()
            _, d = self._replay(data)
            outcome = d.handle(ev)
            key = None
            if outcome == "duplicate_ignored":
                return outcome, None
            data["events"].append({"received": _now(), "event": asdict(ev), "outcome": outcome})
            if outcome == "delivered":
                key = f"pro_{secrets.token_urlsafe(18)}"
                data["keys"][_hash(key)] = ev.order_id
            self._write(data)
        return outcome, key

    def stored_event(self, event_id: str) -> MockPaymentEvent:
        """An event already received, for a provider retry. Unknown event ids are refused: a real handler would
        also verify the provider's signature, which the MOCKED provider does not have."""
        for e in self._read()["events"]:
            if e["event"]["event_id"] == event_id:
                return MockPaymentEvent(**e["event"])
        raise KeyError(event_id)

    # ---------- access ----------
    def check_key(self, key: str | None) -> tuple[str, str | None]:
        """('pro', order) for a key whose order is paid, ('revoked', order) after a refund, else ('free', None)."""
        if not key:
            return "free", None
        data = self._read()
        oid = data["keys"].get(_hash(key))
        if oid is None:
            return "free", None
        _, d = self._replay(data)
        return ("pro" if d.access.get(oid) else "revoked"), oid

    # ---------- reporting ----------
    def orders(self) -> list[dict]:
        data = self._read()
        ledger, d = self._replay(data)
        out = []
        for oid, o in data["orders"].items():
            out.append({"order_id": oid, **o, "status": ledger.orders[oid]["status"],
                        "access": bool(d.access.get(oid)),
                        "events": [e["event"]["event_id"] + " " + e["event"]["type"] + " -> " + e["outcome"]
                                   for e in data["events"] if e["event"]["order_id"] == oid]})
        return out

    def reconcile(self) -> dict:
        """Matches orders, payments, fees and the MOCKED payout of the net amount still held."""
        with _lock:
            data = self._read()
            ledger, d = self._replay(data)
            paid = [e for e in ledger.payments.values() if e.type == "payment_succeeded"]
            refunded = {e.order_id for e in ledger.payments.values() if e.type == "refund_succeeded"}
            net = sum(e.amount_cents - e.fee_cents for e in paid if e.order_id not in refunded)
            data["payouts"] = [{"amount_cents": net, "mocked": True}] if paid else []
            self._write(data)
            ledger.payouts[:] = data["payouts"]
            issues = reconcile(ledger)
        return {"orders": len(ledger.orders), "paid": len(paid), "refunded": len(refunded),
                "open": sum(1 for o in ledger.orders.values() if o["status"] == "open"),
                "deliveries": d.deliveries, "events": len(data["events"]),
                "gross_cents": sum(e.amount_cents for e in paid), "fees_cents": sum(e.fee_cents for e in paid),
                "refunded_cents": sum(e.amount_cents for e in paid if e.order_id in refunded),
                "net_payout_cents": net, "issues": issues}

    def report_md(self, product: str) -> str:
        r = self.reconcile()
        rows = self.orders()
        usd = lambda c: f"{c / 100:.2f}"  # noqa: E731
        lines = [
            "# Phase 5, step 4: Test-mode sales on the MVP app (payments MOCKED)", "",
            f"Product: {product}. Every order below was placed through the app's test-mode checkout, and every event "
            "went through the same webhook handler a real provider would call. The provider, its events, its fee and "
            "the payout are MOCKED: no card, money or account is involved. Test orders are not revenue and are not "
            "counted as paid orders in Phase 6.", "",
            "| Order | Plan | Amount (USD) | Status | Access key | Events (id type -> outcome) |", "|---|---|---|---|---|---|",
            *[f"| {o['order_id']} | {o['tier']} | {usd(o['amount_cents'])} | {o['status']} | "
              f"{'active' if o['access'] else 'revoked' if o['status'] == 'refunded' else 'none'} | "
              f"{'; '.join(o['events']) or 'none'} |" for o in rows],
            "", "## Reconciliation", "",
            "| Check | Value |", "|---|---|",
            f"| Orders / paid / refunded / open | {r['orders']} / {r['paid']} / {r['refunded']} / {r['open']} |",
            f"| Events processed (duplicates are not stored) | {r['events']} |",
            f"| Deliveries made | {r['deliveries']} (one per paid order: {r['deliveries'] == r['paid']}) |",
            f"| Gross / MOCKED fees / refunded | {usd(r['gross_cents'])} / {usd(r['fees_cents'])} / {usd(r['refunded_cents'])} |",
            f"| MOCKED payout (net of fees and refunds) | {usd(r['net_payout_cents'])} |",
            f"| Reconciliation issues | {'; '.join(r['issues']) or 'none'} |",
        ]
        return "\n".join(lines) + "\n"
