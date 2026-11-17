"""Payments: MOCKED. This system never takes, holds, moves or refunds money.

The mock exists to exercise the sale-to-cash logic (delivery on payment,
idempotency, refunds revoking access, reconciliation) without any provider,
sandbox, card data or account.
"""
from __future__ import annotations

from dataclasses import dataclass, field

MOCKED = True


@dataclass
class MockPaymentEvent:
    event_id: str  # provider event id; used as the idempotency key
    order_id: str
    type: str  # "payment_succeeded" | "refund_succeeded"
    amount_cents: int
    fee_cents: int = 0


@dataclass
class MockLedger:
    orders: dict[str, dict] = field(default_factory=dict)
    payments: dict[str, MockPaymentEvent] = field(default_factory=dict)
    payouts: list[dict] = field(default_factory=list)

    def create_order(self, order_id: str, product: str, amount_cents: int) -> None:
        self.orders[order_id] = {"product": product, "amount_cents": amount_cents, "status": "open"}
