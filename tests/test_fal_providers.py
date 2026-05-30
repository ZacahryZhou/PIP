"""Tests for fal provider wiring that do not call external APIs."""

import pytest

from video_pipeline.config import Settings
from video_pipeline.providers.fal_utils import first_url
from video_pipeline.providers.fal_video import select_fal_video_endpoint
from video_pipeline.schemas import RouteDecision


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
