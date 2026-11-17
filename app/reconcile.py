"""Reconciliation: matches orders, payments, fees and payouts. Runs on the
MOCKED ledger here; the same checks apply to a real provider export."""
from __future__ import annotations

from app.payments import MockLedger


def reconcile(ledger: MockLedger) -> list[str]:
    issues: list[str] = []
    paid = {e.order_id: e for e in ledger.payments.values() if e.type == "payment_succeeded"}
    refunded = {e.order_id for e in ledger.payments.values() if e.type == "refund_succeeded"}
    charges: dict[str, int] = {}
    for e in ledger.payments.values():
        if e.type == "payment_succeeded":
            charges[e.order_id] = charges.get(e.order_id, 0) + 1
    for oid, n in charges.items():
        if n > 1:
            issues.append(f"{oid}: {n} successful payments for one order (charged twice; refund the extra one)")
    for oid, order in ledger.orders.items():
        ev = paid.get(oid)
        if order["status"] in ("paid", "refunded") and ev is None:
            issues.append(f"{oid}: marked {order['status']} but no payment event")
        if ev and ev.amount_cents != order["amount_cents"]:
            issues.append(f"{oid}: paid {ev.amount_cents} but order is {order['amount_cents']}")
    expected = sum(e.amount_cents - e.fee_cents for o, e in paid.items() if o not in refunded)
    paid_out = sum(p["amount_cents"] for p in ledger.payouts)
    if ledger.payouts and expected != paid_out:
        issues.append(f"payouts {paid_out} != expected net {expected}")
    return issues
