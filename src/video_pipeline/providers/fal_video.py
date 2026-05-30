"""fal.ai video provider for t2v and i2v shots."""

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
    """Map internal routing names to configured fal endpoints."""
    model = route.preferred_model
    if model == "seedance":
        endpoint = (
            settings.fal_video_model_seedance_i2v
            if route.generation_mode == "i2v"
            else settings.fal_video_model_seedance
        )
    elif model == "kling":
        endpoint = (
            settings.fal_video_model_kling_i2v
            if route.generation_mode == "i2v"
            else settings.fal_video_model_kling
        )
    elif model == "wan_t2v":
        endpoint = settings.fal_video_model_wan
    elif model == "premium_api":
        endpoint = settings.fal_video_model_seedance
    else:
        endpoint = ""

    if not endpoint:
        raise ValueError(f"No fal endpoint configured for {model}/{route.generation_mode}")
    return endpoint


def generate_fal_clip(
    output_path: Path,
    *,
    settings: Settings,
    route: RouteDecision,
    shot: Shot,
    prompt: str,
    keyframe_path: str | None = None,
) -> FalVideoResult:
    """Generate one video clip with fal and save it to the raw clips directory."""
    fal_client = require_fal_client(settings.fal_key)
    endpoint = select_fal_video_endpoint(route, settings)
    duration = max(1, math.ceil(shot.duration_sec))
    arguments: dict[str, object] = {
        "prompt": prompt,
        "duration": str(duration),
        "aspect_ratio": "16:9",
        "generate_audio": settings.fal_video_generate_audio,
    }

    if route.generation_mode == "i2v":
        if not keyframe_path:
            raise ValueError("keyframe_path is required for i2v fal generation")
        arguments["image_url"] = fal_client.upload_file(keyframe_path)

    result = fal_client.subscribe(endpoint, arguments=arguments, with_logs=True)
    video_url = first_url(result, preferred_exts=(".mp4", ".mov", ".webm", ".m4v"))
    download_url(video_url, output_path)
    return FalVideoResult(
        output_path=output_path,
        provider_request_id=request_id_from(result),
        endpoint=endpoint,
    )
