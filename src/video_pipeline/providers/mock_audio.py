"""Mock audio providers for pipeline tests."""

from __future__ import annotations

from pathlib import Path

from video_pipeline.media.ffmpeg import generate_silent_wav, generate_tone_wav


def generate_mock_tts_segment(
    output_path: Path,
    *,
    duration_sec: float,
) -> Path:
    return generate_silent_wav(output_path, duration_sec=max(0.2, duration_sec))


def generate_mock_bgm(
    output_path: Path,
    *,
    duration_sec: float,
    bpm: int = 120,
) -> Path:
    frequency = 180 + (bpm % 80)
    return generate_tone_wav(output_path, duration_sec=duration_sec, frequency_hz=frequency)
