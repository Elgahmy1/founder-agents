"""Founder-reported numbers close the MOCKED loops; forks reuse sources without touching the parent; compare is read-only."""
from fastapi.testclient import TestClient

from app import imports


def test_waitlist_csv_counts_unique_emails_and_keeps_only_hashes():
    csv = "Timestamp,Email\n1,Sara@Example.com\n2,sara@example.com \n3,omar@test.eg\n4,not an email\n"
    h = imports.parse_waitlist_csv(csv)
    assert len(h) == 2 and all(len(x) == 64 and "@" not in x for x in h)


def test_sales_csv_counts_without_amounts_and_dedupes_orders():
    csv = "order_id,type,status,amount\nA1,order,paid,100\nA1,order,paid,100\nA2,order,refunded,50\nB1,activation,active,\n"
    assert imports.parse_sales_csv(csv) == {"orders": 1, "activations": 1, "not_completed": 1, "rows": 4}


def test_static_export_points_the_form_at_the_founders_endpoint():
    page = '<form method="post" action="/lp/r1/join"><input name="email"></form></body>'
    out = imports.export_landing(page, "r1", "https://formspree.io/f/abc")
    assert 'action="https://formspree.io/f/abc"' in out and "/lp/r1/join" not in out
    for bad in ("javascript:alert(1)", "http://insecure.example", "/local"):
        try:
            imports.export_landing(page, "r1", bad)
            raise AssertionError(bad)
        except ValueError:
            pass


def test_imported_signups_feed_the_demand_gate_labelled(make_orch, brief):
    orch = make_orch()
    st = orch.start(brief)
    st = orch.founder_gate_decision(st.run_id, "go")
    _, q = orch.load(st.run_id)
    for i in q.pending():
        orch.approve(st.run_id, i.id, True)
    st, _ = orch.load(st.run_id)
    if st.stage == "p2_targets_wait":
        st = orch.founder_lock_targets(st.run_id, True)
    assert st.stage == "p2_collecting", st.stage
    orch.founder_import_waitlist(st.run_id, "email\na@x.com\nb@x.com\nb@x.com\n", "form.csv")
    st = orch.founder_record_results(st.run_id, 5, 3)
    assert st.results["signups"] == 2
    log = orch.log.read()
    assert any(e["action"] == "import_waitlist_csv" and "[FOUNDER-REPORTED METRIC]" in e["detail"] for e in log)


def test_fork_reuses_sources_never_touches_parent_and_compare_is_read_only(monkeypatch, make_orch, brief):
    import app.main as main
    orch = make_orch()
    monkeypatch.setattr(main, "orch", orch)
    parent = orch.start(brief)
    child = orch.fork(parent.run_id)
    assert child.parent_run_id == parent.run_id and child.docs == parent.docs and child.slug != parent.slug
    e = [x for x in orch.log.read() if x["action"] == "fork_run"][-1]
    assert e["parent_run_id"] == parent.run_id and e["fork_from_phase"] == 1
    assert orch.load(parent.run_id)[0].stage == parent.stage
    r = TestClient(main.app).get(f"/compare/{parent.run_id}/{child.run_id}")
    assert r.status_code == 200 and "Forked from" in r.text and parent.run_id in r.text
