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
        raise LLMError(f"model returned invalid JSON twice: {last_err}")


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
        """POST with backoff on free-tier rate limits (HTTP 429)."""
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
            wait = _retry_after(r) or min(60, 5 * (attempt + 1))
            time.sleep(wait + 0.5)
        r.raise_for_status()
        return r

    def structured(self, system: str, user: str, schema: type[T]) -> T:
        sys_msg = (f"{system}\n\nReply with a single JSON object that matches this JSON schema:\n"
                   f"{json.dumps(schema.model_json_schema())}")
        messages = [{"role": "system", "content": sys_msg}, {"role": "user", "content": user}]
        last_err: Exception | None = None
        for _ in range(2):
            try:
                r = self._post(messages)
            except httpx.HTTPError as e:
                detail = getattr(getattr(e, "response", None), "text", "")[:300]
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
        raise LLMError(f"model returned invalid JSON twice: {last_err}")


def make_llm(settings: Settings):
    return OpenAICompatLLM(settings) if settings.provider == "openai" else OllamaLLM(settings)


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
