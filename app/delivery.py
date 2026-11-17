"""Delivery: MOCKED. Grants or revokes access to a digital product in
response to (mock) payment events. Idempotent per event id."""
from __future__ import annotations

from dataclasses import dataclass, field

from app.payments import MockLedger, MockPaymentEvent

MOCKED = True


@dataclass
class Delivery:
    ledger: MockLedger
    processed_events: set[str] = field(default_factory=set)
    access: dict[str, bool] = field(default_factory=dict)  # order_id -> has access
    deliveries: int = 0

    def handle(self, ev: MockPaymentEvent) -> str:
        if ev.event_id in self.processed_events:
            return "duplicate_ignored"
        self.processed_events.add(ev.event_id)
        order = self.ledger.orders.get(ev.order_id)
        if order is None:
            return "unknown_order"
        self.ledger.payments[ev.event_id] = ev
        if ev.type == "payment_succeeded":
            if self.access.get(ev.order_id):
                return "already_delivered"
            self.access[ev.order_id] = True
            order["status"] = "paid"
            self.deliveries += 1
            return "delivered"
        if ev.type == "refund_succeeded":
            self.access[ev.order_id] = False
            order["status"] = "refunded"
            return "access_revoked"
        return "ignored"
