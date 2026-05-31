"""Tests for fal audio provider helpers."""

from video_pipeline.providers.fal_audio import build_bgm_prompt


def test_build_bgm_prompt_instrumental() -> None:
    prompt = build_bgm_prompt(
        music_mood="tense electronic",
        music_bpm=128,
        instrumental=True,
    )
    assert "Instrumental" in prompt
    assert "128 BPM" in prompt
    assert "no vocals" in prompt
