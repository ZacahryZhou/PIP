"""fal.ai TTS and BGM providers."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from video_pipeline.config import Settings
from video_pipeline.providers.fal_utils import (
    download_url,
    first_url,
    request_id_from,
    require_fal_client,
)


@dataclass(frozen=True)
class FalAudioResult:
    output_path: Path
    provider_request_id: str | None = None
    endpoint: str | None = None


def generate_fal_tts(
    output_path: Path,
    *,
    settings: Settings,
    text: str,
) -> FalAudioResult:
    fal_client = require_fal_client(settings.fal_key)
    endpoint = settings.fal_tts_model
    arguments = {
        "text": text,
        "voice": settings.fal_tts_voice,
        "language": settings.fal_tts_language,
    }
    result = fal_client.subscribe(endpoint, arguments=arguments, with_logs=True)
    audio_url = first_url(result, preferred_exts=(".mp3", ".wav", ".m4a", ".aac"))
    download_url(audio_url, output_path)
    return FalAudioResult(
        output_path=output_path,
        provider_request_id=request_id_from(result),
        endpoint=endpoint,
    )


def build_bgm_prompt(*, music_mood: str, music_bpm: int, instrumental: bool) -> str:
    if instrumental:
        return (
            f"Instrumental cinematic underscore, {music_mood}, approximately {music_bpm} BPM, "
            "no vocals, no lyrics, suitable for short film background"
        )
    return f"Cinematic background music, {music_mood}, approximately {music_bpm} BPM"


def generate_fal_bgm(
    output_path: Path,
    *,
    settings: Settings,
    music_mood: str,
    music_bpm: int,
    instrumental: bool = True,
) -> FalAudioResult:
    fal_client = require_fal_client(settings.fal_key)
    endpoint = settings.fal_bgm_model
    arguments = {
        "prompt": build_bgm_prompt(
            music_mood=music_mood,
            music_bpm=music_bpm,
            instrumental=instrumental,
        ),
        "is_instrumental": instrumental,
        "lyrics": "",
    }
    result = fal_client.subscribe(endpoint, arguments=arguments, with_logs=True)
    audio_url = first_url(result, preferred_exts=(".mp3", ".wav", ".m4a", ".aac"))
    download_url(audio_url, output_path)
    return FalAudioResult(
        output_path=output_path,
        provider_request_id=request_id_from(result),
        endpoint=endpoint,
    )
