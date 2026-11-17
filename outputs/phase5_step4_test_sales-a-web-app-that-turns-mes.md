# Phase 5, step 4: Test-mode sales on the MVP app (payments MOCKED)

Product: ExamReady AI. Every order below was placed through the app's test-mode checkout, and every event went through the same webhook handler a real provider would call. The provider, its events, its fee and the payout are MOCKED: no card, money or account is involved. Test orders are not revenue and are not counted as paid orders in Phase 6.

| Order | Plan | Amount (USD) | Status | Access key | Events (id type -> outcome) |
|---|---|---|---|---|---|
| ord_test_132328bb | Pro | 9.99 | refunded | revoked | evt_test_57cfe80711 payment_succeeded -> delivered; evt_test_036e21e1e5 refund_succeeded -> access_revoked |
| ord_test_f344d9b0 | Pro | 9.99 | paid | active | evt_test_52a41bb416 payment_succeeded -> delivered |
| ord_test_b46331ca | Pro | 9.99 | paid | active | evt_test_dcdb264f14 payment_succeeded -> delivered |

## Reconciliation

| Check | Value |
|---|---|
| Orders / paid / refunded / open | 3 / 3 / 1 / 0 |
| Events processed (duplicates are not stored) | 4 |
| Deliveries made | 3 (one per paid order: True) |
| Gross / MOCKED fees / refunded | 29.97 / 1.50 / 9.99 |
| MOCKED payout = gross - fees - refunded (the fee on a refunded order is not returned) | 18.48 |
| Reconciliation issues | none |
