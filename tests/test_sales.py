"""Phase 5 sale to cash on the real MVP app: test checkout -> webhook -> access key -> refund revokes.
Payments are MOCKED; these tests check the logic around them."""
import re

import pytest
from fastapi.testclient import TestClient

from app.decision_log import validate
from app.payments import MockPaymentEvent
from app.sales import FREE_INPUT_CHARS, SalesBook
from tests.test_launch import _to_launch


def _live(orch, brief, monkeypatch):
    import app.main as main
    monkeypatch.setattr(main, "orch", orch)
    monkeypatch.setattr(main, "settings", orch.settings)
    c = TestClient(main.app)
    st = _to_launch(orch, brief)
    assert c.get(f"/order/{st.run_id}").status_code == 404  # nothing approved yet
    orch.founder_generate_code(st.run_id)
    orch.founder_build_mvp(st.run_id)
    _, q = orch.load(st.run_id)
    for i in q.pending():
        orch.approve(st.run_id, i.id, i.executor in ("publish_store_local", "publish_mvp_local"))
    return c, st


def test_book_is_idempotent_and_reconciles(tmp_path):
    b = SalesBook(tmp_path, "r1")
    with pytest.raises(ValueError):
        b.create_test_order("P", "Free", 0)
    o1, o2 = b.create_test_order("P", "Pro", 400), b.create_test_order("P", "Pro", 400)
    ev = b.mock_provider_event(o1, "payment_succeeded")
    out, key = b.handle_event(ev)
    assert out == "delivered" and key and b.check_key(key) == ("pro", o1)
    assert b.handle_event(ev) == ("duplicate_ignored", None)
    _, k2 = b.handle_event(b.mock_provider_event(o2, "payment_succeeded"))
    assert b.handle_event(b.mock_provider_event(o2, "refund_succeeded"))[0] == "access_revoked"
    assert b.check_key(k2) == ("revoked", o2) and b.check_key("pro_guess") == ("free", None)
    assert key not in b.path.read_text()  # only the hash is stored
    r = b.reconcile()
    assert (r["paid"], r["refunded"], r["deliveries"], r["issues"]) == (2, 1, 2, [])
    assert r["net_payout_cents"] == 2 * (400 - 20) - 400  # the refunded order's fee is not returned
    assert "Reconciliation issues | none" in b.report_md("P")
    # a second, different payment event for a paid order: no second delivery, and reconciliation flags the double charge
    assert b.handle_event(b.mock_provider_event(o1, "payment_succeeded"))[0] == "already_delivered"
    r = b.reconcile()
    assert r["deliveries"] == 2 and any("charged twice" in i for i in r["issues"])


def test_checkout_delivers_key_refund_revokes_and_retry_never_redelivers(make_orch, brief, monkeypatch):
    orch = make_orch()
    c, st = _live(orch, brief, monkeypatch)
    store = c.get(f"/store/{st.run_id}").text
    assert f"/order/{st.run_id}" in store
    page = c.get(f"/order/{st.run_id}").text
    assert "TEST MODE" in page and all("type='hidden'" in i for i in re.findall(r"<input[^>]*>", page))  # no card fields
    tier = re.search(r"name='tier' value='([^']+)'", page).group(1)
    r = c.post(f"/order/{st.run_id}", data={"tier": tier}).text
    key = re.search(r"\?key=([\w-]+)", r).group(1)
    evt = re.search(r"name='event_id' value='([^']+)'", r).group(1)
    oid = re.search(r"Test order (ord_test_\w+)", r).group(1)
    long_text = "Cells divide. " * (FREE_INPUT_CHARS // 14 + 10)
    assert "this plan allows" in c.post(f"/mvp/{st.run_id}", data={"text": long_text}).text  # free limit
    pro = c.post(f"/mvp/{st.run_id}?key={key}", data={"text": long_text}).text
    assert "Pro access" in pro and "Cells divide." in pro and "this plan allows" not in pro
    assert "duplicate_ignored" in c.post(f"/webhooks/mock-provider/{st.run_id}/replay", data={"event_id": evt}).text
    assert c.post(f"/webhooks/mock-provider/{st.run_id}/replay", data={"event_id": "evt_forged"}).status_code == 404
    assert "Send refund event" in c.get(f"/runs/{st.run_id}").text
    c.post(f"/runs/{st.run_id}/sales/{oid}/refund")
    assert "revoked" in c.get(f"/mvp/{st.run_id}?key={key}").text
    c.post(f"/runs/{st.run_id}/sales/reconcile")
    st2, _ = orch.load(st.run_id)
    out = next(o for o in st2.outputs if o.startswith("phase5_step4_test_sales"))
    md = (orch.settings.outputs_dir / out).read_text()
    assert "refunded" in md and "Deliveries made | 1 (one per paid order: True)" in md and "issues | none" in md
    log = orch.log.read()
    acts = [(e["agent"], e["action"], e.get("outcome")) for e in log]
    for a in [("checkout", "create_test_order", "open"), ("webhooks", "receive_payment_event", "delivered"),
              ("delivery", "issue_access_key", "delivered"), ("webhooks", "receive_payment_event", "duplicate_ignored"),
              ("delivery", "revoke_access_key", "revoked"), ("reconcile", "reconcile_orders", "pass")]:
        assert a in acts, a
    assert sum(1 for a in acts if a[1] == "issue_access_key") == 1
    assert key not in orch.log.path.read_text()  # keys never reach the log
    assert not validate(log)
