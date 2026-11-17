"""Command-line founder console.

  python -m app.cli run briefs/study-notes.json     # interactive: you approve every gate and action
  python -m app.cli code <run_id>                  # Phase 3 step 4: write the core code and test it in the sandbox
  python -m app.cli payment-test                    # MOCKED sale-to-cash test -> outputs/payment_test_log.md
  python -m app.cli validate-log                    # check decision_log.json
"""
from __future__ import annotations

import json
import sys

from app.brief import FounderBrief
from app.config import load_settings
from app.decision_log import DecisionLog, validate
from app.llm import make_llm
from app.orchestrator import Orchestrator


def ask(prompt: str, choices: tuple[str, ...]) -> str:
    while True:
        a = input(f"{prompt} [{'/'.join(choices)}]: ").strip().lower()
        if a in choices:
            return a


def run(path: str) -> None:
    s = load_settings()
    llm = make_llm(s)
    if not llm.health():
        sys.exit(f"Model '{s.model}' is not ready (provider {s.provider}). Ollama: run `ollama pull {s.model}`; "
                 "free-tier endpoint: set OPENAI_API_KEY in .env")
    orch = Orchestrator(s, llm)
    brief = FounderBrief(**json.loads(open(path, encoding="utf-8").read()))
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
        if st.stage in ("p1_gate_wait", "p2_gate_wait", "p3_gate_wait", "p4_gate_wait", "p5_gate_wait",
                        "p6_gate_wait"):
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
        elif st.stage == "p6_collecting":
            print(f"\nSign-ups counted by the app since launch: "
                  f"{orch.signups(st.run_id) - st.launch.get('signups_at_launch', 0)}")
            if ask("Record launch results now and run the learn gate?", ("y", "n")) == "n":
                print(f"Paused. Resume in the web UI: {s.public_base_url}/runs/{st.run_id}")
                break
            visits = int(input("Store page visits (from your own analytics): "))
            paid = int(input("Paid orders (from your own payment provider; 0 while checkout is MOCKED): "))
            print("Paste real user feedback, one item per line; empty line to finish:")
            fb = []
            while (line := input().strip()):
                fb.append(line)
            st = orch.founder_record_launch_results(st.run_id, visits, paid, fb)
        elif st.stage in ("stopped", "done"):
            break
    print(f"\nRun {st.run_id} ended at stage '{st.stage}'. Outputs: {', '.join(st.outputs)}")
    u = llm.usage
    print(f"Model calls {u.calls}, tokens {u.total_tokens}, cost ${u.cost_usd:.2f}")


def payment_test() -> None:
    """Exercises sale-to-cash on MOCKED events. No provider, no money."""
    from app.sale_to_cash import run_payment_test
    s = load_settings()
    text, ok = run_payment_test()
    s.outputs_dir.mkdir(parents=True, exist_ok=True)
    (s.outputs_dir / "payment_test_log.md").write_text(text, encoding="utf-8")
    DecisionLog(s.decision_log_path).append(agent="delivery", action="mock_payment_delivery_test",
                                            outcome="pass" if ok else "fail")
    print(text)


def main() -> None:
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    cmd = sys.argv[1]
    if cmd == "run" and len(sys.argv) == 3:
        run(sys.argv[2])
    elif cmd == "code" and len(sys.argv) == 3:
        s = load_settings()
        st = Orchestrator(s, make_llm(s)).founder_generate_code(sys.argv[2])
        print(f"{st.code['passed']}/{st.code['total']} acceptance checks passed; see outputs/{next(o for o in st.outputs if o.startswith('phase3_step4'))}")
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
