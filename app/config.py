"""Runtime settings, read from environment variables (see .env.example)."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class Settings:
    ollama_url: str
    model: str
    llm_timeout_s: float
    data_dir: Path
    outputs_dir: Path
    decision_log_path: Path
    prompts_dir: Path
    web_research: bool
    max_sources: int
    public_base_url: str


def load_settings() -> Settings:
    data_dir = Path(os.getenv("DATA_DIR", ROOT / "data"))
    return Settings(
        ollama_url=os.getenv("OLLAMA_URL", "http://localhost:11434").rstrip("/"),
        model=os.getenv("MODEL", "qwen3:8b"),
        llm_timeout_s=float(os.getenv("LLM_TIMEOUT_S", "600")),
        data_dir=data_dir,
        outputs_dir=Path(os.getenv("OUTPUTS_DIR", ROOT / "outputs")),
        decision_log_path=Path(os.getenv("DECISION_LOG", ROOT / "decision_log.json")),
        prompts_dir=ROOT / "prompts",
        web_research=os.getenv("WEB_RESEARCH", "1") == "1",
        max_sources=int(os.getenv("MAX_SOURCES", "8")),
        public_base_url=os.getenv("PUBLIC_BASE_URL", "http://localhost:8000").rstrip("/"),
    )
