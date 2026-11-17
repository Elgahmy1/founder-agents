"""Client for a local open-weight model served by Ollama.

Every call returns parsed JSON that matches a pydantic schema, plus token
counts so the run can report its cost. Local models cost $0.
"""
from __future__ import annotations

import json
import re
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
