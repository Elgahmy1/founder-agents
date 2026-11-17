"""Funding scout: honest fit scores, verified names, contacts only from sources, never lenders."""


def test_funding_runs_for_promising_ideas_and_stays_honest(make_orch, brief, settings):
    orch = make_orch()
    st = orch.start(brief)
    assert st.verdict["verdict"] in ("strong", "promising")
    rows = {r["name"]: r for r in st.funding["funders"]}
    assert "City Bank Startup Loans" not in rows  # lending is dropped
    n = rows["Notion for Startups"]
    assert n["verified"] and n["fit"] == 67 and n["contact"] == "https://example.com/notion-vs-obsidian"
    i = rows["Imaginary Founders Fund"]
    assert not i["verified"] and i["contact"] == ""  # an email not in any source is never shown
    out = (settings.outputs_dir / next(o for o in st.outputs if o.startswith("phase1_step5_funding"))).read_text(encoding="utf-8")
    assert "not a probability of being funded" in out and "UNVERIFIED" in out and "Dropped (lending" in out
    assert "hello@imaginary.example" not in out
    assert "a draft only: nothing is sent" in out


def test_weak_ideas_get_no_funding_search(make_orch, brief):
    st = make_orch(strong=False).start(brief)
    assert st.funding is None
