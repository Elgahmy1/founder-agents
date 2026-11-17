from app.evidence import Claim, Ledger


def test_repeated_claim_with_same_source_counts_once():
    led = Ledger()
    c = Claim("Freelancers often do not know how to scope a proposal.", "SOURCED", ["https://example.org/q/1"])
    for _ in range(4):
        led.add([Claim(c.text, c.status, list(c.sources))])
    led.add([Claim("freelancers often do NOT know how to scope a proposal", "SOURCED", ["https://example.org/q/1"])])
    assert len(led.sourced) == 1 and len(led.claims) == 1


def test_same_text_with_a_different_source_is_separate_evidence():
    led = Ledger()
    led.add([Claim("Proposals take hours.", "SOURCED", ["https://a.example/1"]),
             Claim("Proposals take hours.", "SOURCED", ["https://b.example/2"]),
             Claim("Proposals take hours.", "ASSUMPTION", [], "no source")])
    assert len(led.sourced) == 2 and len(led.assumptions) == 1
