"""TTS provider interface — fal (V2 default) or ElevenLabs direct."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from video_pipeline.config import Settings


@dataclass(frozen=True)
class TTSRequest:
    text: str
    voice: str
    language: str
    output_path: Path
    estimated_duration_sec: float


@dataclass(frozen=True)
class TTSResult:
    output_path: Path
    duration_sec: float
    provider: str
    provider_request_id: str | None = None


class TTSProvider(Protocol):
    def synthesize(self, request: TTSRequest) -> TTSResult:
        """Generate speech audio at request.output_path (wav preferred)."""


def resolve_tts_provider(*, settings: Settings, mock: bool) -> TTSProvider:
    if mock:
        from video_pipeline.providers.tts.mock_provider import MockTTSProvider

        return MockTTSProvider()

    provider_name = (settings.pip_tts_provider or "fal").strip().lower()
    if provider_name == "fal":
        from video_pipeline.providers.tts.fal_provider import FalTTSProvider

        return FalTTSProvider(settings=settings)
    if provider_name == "elevenlabs":
        from video_pipeline.providers.tts.elevenlabs_provider import ElevenLabsTTSProvider

        return ElevenLabsTTSProvider(settings=settings)

    raise ValueError(
        f"Unknown PIP_TTS_PROVIDER: {provider_name!r} — supported: fal, elevenlabs"
    )
