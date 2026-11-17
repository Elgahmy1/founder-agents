"""Speech to text for the founder's interview recordings.

Uses the OpenAI-compatible `/audio/transcriptions` endpoint of the configured free tier with an open-weight
Whisper model (`TRANSCRIBE_MODEL`, default `whisper-large-v3-turbo`, served free on Groq). With a local Ollama
setup there is no speech model, so audio upload is unavailable (the founder pastes the transcript instead) and
the app says so. The recording is sent only to that endpoint, is not stored, and needs the interviewee's consent.
"""
from __future__ import annotations

import os

import httpx

MAX_BYTES = 25 * 1024 * 1024


class TranscriptionUnavailable(RuntimeError):
    pass


def available(settings) -> bool:
    return getattr(settings, "provider", "") == "openai" and bool(getattr(settings, "openai_api_key", ""))


def model_name() -> str:
    return os.getenv("TRANSCRIBE_MODEL", "whisper-large-v3-turbo")


def transcribe(settings, audio: bytes, filename: str) -> str:
    if not available(settings):
        raise TranscriptionUnavailable("No speech model is configured (local Ollama has none): paste the transcript instead.")
    if not audio:
        raise ValueError("the recording is empty")
    if len(audio) > MAX_BYTES:
        raise ValueError("the recording is larger than 25 MB: split it or paste the transcript")
    r = httpx.post(f"{settings.openai_base_url}/audio/transcriptions",
                   headers={"Authorization": f"Bearer {settings.openai_api_key}"},
                   files={"file": (filename or "interview.m4a", audio)},
                   data={"model": model_name(), "response_format": "json", "temperature": "0"},
                   timeout=settings.llm_timeout_s)
    if r.status_code >= 400:
        raise TranscriptionUnavailable(f"transcription failed (HTTP {r.status_code})")
    text = (r.json().get("text") or "").strip()
    if not text:
        raise ValueError("no speech was found in the recording")
    return text
