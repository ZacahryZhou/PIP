"""fal.ai Kling first-last-frame video provider (V2)."""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path

from video_pipeline.config import Settings
from video_pipeline.providers.fal_utils import (
    download_url,
    first_url,
    request_id_from,
    require_fal_client,
)
from video_pipeline.schemas import RouteDecision, Shot


@dataclass(frozen=True)
class FalVideoResult:
    output_path: Path
    provider_request_id: str | None = None
    endpoint: str | None = None


def select_fal_video_endpoint(route: RouteDecision, settings: Settings) -> str:
    if route.generation_mode != "first_last_frame":
        raise ValueError(f"V2 only supports first_last_frame, got {route.generation_mode}")
    if route.preferred_model != "kling":
        raise ValueError(f"V2 only supports kling, got {route.preferred_model}")
    endpoint = settings.fal_video_model_kling_fl
    if not endpoint:
        raise ValueError("FAL video endpoint not configured (fal_video_model_kling_fl)")
    return endpoint


def build_fal_video_arguments(
    *,
    settings: Settings,
    route: RouteDecision,
    shot: Shot,
    prompt: str,
    endpoint: str,
    start_image_url: str | None = None,
    end_image_url: str | None = None,
) -> dict[str, object]:
    duration = max(1, math.ceil(shot.duration_sec))
    arguments: dict[str, object] = {
        "prompt": prompt,
        "duration": str(duration),
        "aspect_ratio": "16:9",
        "generate_audio": settings.fal_video_generate_audio,
    }
    if route.generation_mode == "first_last_frame":
        if not start_image_url or not end_image_url:
            raise ValueError("start_image_url and end_image_url are required for first-last-frame")
        arguments["start_image_url"] = start_image_url
        arguments["end_image_url"] = end_image_url
        # Some fal Kling endpoints also accept image_url as alias for start.
        arguments["image_url"] = start_image_url
    return arguments


def generate_fal_clip(
    output_path: Path,
    *,
    settings: Settings,
    route: RouteDecision,
    shot: Shot,
    prompt: str,
    keyframe_path: str | None = None,
    end_keyframe_path: str | None = None,
) -> FalVideoResult:
    """Generate one Kling first-last-frame clip via fal."""
    fal_client = require_fal_client(settings.fal_key)
    endpoint = select_fal_video_endpoint(route, settings)

    start_url: str | None = None
    end_url: str | None = None
    if route.generation_mode == "first_last_frame":
        if not keyframe_path or not end_keyframe_path:
            raise ValueError("keyframe_path and end_keyframe_path are required")
        start_url = fal_client.upload_file(keyframe_path)
        end_url = fal_client.upload_file(end_keyframe_path)

    arguments = build_fal_video_arguments(
        settings=settings,
        route=route,
        shot=shot,
        prompt=prompt,
        endpoint=endpoint,
        start_image_url=start_url,
        end_image_url=end_url,
    )

    result = fal_client.subscribe(endpoint, arguments=arguments, with_logs=True)
    video_url = first_url(result, preferred_exts=(".mp4", ".mov", ".webm", ".m4v"))
    download_url(video_url, output_path)
    return FalVideoResult(
        output_path=output_path,
        provider_request_id=request_id_from(result),
        endpoint=endpoint,
    )
