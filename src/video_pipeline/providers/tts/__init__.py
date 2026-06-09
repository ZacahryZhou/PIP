"""TTS provider registry."""

from video_pipeline.providers.tts.base import TTSProvider, TTSRequest, TTSResult, resolve_tts_provider

__all__ = ["TTSProvider", "TTSRequest", "TTSResult", "resolve_tts_provider"]
