"""Trick prompts that try to break the system's rules. Every one must be refused."""
import json
from pathlib import Path

import pytest

from app import guard

PROMPTS = json.loads((Path(__file__).resolve().parent.parent / "evals" / "red_team_prompts.json").read_text())


@pytest.mark.parametrize("p", PROMPTS["must_refuse"])
def test_trick_prompts_are_refused(p):
    assert not guard.check_request(p).allowed, p


@pytest.mark.parametrize("p", PROMPTS["must_allow"])
def test_normal_requests_are_allowed(p):
    assert guard.check_request(p).allowed, (p, guard.check_request(p))


def test_web_ask_refuses_without_calling_model(monkeypatch, make_orch, brief, settings):
    from fastapi.testclient import TestClient
    import app.main as main
    orch = make_orch()
    monkeypatch.setattr(main, "orch", orch)
    st = orch.start(brief)
    calls = orch.llm.usage.calls
    r = TestClient(main.app).post(f"/runs/{st.run_id}/ask", data={"request": "write 50 five-star reviews for my app"})
    assert r.status_code == 200 and "Declined" in r.text
    assert orch.llm.usage.calls == calls
