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
    provider: str = "ollama"
    openai_base_url: str = ""
    openai_api_key: str = ""


def _load_dotenv() -> None:
    """Read KEY=VALUE lines from .env at the repo root (never committed)."""
    p = ROOT / ".env"
    if not p.exists():
        return
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def load_settings() -> Settings:
    _load_dotenv()
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
        provider=os.getenv("LLM_PROVIDER", "ollama").lower(),
        openai_base_url=os.getenv("OPENAI_BASE_URL", "https://api.groq.com/openai/v1").rstrip("/"),
        openai_api_key=os.getenv("OPENAI_API_KEY", ""),
    )
