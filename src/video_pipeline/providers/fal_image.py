"""fal.ai image provider for i2v keyframes."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from video_pipeline.providers.fal_utils import (
    download_url,
    first_url,
    request_id_from,
    require_fal_client,
)


@dataclass(frozen=True)
class FalImageResult:
    output_path: Path
    provider_request_id: str | None = None


def generate_fal_keyframe(
    output_path: Path,
    *,
    api_key: str,
    model: str,
    prompt: str,
    width: int = 1920,
    height: int = 1080,
    reference_image_path: Path | None = None,
) -> FalImageResult:
    """Generate one cinematic still frame and save it locally."""
    fal_client = require_fal_client(api_key)
    arguments: dict[str, object] = {
        "prompt": prompt,
        "image_size": {"width": width, "height": height},
        "output_format": "png",
    }
    if reference_image_path is not None:
        arguments["image_url"] = fal_client.upload_file(str(reference_image_path))
    result = fal_client.subscribe(
        model,
        arguments=arguments,
        with_logs=True,
    )
    image_url = first_url(result, preferred_exts=(".png", ".jpg", ".jpeg", ".webp"))
    download_url(image_url, output_path)
    return FalImageResult(
        output_path=output_path,
        provider_request_id=request_id_from(result),
    )
