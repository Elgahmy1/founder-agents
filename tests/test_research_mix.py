from app import research
from app.research import Researcher


def _fake(origin, n):
    def fn(query, limit=4):
        return [{"url": f"https://{origin}.example/{query}/{i}", "title": f"{origin} {i}",
                 "snippet": "text", "origin": origin} for i in range(n)]
    fn.__name__ = f"{origin}_search"
    return fn


def test_sources_are_interleaved_so_one_source_cannot_fill_the_budget(monkeypatch):
    monkeypatch.setattr(Researcher, "SOURCES", (_fake("hn", 4), _fake("se", 4), _fake("wiki", 2), _fake("web", 4)))
    docs = Researcher(True, max_sources=8).gather(["q1", "q2"], founder_urls=["https://founder.example/a"])
    assert docs[0].origin == "founder"
    assert {d.origin for d in docs} == {"founder", "hn", "se", "wiki", "web"}
    assert len(docs) == 8 and [d.id for d in docs] == [f"S{i}" for i in range(1, 9)]


def test_failing_source_is_recorded_and_others_still_used(monkeypatch):
    def broken(query, limit=4):
        raise RuntimeError("blocked")
    broken.__name__ = "broken_search"
    monkeypatch.setattr(Researcher, "SOURCES", (broken, _fake("wiki", 2)))
    r = Researcher(True, max_sources=8)
    docs = r.gather(["q"])
    assert [d.origin for d in docs] == ["wiki", "wiki"]
    assert r.errors == ["broken_search('q'): RuntimeError"]


def test_wikipedia_url_is_built_from_title(monkeypatch):
    class R:
        def raise_for_status(self): pass
        def json(self): return {"query": {"search": [{"title": "Note-taking", "snippet": "<b>Notes</b>"}]}}
    monkeypatch.setattr(research.httpx, "get", lambda *a, **k: R())
    out = research.wikipedia_search("notes")
    assert out == [{"url": "https://en.wikipedia.org/wiki/Note-taking", "title": "Note-taking",
                    "snippet": "<b>Notes</b>", "origin": "wikipedia"}]
