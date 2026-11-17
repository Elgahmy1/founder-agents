"""Sale-to-cash test on MOCKED provider events (no provider, sandbox, card data or money).
Used by `python -m app.cli payment-test` and by Phase 5 before the launch gate."""
from __future__ import annotations

from datetime import datetime, timezone

from app.delivery import Delivery
from app.payments import MockLedger, MockPaymentEvent
from app.reconcile import reconcile


def run_payment_test(product: str = "demo-product", amount_cents: int = 1500) -> tuple[str, bool]:
    fee = max(1, round(amount_cents * 0.05))
    ledger = MockLedger()
    d = Delivery(ledger)
    ledger.create_order("ord_1", product, amount_cents)
    ledger.create_order("ord_2", product, amount_cents)
    steps = [
        ("payment for ord_1 triggers delivery", MockPaymentEvent("evt_1", "ord_1", "payment_succeeded", amount_cents, fee), "delivered"),
        ("same event replayed (webhook retry)", MockPaymentEvent("evt_1", "ord_1", "payment_succeeded", amount_cents, fee), "duplicate_ignored"),
        ("payment for ord_2 triggers delivery", MockPaymentEvent("evt_2", "ord_2", "payment_succeeded", amount_cents, fee), "delivered"),
        ("refund for ord_2 revokes access", MockPaymentEvent("evt_3", "ord_2", "refund_succeeded", amount_cents, 0), "access_revoked"),
    ]
    lines = ["# Payment and delivery test log (MOCKED)", "",
             f"Run at {datetime.now(timezone.utc).isoformat(timespec='seconds')} for product '{product}' at "
             f"{amount_cents / 100:.2f} USD. All events are MOCKED: no payment provider, sandbox, card data or money is involved.", "",
             "| Step | Event | Expected | Got | Result |", "|---|---|---|---|---|"]
    ok_all = True
    for name, ev, expected in steps:
        got = d.handle(ev)
        ok = got == expected
        ok_all &= ok
        lines.append(f"| {name} | {ev.event_id} {ev.type} | {expected} | {got} | {'PASS' if ok else 'FAIL'} |")
    ledger.payouts.append({"amount_cents": amount_cents - 2 * fee})  # two fees kept; ord_2's amount refunded
    issues = reconcile(ledger)
    lines += ["", f"Deliveries made: {d.deliveries} (expected 2, idempotency held: {d.deliveries == 2})",
              f"Access now: {d.access}", f"Reconciliation issues: {issues or 'none'}"]
    ok_all &= d.deliveries == 2 and not issues
    lines.append(f"\n**Overall: {'PASS' if ok_all else 'FAIL'}**")
    return "\n".join(lines) + "\n", ok_all
