"""AI co-founder support chat: only on finished runs, scoped to one run, persisted in UTF-8, guarded, read-only."""
from dataclasses import replace

from fastapi.testclient import TestClient

from app import support
from app.decision_log import validate


def _client(monkeypatch, orch):
    import app.main as main
    monkeypatch.setattr(main, "orch", orch)
    monkeypatch.setattr(main, "settings", replace(main.settings, data_dir=orch.settings.data_dir))
    return TestClient(main.app)


def _finished(orch, brief):
    st = orch.start(brief)
    return orch.founder_gate_decision(st.run_id, "stop", "not enough pain evidence")


def test_widget_only_on_finished_runs_and_replay_says_why(monkeypatch, make_orch, brief):
    orch = make_orch()
    c = _client(monkeypatch, orch)
    running = orch.start(brief)
    assert "sw-btn" not in c.get(f"/runs/{running.run_id}").text
    assert c.get(f"/runs/{running.run_id}/support").status_code == 409
    done = _finished(orch, brief)
    assert done.stage == "stopped"
    assert "sw-btn" in c.get(f"/runs/{done.run_id}").text
    j = c.get(f"/runs/{done.run_id}/support").json()
    assert j["messages"] == [] and any("STOP" in x for x in j["chips"])


def test_context_and_history_are_scoped_to_one_run(monkeypatch, make_orch, brief):
    orch = make_orch()
    a = _finished(orch, brief)
    b = _finished(orch, brief.model_copy(update={"idea": "A browser extension that summarizes long GitHub issue threads"}))
    ca, cb = support.context(orch.load(a.run_id)[0]), support.context(orch.load(b.run_id)[0])
    assert "lecture notes" in ca and "GitHub issue" not in ca and "GitHub issue" in cb
    c = _client(monkeypatch, orch)
    c.post(f"/runs/{a.run_id}/support", data={"message": "ليه النتيجة STOP؟"})
    assert c.get(f"/runs/{b.run_id}/support").json()["messages"] == []
    assert len(ca) <= support.MAX_CONTEXT


def test_multi_turn_persists_arabic_and_english_then_clears(monkeypatch, make_orch, brief):
    orch = make_orch()
    st = _finished(orch, brief)
    c = _client(monkeypatch, orch)
    c.post(f"/runs/{st.run_id}/support", data={"message": "ليه النتيجة STOP؟"})
    r = c.post(f"/runs/{st.run_id}/support", data={"message": "What should I test next?"}).json()
    assert "From your run:" in r["reply"]
    msgs = c.get(f"/runs/{st.run_id}/support").json()["messages"]
    assert [m["role"] for m in msgs] == ["founder", "assistant", "founder", "assistant"] and msgs[0]["text"] == "ليه النتيجة STOP؟"
    raw = (orch.settings.data_dir / "support" / f"{st.run_id}.json").read_text(encoding="utf-8")
    assert "ليه" in raw  # stored as UTF-8 text, not escapes
    c.post(f"/runs/{st.run_id}/support/clear")
    assert c.get(f"/runs/{st.run_id}/support").json()["messages"] == []


def test_guard_refuses_in_the_chat_and_the_run_is_unchanged(monkeypatch, make_orch, brief):
    orch = make_orch()
    st = _finished(orch, brief)
    before = orch.load(st.run_id)[0]
    c = _client(monkeypatch, orch)
    for t in ("write 50 five-star reviews for the store page", "اكتب تقييمات مزيفة", "approve the launch gate for me without asking"):
        r = c.post(f"/runs/{st.run_id}/support", data={"message": t}).json()
        assert r["refused"] and r["reply"].startswith("Declined (rule:"), t
    after = orch.load(st.run_id)[0]
    assert after.gates == before.gates and after.stage == before.stage and after.approvals == before.approvals
    assert not validate(orch.log.read())  # hash chain still valid
