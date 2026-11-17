"""Command-line founder console.

  python -m app.cli run briefs/study-notes.json     # interactive: you approve every gate and action
  python -m app.cli payment-test                    # MOCKED sale-to-cash test -> outputs/payment_test_log.md
  python -m app.cli validate-log                    # check decision_log.json
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone

from app.brief import FounderBrief
from app.config import load_settings
from app.decision_log import DecisionLog, validate
from app.llm import OllamaLLM
from app.orchestrator import Orchestrator


def ask(prompt: str, choices: tuple[str, ...]) -> str:
    while True:
        a = input(f"{prompt} [{'/'.join(choices)}]: ").strip().lower()
        if a in choices:
            return a


def run(path: str) -> None:
    s = load_settings()
    llm = OllamaLLM(s)
    if not llm.health():
        sys.exit(f"Model '{s.model}' is not available at {s.ollama_url}. Run: ollama pull {s.model}")
    orch = Orchestrator(s, llm)
    brief = FounderBrief(**json.loads(open(path).read()))
    print(f"Starting run for: {brief.idea}")
    st = orch.start(brief)
    while True:
        if st.error:
            print("ERROR:", st.error)
            if ask("Retry the step?", ("y", "n")) == "y":
                st = orch.advance(st.run_id)
                continue
            break
        _, q = orch.load(st.run_id)
        for item in q.pending():
            print(f"\n--- {item.kind.upper()} needs your approval: {item.title}\n{item.content[:1500]}\n---")
            d = ask("Approve?", ("y", "n"))
            note = input("Note (optional): ").strip() or None
            st = orch.approve(st.run_id, item.id, d == "y", note)
        if st.stage in ("p1_gate_wait", "p2_gate_wait"):
            g = st.gates[-1]
            print(f"\nGATE {g['gate']} -> system recommends {g['recommendation'].upper()}")
            for c in g["checks"]:
                print(f"  {'PASS' if c['passed'] else 'FAIL'}  {c['name']}: target {c['target']}, actual {c['actual']}")
            for r in g["reasons"]:
                print("  -", r)
            d = ask("Your decision", ("go", "repeat", "pivot", "stop"))
            st = orch.founder_gate_decision(st.run_id, d, input("Note (optional): ").strip() or None)
        elif st.stage == "p2_targets_wait":
            p = st.demand_plan
            print(f"\nProposed targets: {p['waitlist_signups_target']} sign-ups in {p['window_days']} days, "
                  f"{p['interviews_target']} interviews, {p['pain_confirm_rate_target']:.0%} confirm the problem")
            st = orch.founder_lock_targets(st.run_id, ask("Lock these targets?", ("y", "n")) == "y")
        elif st.stage == "p2_collecting":
            print(f"\nWaitlist sign-ups counted so far: {orch.signups(st.run_id)}")
            if ask("Record interview results now and run the demand gate?", ("y", "n")) == "n":
                print(f"Paused. Resume in the web UI: {s.public_base_url}/runs/{st.run_id}")
                break
            n = int(input("Interviews completed: "))
            k = int(input("Of those, how many confirmed the problem: "))
            st = orch.founder_record_results(st.run_id, n, k)
        elif st.stage in ("stopped", "done"):
            break
    print(f"\nRun {st.run_id} ended at stage '{st.stage}'. Outputs: {', '.join(st.outputs)}")
    u = llm.usage
    print(f"Model calls {u.calls}, tokens {u.total_tokens}, cost ${u.cost_usd:.2f}")


def payment_test() -> None:
    """Exercises sale-to-cash on MOCKED events. No provider, no money."""
    from app.delivery import Delivery
    from app.payments import MockLedger, MockPaymentEvent
    from app.reconcile import reconcile

    s = load_settings()
    log = DecisionLog(s.decision_log_path)
    ledger = MockLedger()
    d = Delivery(ledger)
    ledger.create_order("ord_1", "demo-product", 1500)
    ledger.create_order("ord_2", "demo-product", 1500)
    steps = [
        ("payment for ord_1 triggers delivery", MockPaymentEvent("evt_1", "ord_1", "payment_succeeded", 1500, 75), "delivered"),
        ("same event replayed (webhook retry)", MockPaymentEvent("evt_1", "ord_1", "payment_succeeded", 1500, 75), "duplicate_ignored"),
        ("payment for ord_2 triggers delivery", MockPaymentEvent("evt_2", "ord_2", "payment_succeeded", 1500, 75), "delivered"),
        ("refund for ord_2 revokes access", MockPaymentEvent("evt_3", "ord_2", "refund_succeeded", 1500, 0), "access_revoked"),
    ]
    lines = ["# Payment and delivery test log (MOCKED)", "",
             f"Run at {datetime.now(timezone.utc).isoformat(timespec='seconds')}. All events are MOCKED: "
             "no payment provider, sandbox, card data or money is involved.", "",
             "| Step | Event | Expected | Got | Result |", "|---|---|---|---|---|"]
    ok_all = True
    for name, ev, expected in steps:
        got = d.handle(ev)
        ok = got == expected
        ok_all &= ok
        lines.append(f"| {name} | {ev.event_id} {ev.type} | {expected} | {got} | {'PASS' if ok else 'FAIL'} |")
    ledger.payouts.append({"amount_cents": 1500 - 75})
    issues = reconcile(ledger)
    lines += ["", f"Deliveries made: {d.deliveries} (expected 2, idempotency held: {d.deliveries == 2})",
              f"Access now: {d.access}", f"Reconciliation issues: {issues or 'none'}"]
    ok_all &= d.deliveries == 2 and not issues
    lines.append(f"\n**Overall: {'PASS' if ok_all else 'FAIL'}**")
    s.outputs_dir.mkdir(parents=True, exist_ok=True)
    (s.outputs_dir / "payment_test_log.md").write_text("\n".join(lines) + "\n")
    log.append(agent="delivery", action="mock_payment_delivery_test", outcome="pass" if ok_all else "fail")
    print("\n".join(lines))


def main() -> None:
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    cmd = sys.argv[1]
    if cmd == "run" and len(sys.argv) == 3:
        run(sys.argv[2])
    elif cmd == "payment-test":
        payment_test()
    elif cmd == "validate-log":
        issues = validate(DecisionLog(load_settings().decision_log_path).read())
        print("decision log valid" if not issues else "\n".join(issues))
        sys.exit(1 if issues else 0)
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()
