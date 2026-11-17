from dataclasses import replace

from pydantic import BaseModel

from app import llm as llm_mod
from app.config import load_settings
from app.llm import FallbackLLM, LLMError, OllamaLLM, OpenAICompatLLM, RateLimited, make_llm


class Out(BaseModel):
    x: int


def _settings(**kw):
    return replace(load_settings(), provider="openai", model="openai/gpt-oss-120b",
                   openai_api_key="test-key", **kw)


class Resp:
    def __init__(self, status, body=None, headers=None):
        self.status_code, self._body, self.headers, self.text = status, body or {}, headers or {}, ""
    def json(self): return self._body
    def raise_for_status(self): pass


def test_rate_limit_wait_is_capped(monkeypatch):
    slept = []
    monkeypatch.setattr(llm_mod.time, "sleep", slept.append)
    monkeypatch.setattr(llm_mod.httpx, "post", lambda *a, **k: Resp(429, headers={"retry-after": "40"}))
    p = OpenAICompatLLM(_settings(max_rate_wait_s=90))
    try:
        p.structured("s", "u", Out)
        raise AssertionError("expected RateLimited")
    except RateLimited:
        pass
    assert sum(slept) <= 90


def test_fallback_answers_and_log_model_is_the_one_that_answered(monkeypatch):
    s = _settings(fallback_model="qwen3:8b")
    f = make_llm(s)
    assert isinstance(f, FallbackLLM) and f.model == "openai/gpt-oss-120b"

    def limited(*a, **k): raise RateLimited("429 for too long")
    monkeypatch.setattr(OpenAICompatLLM, "structured", limited)
    monkeypatch.setattr(OllamaLLM, "health", lambda self: True)
    monkeypatch.setattr(OllamaLLM, "structured", lambda self, *a: Out(x=1))
    assert f.structured("s", "u", Out).x == 1
    assert f.model == "qwen3:8b" and f.fallbacks == 1


def test_no_fallback_when_local_model_missing(monkeypatch):
    f = make_llm(_settings(fallback_model="qwen3:8b"))
    def limited(*a, **k): raise RateLimited("429")
    monkeypatch.setattr(OpenAICompatLLM, "structured", limited)
    monkeypatch.setattr(OllamaLLM, "health", lambda self: False)
    try:
        f.structured("s", "u", Out)
        raise AssertionError("expected LLMError")
    except LLMError as e:
        assert "429" in str(e)


def test_without_fallback_model_primary_is_used_directly():
    assert isinstance(make_llm(_settings()), OpenAICompatLLM)
    assert isinstance(make_llm(replace(load_settings(), provider="ollama")), OllamaLLM)
