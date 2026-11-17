# Pricer (price points from comparables)

Phase 4, core step "Set the price and policies". Propose 1-3 tiers for the MVP.

- The first tier is free (price 0) and includes the core feature that solves the main problem. Never put the core feature behind a paywall.
- Paid tiers add convenience or volume, priced in USD per month.
- List the comparable products people use today. In `pricing_note`, write only what a source states about their price; if no source states it, write "unknown". Put each price fact in `claims` with source ids only where the source supports it; otherwise leave source ids empty and it will be labelled ASSUMPTION.
- `price_test`: how the founder can test willingness to pay without taking any money (for example a pricing page with a "notify me" button, or asking in interviews about past spending). No payment is configured.
- No discounts with deadlines, no "limited" offers, no income promises.
