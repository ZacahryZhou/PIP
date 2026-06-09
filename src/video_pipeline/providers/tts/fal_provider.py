"""fal.ai TTS provider."""

from __future__ import annotations

from video_pipeline.config import Settings
from video_pipeline.media.ffmpeg import convert_audio_to_wav, probe_audio_duration
from video_pipeline.providers.fal_audio import generate_fal_tts
from video_pipeline.providers.tts.base import TTSProvider, TTSRequest, TTSResult


class FalTTSProvider:
    def __init__(self, *, settings: Settings) -> None:
        self.settings = settings

    def synthesize(self, request: TTSRequest) -> TTSResult:
        raw_path = request.output_path.with_suffix(request.output_path.suffix + ".raw")
        result = generate_fal_tts(raw_path, settings=self.settings, text=request.text)
        convert_audio_to_wav(raw_path, request.output_path)
        duration = probe_audio_duration(request.output_path)
        if duration <= 0:
            duration = max(0.2, request.estimated_duration_sec)
        return TTSResult(
            output_path=request.output_path,
            duration_sec=duration,
            provider="fal",
            provider_request_id=result.provider_request_id,
        )
