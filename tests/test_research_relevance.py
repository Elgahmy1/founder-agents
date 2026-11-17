from app.research import Researcher, relevant


def test_results_matching_only_one_word_of_the_query_are_dropped():
    q = "Egyptian freelancers Upwork English proposals"
    assert not relevant(q, "Casualties of the Gaza war", "Egypt and Israel ... ceasefire talks")
    assert relevant(q, "How I write Upwork proposals", "tips for freelancers who write English proposals")
    assert relevant("notes", "Note-taking", "notes")  # short queries need one match


def test_researcher_records_what_it_dropped(monkeypatch):
    def fn(query, limit=4):
        return [{"url": "https://w.example/gaza", "title": "Gaza war", "snippet": "Egypt", "origin": "wikipedia"},
                {"url": "https://w.example/up", "title": "Upwork proposals for freelancers", "snippet": "", "origin": "web"}]
    fn.__name__ = "x_search"
    monkeypatch.setattr(Researcher, "SOURCES", (fn,))
    r = Researcher(True)
    docs = r.gather(["Egyptian freelancers Upwork proposals"])
    assert [d.url for d in docs] == ["https://w.example/up"] and r.dropped == ["https://w.example/gaza"]
