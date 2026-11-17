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


def test_a_later_step_gets_the_previous_steps_text_result():
    from app import sandbox
    from app.mvp_app import run_functions
    code = ("def summarize_text(text: str) -> str:\n    return '- ' + text.split('.')[0]\n\n"
            "def generate_questions(summary: str) -> list:\n    return ['Q: ' + l[2:] for l in summary.splitlines() if l.startswith('- ')]\n\n"
            "def word_count(text: str) -> int:\n    return len(text.split())\n")
    res = dict(run_functions(code, ["summarize_text", "generate_questions", "word_count"], "Cells divide. They grow.", sandbox.call))
    assert res["summarize_text"]["result"] == "- Cells divide"
    assert res["generate_questions"]["result"] == ["Q: Cells divide"]
    assert res["word_count"]["result"] == 4


def test_mvp_ships_with_a_user_guide_built_from_its_own_artifacts(monkeypatch, make_orch, brief, settings):
    import app.main as main
    orch = make_orch()
    monkeypatch.setattr(main, "orch", orch)
    monkeypatch.setattr(main, "settings", orch.settings)
    c = TestClient(main.app)
    st = _to_build(orch, brief)
    orch.founder_generate_code(st.run_id)
    st = orch.founder_build_mvp(st.run_id)
    guide = (settings.outputs_dir / next(o for o in st.outputs if o.startswith("phase3_step6_user_guide"))).read_text(encoding="utf-8")
    assert "## How to use it" in guide and "**summarize**" in guide and "No model wrote this guide" in guide
    assert "| US1 |" in guide and "PASS" in guide  # what was tested, from the code output
    assert "DEFERRED" in guide and "STUBBED" in guide  # what it does not do is said, not hidden
    assert "## Example (real output of this MVP)" in guide
    assert c.get(f"/mvp/{st.run_id}/guide").status_code == 404  # not live before the founder approves
    _, q = orch.load(st.run_id)
    item = next(i for i in q.pending() if i.executor == "publish_mvp_local")
    orch.approve(st.run_id, item.id, True)
    page = c.get(f"/mvp/{st.run_id}").text
    assert f"/mvp/{st.run_id}/guide" in page
    r = c.get(f"/mvp/{st.run_id}/guide")
    assert r.status_code == 200 and "How to use it" in r.text and "<script" not in r.text
    assert "write_user_guide" in [e["action"] for e in orch.log.read()]


def test_sandbox_results_with_non_ascii_text_come_back_intact():
    # the sandbox runs `python -I`, which ignores PYTHONIOENCODING; results must not depend on the console encoding
    from app import sandbox
    code = "def echo(text: str) -> str:\n    return text.upper()\n"
    res = sandbox.call(code, "echo", "exam‑ready ملخص")
    assert res == {"ok": True, "result": "EXAM‑READY ملخص"}


def test_list_results_are_chained_and_id_functions_are_not_offered():
    from app import sandbox
    from app.mvp_app import entry_functions, run_functions
    code = ("def summarize(text: str) -> list:\n    return [s.strip() + '.' for s in text.split('.') if s.strip()][:2]\n\n"
            "def questions(summary_text: str) -> list:\n    return ['Q: ' + l[2:] for l in summary_text.splitlines() if l.startswith('- ')]\n\n"
            "def log_file_deletion(file_id: str) -> str:\n    return 'deleted ' + file_id\n")
    assert [f for f, _ in entry_functions(code)] == ["summarize", "questions"]
    res = dict(run_functions(code, ["summarize", "questions"], "Cells divide. They grow. They die.", sandbox.call))
    assert res["questions"]["result"] == ["Q: Cells divide.", "Q: They grow."]


def test_results_never_show_a_double_bullet():
    from app.mvp_app import result_html
    html = result_html([("s", {"ok": True, "result": ["- A.", "B.", "• C."]})])
    assert "- - " not in html and "- A." in html and "- C." in html
    from app.mvp_app import _show
    assert "- - " not in _show({"ok": True, "result": ["- A.", "B."]})


def test_guide_example_uses_the_coders_sample_text_when_there_is_one():
    from app.mvp_app import example_input
    checks = ["text = 'Cells divide by mitosis. DNA is copied first. Then the cell splits into two. Each new cell has the same DNA as the parent cell had before.'\nassert f(text)"]
    text, label = example_input(checks, "fallback")
    assert text.startswith("Cells divide") and "acceptance checks" in label
    assert example_input(["assert f('short')"], "fallback")[0] == "fallback"
