"""Tests for fal provider wiring that do not call external APIs."""

import pytest

from video_pipeline.config import Settings
from video_pipeline.providers.fal_utils import first_url
from video_pipeline.providers.fal_video import build_fal_video_arguments, select_fal_video_endpoint
from video_pipeline.schemas import RouteDecision, Shot


def route(preferred_model: str, generation_mode: str) -> RouteDecision:
    return RouteDecision(
        shot_id="shot_001",
        preferred_model=preferred_model,  # type: ignore[arg-type]
        fallback_model="kling",
        generation_mode=generation_mode,  # type: ignore[arg-type]
        generation_mode_reason="test",
        routing_reason="test",
        estimated_cost_per_shot=0.1,
        estimated_duration_sec=1,
    )


def test_select_fal_video_endpoint_branches_t2v_and_i2v() -> None:
    settings = Settings(
        fal_video_model_seedance="seedance-t2v",
        fal_video_model_seedance_i2v="seedance-i2v",
        fal_video_model_kling="kling-t2v",
        fal_video_model_kling_i2v="kling-i2v",
    )

    assert select_fal_video_endpoint(route("seedance", "t2v"), settings) == "seedance-t2v"
    assert select_fal_video_endpoint(route("seedance", "i2v"), settings) == "seedance-i2v"
    assert select_fal_video_endpoint(route("kling", "t2v"), settings) == "kling-t2v"
    assert select_fal_video_endpoint(route("kling", "i2v"), settings) == "kling-i2v"


def test_select_fal_video_endpoint_requires_wan_configuration() -> None:
    with pytest.raises(ValueError, match="No fal endpoint configured"):
        select_fal_video_endpoint(route("wan_t2v", "t2v"), Settings(fal_video_model_wan=""))


def test_first_url_prefers_media_extension_in_nested_response() -> None:
    payload = {
        "logs": [{"url": "https://example.com/not-media"}],
        "video": {"url": "https://cdn.example.com/result.mp4"},
    }

    assert first_url(payload, preferred_exts=(".mp4",)) == "https://cdn.example.com/result.mp4"


def _sample_shot() -> Shot:
    return Shot.model_validate(
        {
            "shot_id": "shot_001",
            "scene_id": "scene_001",
            "duration_sec": 4.0,
            "subject": "hero in alley",
            "shot_size": "MS",
            "camera_angle": "eye level",
            "camera_move": "slow push-in",
            "action": "looks over shoulder",
            "facial_expression": "alert",
            "character_gaze": "off-screen left",
            "blocking": "center frame",
            "mood": "tense",
            "scene_type": "realistic",
            "motion_intensity": "medium",
            "has_characters": True,
            "character_ids": ["hero"],
            "character_prompts": ["hero: athletic build"],
            "generation_mode": "t2v",
            "generation_mode_reason": "establishing motion",
        }
    )


def test_build_fal_video_arguments_seedance_includes_1080p() -> None:
    settings = Settings(fal_video_resolution="1080p")
    args = build_fal_video_arguments(
        settings=settings,
        route=route("seedance", "t2v"),
        shot=_sample_shot(),
        prompt="test prompt",
        endpoint="fal-ai/bytedance/seedance/v1.5/pro/text-to-video",
    )
    assert args["resolution"] == "1080p"
    assert args["aspect_ratio"] == "16:9"


def test_build_fal_video_arguments_kling_omits_resolution_param() -> None:
    settings = Settings(fal_video_resolution="1080p")
    args = build_fal_video_arguments(
        settings=settings,
        route=route("kling", "t2v"),
        shot=_sample_shot(),
        prompt="test prompt",
        endpoint="fal-ai/kling-video/v3/pro/text-to-video",
    )
    assert "resolution" not in args
