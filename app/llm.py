"""Client for a local open-weight model served by Ollama.

Every call returns parsed JSON that matches a pydantic schema, plus token
counts so the run can report its cost. Local models cost $0.
"""
from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from typing import Protocol, TypeVar

import httpx
from pydantic import BaseModel, ValidationError

from app.config import Settings

T = TypeVar("T", bound=BaseModel)


class LLMError(RuntimeError):
    pass


class RateLimited(LLMError):
    """The free tier kept answering HTTP 429 for longer than the allowed wait."""


@dataclass
class Usage:
    prompt_tokens: int = 0
    completion_tokens: int = 0
    calls: int = 0
    cost_usd: float = 0.0  # local open-weight model: no per-token charge

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens


class LLM(Protocol):
    model: str
    usage: Usage

    def structured(self, system: str, user: str, schema: type[T]) -> T: ...


@dataclass
class OllamaLLM:
    settings: Settings
    usage: Usage = field(default_factory=Usage)

    @property
    def model(self) -> str:
        return self.settings.model

    def health(self) -> bool:
        try:
            r = httpx.get(f"{self.settings.ollama_url}/api/tags", timeout=5)
            names = {m["name"] for m in r.json().get("models", [])}
            return self.model in names or f"{self.model}:latest" in names
        except Exception:
            return False

    def structured(self, system: str, user: str, schema: type[T]) -> T:
        last_err: Exception | None = None
        messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
        for _ in range(2):
            try:
                r = httpx.post(
                    f"{self.settings.ollama_url}/api/chat",
                    json={
                        "model": self.model,
                        "messages": messages,
                        "format": schema.model_json_schema(),
                        "stream": False,
                        "think": False,
                        "options": {"temperature": 0.3, "num_ctx": 16384},
                    },
                    timeout=self.settings.llm_timeout_s,
                )
                r.raise_for_status()
            except httpx.HTTPError as e:
                raise LLMError(
                    f"Ollama at {self.settings.ollama_url} did not answer for model "
                    f"'{self.model}': {e}"
                ) from e
            data = r.json()
            self.usage.calls += 1
            self.usage.prompt_tokens += int(data.get("prompt_eval_count", 0))
            self.usage.completion_tokens += int(data.get("eval_count", 0))
            content = data.get("message", {}).get("content", "")
            try:
                return schema.model_validate(json.loads(_extract_json(content)))
            except (json.JSONDecodeError, ValidationError) as e:
                last_err = e
                messages += [
                    {"role": "assistant", "content": content},
                    {"role": "user", "content": f"That was not valid JSON for the schema: {e}. Reply with JSON only."},
                ]
        raise LLMError(f"model returned invalid JSON three times: {last_err}")


def _extract_json(text: str) -> str:
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.S).strip()
    m = re.search(r"\{.*\}", text, flags=re.S)
    return m.group(0) if m else text


@dataclass
class OpenAICompatLLM:
    """Any OpenAI-compatible endpoint serving an open-weight model on a free
    tier (for example Groq's free tier with openai/gpt-oss-120b). Used when
    the laptop has no GPU. Cost is recorded as $0: free tier, no billing."""
    settings: Settings
    usage: Usage = field(default_factory=Usage)

    @property
    def model(self) -> str:
        return self.settings.model

    def health(self) -> bool:
        return bool(self.settings.openai_api_key)

    def _post(self, messages: list[dict]) -> httpx.Response:
        """POST with backoff on free-tier rate limits (HTTP 429), up to max_rate_wait_s in total."""
        waited = 0.0
        for attempt in range(8):
            r = httpx.post(
                f"{self.settings.openai_base_url}/chat/completions",
                headers={"Authorization": f"Bearer {self.settings.openai_api_key}"},
                json={"model": self.model, "messages": messages, "temperature": 0.3,
                      "response_format": {"type": "json_object"}},
                timeout=self.settings.llm_timeout_s,
            )
            if r.status_code != 429:
                break
            wait = (_retry_after(r) or min(60, 5 * (attempt + 1))) + 0.5
            if waited + wait > self.settings.max_rate_wait_s:
                raise RateLimited(f"{self.settings.openai_base_url} rate-limited '{self.model}' "
                                  f"for longer than {self.settings.max_rate_wait_s:g} s")
            time.sleep(wait)
            waited += wait
        r.raise_for_status()
        return r

    def structured(self, system: str, user: str, schema: type[T]) -> T:
        sys_msg = (f"{system}\n\nReply with a single JSON object that matches this JSON schema:\n"
                   f"{json.dumps(schema.model_json_schema())}")
        messages = [{"role": "system", "content": sys_msg}, {"role": "user", "content": user}]
        last_err: Exception | None = None
        for attempt in range(3):
            try:
                r = self._post(messages)
            except httpx.HTTPError as e:
                detail = getattr(getattr(e, "response", None), "text", "")[:300]
                # The free tier sometimes rejects its own JSON-mode output for long answers (for example generated code):
                # HTTP 400 "json_validate_failed". That is a transient generation failure, so ask again (twice at most).
                if "json_validate_failed" in detail and attempt < 2:
                    last_err = e
                    messages = messages[:2] + [{"role": "user", "content": "Your previous reply was not valid JSON. Reply again "
                                                "with one valid JSON object only; escape newlines and quotes inside strings."}]
                    continue
                raise LLMError(f"{self.settings.openai_base_url} failed for '{self.model}': {e} {detail}") from e
            data = r.json()
            u = data.get("usage", {})
            self.usage.calls += 1
            self.usage.prompt_tokens += int(u.get("prompt_tokens", 0))
            self.usage.completion_tokens += int(u.get("completion_tokens", 0))
            content = data["choices"][0]["message"].get("content") or ""
            try:
                return schema.model_validate(json.loads(_extract_json(content)))
            except (json.JSONDecodeError, ValidationError) as e:
                last_err = e
                messages += [{"role": "assistant", "content": content},
                             {"role": "user", "content": f"Invalid for the schema: {e}. Reply with corrected JSON only."}]
        raise LLMError(f"model returned invalid JSON three times: {last_err}")


@dataclass
class FallbackLLM:
    """Free-tier endpoint first; if it stays rate-limited or fails, the same call goes
    to the local open-weight model, so a run never stalls on a daily cap. The decision
    log records whichever model actually answered."""
    primary: OpenAICompatLLM
    fallback: OllamaLLM
    usage: Usage = field(default_factory=Usage)
    last_model: str = ""
    fallbacks: int = 0

    def __post_init__(self) -> None:
        self.primary.usage = self.fallback.usage = self.usage
        self.last_model = self.primary.model

    @property
    def model(self) -> str:
        return self.last_model

    def health(self) -> bool:
        return self.primary.health() or self.fallback.health()

    def structured(self, system: str, user: str, schema: type[T]) -> T:
        try:
            out = self.primary.structured(system, user, schema)
            self.last_model = self.primary.model
            return out
        except LLMError as first:
            if not self.fallback.health():
                raise
            self.fallbacks += 1
            try:
                out = self.fallback.structured(system, user, schema)
            except LLMError as second:
                raise LLMError(f"{first}; local fallback also failed: {second}") from second
            self.last_model = self.fallback.model
            return out


def make_llm(settings: Settings):
    if settings.provider != "openai":
        return OllamaLLM(settings)
    primary = OpenAICompatLLM(settings)
    if not settings.fallback_model:
        return primary
    from dataclasses import replace
    return FallbackLLM(primary, OllamaLLM(replace(settings, model=settings.fallback_model)))


def _retry_after(r: httpx.Response) -> float | None:
    h = r.headers.get("retry-after")
    if h:
        try:
            return float(h)
        except ValueError:
            pass
    m = re.search(r"try again in ([\d.]+)(ms|s)", r.text)
    if m:
        v = float(m.group(1))
        return v / 1000 if m.group(2) == "ms" else v
    return None
