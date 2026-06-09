"""ElevenLabs TTS provider (V2 default)."""

from __future__ import annotations

import json
import urllib.error
import urllib.request

from video_pipeline.config import Settings
from video_pipeline.media.ffmpeg import convert_audio_to_wav, probe_audio_duration
from video_pipeline.providers.tts.base import TTSProvider, TTSRequest, TTSResult


class ElevenLabsTTSProvider:
    def __init__(self, *, settings: Settings) -> None:
        self.settings = settings

    def synthesize(self, request: TTSRequest) -> TTSResult:
        if not self.settings.elevenlabs_api_key:
            raise ValueError("ELEVENLABS_API_KEY is required when PIP_TTS_PROVIDER=elevenlabs")

        voice_id = request.voice or self.settings.elevenlabs_voice_id
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
        payload = {
            "text": request.text,
            "model_id": self.settings.elevenlabs_model_id,
            "voice_settings": {"stability": 0.5, "similarity_boost": 0.75},
        }
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Accept": "audio/mpeg",
                "Content-Type": "application/json",
                "xi-api-key": self.settings.elevenlabs_api_key,
            },
            method="POST",
        )
        raw_path = request.output_path.with_suffix(".mp3")
        try:
            with urllib.request.urlopen(req, timeout=120) as response:
                raw_path.write_bytes(response.read())
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"ElevenLabs TTS failed ({exc.code}): {body}") from exc

        convert_audio_to_wav(raw_path, request.output_path)
        duration = probe_audio_duration(request.output_path)
        if duration <= 0:
            duration = max(0.2, request.estimated_duration_sec)
        return TTSResult(
            output_path=request.output_path,
            duration_sec=duration,
            provider="elevenlabs",
        )
