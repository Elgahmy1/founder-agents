# Payment and delivery test log (MOCKED)

Run at 2026-11-17T09:44:50+00:00. All events are MOCKED: no payment provider, sandbox, card data or money is involved.

| Step | Event | Expected | Got | Result |
|---|---|---|---|---|
| payment for ord_1 triggers delivery | evt_1 payment_succeeded | delivered | delivered | PASS |
| same event replayed (webhook retry) | evt_1 payment_succeeded | duplicate_ignored | duplicate_ignored | PASS |
| payment for ord_2 triggers delivery | evt_2 payment_succeeded | delivered | delivered | PASS |
| refund for ord_2 revokes access | evt_3 refund_succeeded | access_revoked | access_revoked | PASS |

Deliveries made: 2 (expected 2, idempotency held: True)
Access now: {'ord_1': True, 'ord_2': False}
Reconciliation issues: none

**Overall: PASS**
