import json

from app.decision_log import REQUIRED_KEYS, DecisionLog, validate


def test_entries_have_required_keys_and_chain(tmp_path):
    log = DecisionLog(tmp_path / "d.json")
    log.append(agent="researcher", action="find_opportunities", sources=["https://x.y"], model="m")
    log.append(agent="gate", action="evidence_gate", outcome="stop")
    entries = log.read()
    assert all(k in e for e in entries for k in REQUIRED_KEYS)
    assert validate(entries) == []


def test_tampering_is_detected(tmp_path):
    p = tmp_path / "d.json"
    log = DecisionLog(p)
    log.append(agent="gate", action="evidence_gate", outcome="stop")
    log.append(agent="founder", action="decide", approved_by="founder")
    entries = json.loads(p.read_text())
    entries[0]["outcome"] = "go"
    assert validate(entries)


def test_payment_mock_is_idempotent_and_refund_revokes():
    from app.delivery import Delivery
    from app.payments import MockLedger, MockPaymentEvent
    led = MockLedger()
    led.create_order("o1", "p", 100)
    d = Delivery(led)
    ev = MockPaymentEvent("e1", "o1", "payment_succeeded", 100)
    assert d.handle(ev) == "delivered"
    assert d.handle(ev) == "duplicate_ignored"
    assert d.deliveries == 1
    assert d.handle(MockPaymentEvent("e2", "o1", "refund_succeeded", 100)) == "access_revoked"
    assert d.access["o1"] is False
