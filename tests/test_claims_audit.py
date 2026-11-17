"""Every cited URL in outputs/ was retrieved by a logged research action, and the committed audit matches."""
from evals import claims_audit


def test_committed_claims_audit_matches_outputs_and_log():
    assert claims_audit.OUT.read_text(encoding="utf-8") == claims_audit.report(*claims_audit.load())


def test_every_cited_url_was_retrieved_by_a_logged_action():
    rows = claims_audit.audit(*claims_audit.load())
    assert sum(r["sourced"] for r in rows.values()) > 0
    assert [u for r in rows.values() for u in r["unretrieved"]] == []


def test_an_invented_citation_is_flagged():
    log = [{"sources": ["https://news.ycombinator.com/item?id=1"]}]
    text = "- Real. [source: https://news.ycombinator.com/item?id=1]\n- Made up. [source: https://example.com/fake]\n"
    r = claims_audit.audit_file(text, claims_audit.retrieved(log))
    assert r["sourced"] == 2 and r["unretrieved"] == ["https://example.com/fake"]
