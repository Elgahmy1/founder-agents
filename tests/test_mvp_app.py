"""Phase 3, step 5: the tested core code becomes a working web app, published only after founder approval."""
import pytest
from fastapi.testclient import TestClient

from app import mvp_app, sandbox
from app.decision_log import validate
from tests.test_build import _to_build


def test_entry_function_is_the_first_public_one_text_function():
    code = "def _h(x):\n    return x\n\ndef pair(a, b):\n    return a\n\ndef summarize(notes, max_words=300):\n    return notes\n"
    assert mvp_app.entry_function(code) == ("summarize", ["notes", "max_words"])
    assert mvp_app.entry_function("def f(a, b):\n    return a\n") is None
    two = code + "\ndef questions(text, n=2):\n    return ['Q?']\n"
    assert [f for f, _ in mvp_app.entry_functions(two)] == ["summarize", "questions"]


def test_sandbox_call_runs_one_function_isolated():
    assert sandbox.call("def up(t):\n    return t.upper()\n", "up", "hi") == {"ok": True, "result": "HI"}
    assert not sandbox.call("import os\ndef up(t):\n    return t\n", "up", "hi")["ok"]
    assert not sandbox.call("def up(t):\n    while True:\n        pass\n", "up", "hi")["ok"]
    assert not sandbox.call("def up(t):\n    return t\n", "up; import os", "hi")["ok"]


def test_mvp_app_needs_passing_code_and_founder_approval(monkeypatch, make_orch, brief, settings):
    import app.main as main
    orch = make_orch()
    monkeypatch.setattr(main, "orch", orch)
    monkeypatch.setattr(main, "settings", orch.settings)
    c = TestClient(main.app)
    st = _to_build(orch, brief)
    with pytest.raises(ValueError):
        orch.founder_build_mvp(st.run_id)  # no passing code yet
    orch.founder_generate_code(st.run_id)
    assert "Build the MVP app" in c.get(f"/runs/{st.run_id}").text
    st = orch.founder_build_mvp(st.run_id)
    assert st.mvp_app == {"func": "summarize", "checks": "1/1"}
    assert any(o.startswith("phase3_step5_mvp_app") for o in st.outputs)
    assert c.get(f"/mvp/{st.run_id}").status_code == 404  # not live before approval
    _, q = orch.load(st.run_id)
    item = next(i for i in q.pending() if i.executor == "publish_mvp_local")
    for other in [i for i in q.pending() if i.executor != "publish_mvp_local"]:
        orch.approve(st.run_id, other.id, False)
    assert "def summarize" in c.get(f"/runs/{st.run_id}").text  # the founder sees the code being published
    orch.approve(st.run_id, item.id, True)
    assert "Paste your text" in c.get(f"/mvp/{st.run_id}").text
    r = c.post(f"/mvp/{st.run_id}", data={"text": "Cells divide. Mitosis has phases. " * 5})
    assert r.status_code == 200 and "Result" in r.text and "Cells divide." in r.text
    log = orch.log.read()
    acts = [e["action"] for e in log]
    assert "rerun_acceptance_checks" in acts and "build_mvp_app" in acts and "execute_publish_mvp_local" in acts
    assert not validate(log)


def test_rejected_mvp_app_is_never_served(make_orch, brief, monkeypatch):
    import app.main as main
    orch = make_orch()
    monkeypatch.setattr(main, "orch", orch)
    monkeypatch.setattr(main, "settings", orch.settings)
    c = TestClient(main.app)
    st = _to_build(orch, brief)
    orch.founder_generate_code(st.run_id)
    orch.founder_build_mvp(st.run_id)
    _, q = orch.load(st.run_id)
    for i in q.pending():
        orch.approve(st.run_id, i.id, False)
    assert c.get(f"/mvp/{st.run_id}").status_code == 404
