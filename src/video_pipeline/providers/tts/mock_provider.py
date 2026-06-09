"""Mock TTS provider for tests."""

from __future__ import annotations

from video_pipeline.providers.mock_audio import generate_mock_tts_segment
from video_pipeline.providers.tts.base import TTSProvider, TTSRequest, TTSResult


class MockTTSProvider:
    def synthesize(self, request: TTSRequest) -> TTSResult:
        generate_mock_tts_segment(
            request.output_path,
            duration_sec=max(0.2, request.estimated_duration_sec),
        )
        return TTSResult(
            output_path=request.output_path,
            duration_sec=max(0.2, request.estimated_duration_sec),
            provider="mock",
        )
