"""Phase 3, step 4: model-written core code runs only in the sandbox, against the acceptance criteria."""
from fastapi.testclient import TestClient

from app import sandbox
from app.decision_log import validate
from tests.test_build import _to_build


def test_sandbox_runs_pure_code_and_checks():
    r = sandbox.run("def add(a, b):\n    return a + b\n", ["assert add(2, 3) == 5", "assert add(1, 1) == 3"])
    assert not r.static_problems and r.load_error is None
    assert [x["passed"] for x in r.results] == [True, False] and not r.ok


def test_sandbox_refuses_files_network_processes_and_escapes():
    for bad in ("import os\nos.system('echo hi')", "import socket", "open('x.txt', 'w')", "import subprocess",
                "__import__('os')", "x = ().__class__.__bases__", "eval('1+1')", "from urllib import request",
                "getattr(int, 'real')"):
        r = sandbox.run(bad, ["assert True"])
        assert r.static_problems and not r.ok, bad
    assert sandbox.run("x = 1", ["import os"]).static_problems


def test_sandbox_stops_endless_loops():
    r = sandbox.run("def f():\n    while True:\n        pass\n", ["f()"])
    assert not r.ok and (r.timed_out or "limits" in (r.load_error or ""))


def test_codegen_writes_output_and_never_changes_the_run(make_orch, brief, settings):
    orch = make_orch()
    st = _to_build(orch, brief)
    stage, gates = st.stage, list(st.gates)
    st = orch.founder_generate_code(st.run_id)
    assert st.stage == stage and st.gates == gates
    assert st.code == {"passed": 1, "total": 1, "ok": True, "attempts": 1}
    out = (settings.outputs_dir / next(o for o in st.outputs if o.startswith("phase3_step4_code"))).read_text()
    assert "1/1 acceptance checks passed" in out and "def summarize" in out and "Nothing here is published" in out
    log = orch.log.read()
    assert any(e["action"] == "run_acceptance_checks" and e["outcome"] == "pass" for e in log)
    assert not validate(log)


def test_failing_code_gets_one_repair_with_the_failures(make_orch, brief, settings):
    from tests.conftest import GOOD_CODE
    orch = make_orch()
    broken = dict(GOOD_CODE, module_code="def summarize(notes, max_words=300):\n    return notes\n")
    orch.llm.code_drafts = [broken, GOOD_CODE]
    st = _to_build(orch, brief)
    st = orch.founder_generate_code(st.run_id)
    assert st.code["ok"] and st.code["attempts"] == 2
    acts = [e["action"] for e in orch.log.read() if e["agent"] == "coder"]
    assert acts == ["write_mvp_core_code", "repair_mvp_core_code"]


def test_unsafe_code_is_never_run_and_reported(make_orch, brief, settings):
    from tests.conftest import GOOD_CODE
    orch = make_orch()
    evil = dict(GOOD_CODE, module_code="import os\ndef summarize(n, max_words=300):\n    os.remove('x')\n")
    orch.llm.code_drafts = [evil, evil]
    st = _to_build(orch, brief)
    st = orch.founder_generate_code(st.run_id)
    assert not st.code["ok"] and st.code["passed"] == 0
    out = (settings.outputs_dir / next(o for o in st.outputs if o.startswith("phase3_step4_code"))).read_text()
    assert "import of 'os' is not allowed" in out and "should not rely on this code" in out


def test_web_button_runs_codegen(monkeypatch, make_orch, brief):
    import app.main as main
    orch = make_orch()
    monkeypatch.setattr(main, "orch", orch)
    monkeypatch.setattr(main, "settings", orch.settings)
    c = TestClient(main.app)
    st = _to_build(orch, brief)
    page = c.get(f"/runs/{st.run_id}").text
    assert "Generate and test the core code" in page
    orch.founder_generate_code(st.run_id)
    assert "1/1 acceptance checks passed" in c.get(f"/runs/{st.run_id}").text


def test_checks_that_import_the_module_by_an_invented_name_still_run():
    from app import sandbox
    code = "def double(x):\n    return 2 * x\n"
    checks = ["from my_core import double\nassert double(2) == 4",
              "from my_core import double, missing\nassert double(1) == 2",
              "import os\nassert double(0) == 0"]
    res = sandbox.run(code, checks)
    assert any("my_core" in p for p in res.static_problems)  # a name the module does not define still blocks
    assert any("'os'" in p for p in res.static_problems)
    res = sandbox.run(code, checks[:1])
    assert res.ok and res.passed == 1
