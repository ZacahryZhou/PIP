"""fal provider unit tests for V2 Kling first-last-frame."""

from video_pipeline.providers.fal_video import build_fal_video_arguments, select_fal_video_endpoint
from video_pipeline.schemas import RouteDecision
from video_pipeline.config import Settings


def route(model: str, mode: str) -> RouteDecision:
    return RouteDecision(
        shot_id="shot_001",
        preferred_model=model,  # type: ignore[arg-type]
        fallback_model=model,  # type: ignore[arg-type]
        generation_mode=mode,  # type: ignore[arg-type]
        generation_mode_reason="test",
        routing_reason="test",
        estimated_keyframe_cost=0.3,
        estimated_cost_per_shot=0.8,
        estimated_duration_sec=5,
        supports_t2v=False,
        supports_i2v=True,
        supports_first_last_frame=True,
        supports_audio_generation=False,
    )


def test_select_fal_video_endpoint_kling_fl() -> None:
    settings = Settings(fal_video_model_kling_fl="kling-fl-endpoint")
    endpoint = select_fal_video_endpoint(route("kling", "first_last_frame"), settings)
    assert endpoint == "kling-fl-endpoint"


def test_select_fal_video_endpoint_rejects_non_fl() -> None:
    settings = Settings(fal_video_model_kling_fl="kling-fl-endpoint")
    try:
        select_fal_video_endpoint(route("kling", "t2v"), settings)
    except ValueError as exc:
        assert "first_last_frame" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_build_fal_video_arguments_first_last_requires_both_urls() -> None:
    settings = Settings()
    shot = __import__("video_pipeline.schemas", fromlist=["Shot"]).Shot(
        shot_id="shot_001",
        scene_id="scene_001",
        duration_sec=5,
        subject="test",
        shot_size="MS",
        camera_angle="eye level",
        camera_move="static",
        action="walk",
        facial_expression="neutral",
        character_gaze="forward",
        blocking="center",
        mood="calm",
        scene_type="realistic",
        motion_intensity="low",
        has_characters=False,
        generation_mode="first_last_frame",
        generation_mode_reason="test",
    )
    args = build_fal_video_arguments(
        settings=settings,
        route=route("kling", "first_last_frame"),
        shot=shot,
        prompt="prompt",
        endpoint="kling-fl-endpoint",
        start_image_url="https://example.com/start.png",
        end_image_url="https://example.com/end.png",
    )
    assert args["start_image_url"] == "https://example.com/start.png"
    assert args["end_image_url"] == "https://example.com/end.png"


def test_build_fal_video_arguments_passes_reference_urls() -> None:
    settings = Settings()
    shot = __import__("video_pipeline.schemas", fromlist=["Shot"]).Shot(
        shot_id="shot_001",
        scene_id="scene_001",
        duration_sec=5,
        subject="test",
        shot_size="MS",
        camera_angle="eye level",
        camera_move="static",
        action="walk",
        facial_expression="neutral",
        character_gaze="forward",
        blocking="center",
        mood="calm",
        scene_type="realistic",
        motion_intensity="low",
        has_characters=True,
        character_ids=["Coffeefee"],
        character_prompts=["Coffeefee in neutral pose"],
        generation_mode="first_last_frame",
        generation_mode_reason="test",
    )
    args = build_fal_video_arguments(
        settings=settings,
        route=route("kling", "first_last_frame"),
        shot=shot,
        prompt="prompt",
        endpoint="kling-fl-endpoint",
        start_image_url="https://example.com/start.png",
        end_image_url="https://example.com/end.png",
        reference_image_urls=["https://example.com/char.png"],
    )
    assert args["reference_image_urls"] == ["https://example.com/char.png"]
