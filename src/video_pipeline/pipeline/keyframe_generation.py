"""Keyframe generation — still image for i2v shots."""

from __future__ import annotations

from pathlib import Path

from video_pipeline.config import Settings
from video_pipeline.media.ffmpeg import parse_resolution
from video_pipeline.pipeline.prompts import build_keyframe_prompt
from video_pipeline.providers.fal_image import generate_fal_keyframe
from video_pipeline.providers.mock import generate_mock_keyframe
from video_pipeline.schemas import KeyframeReport, KeyframeResult, RoutingPlan, ScriptPlan, ShotsDocument
from video_pipeline.storage import JobPaths, write_json


def keyframe_path(job: JobPaths, shot_id: str) -> Path:
    return job.keyframes_dir / f"{shot_id}_keyframe.png"


def run_keyframe_generation(
    job: JobPaths,
    script: ScriptPlan,
    shots: ShotsDocument,
    routing: RoutingPlan,
    *,
    settings: Settings,
    mock: bool = False,
) -> KeyframeReport:
    width, height = parse_resolution(settings.target_resolution)
    shot_by_id = {shot.shot_id: shot for shot in shots.shots}
    results: list[KeyframeResult] = []

    for route in routing.routes:
        shot = shot_by_id[route.shot_id]
        if route.generation_mode == "t2v":
            results.append(
                KeyframeResult(
                    shot_id=shot.shot_id,
                    generation_mode="t2v",
                    status="skipped",
                )
            )
            continue

        prompt = build_keyframe_prompt(shot, script)
        output = keyframe_path(job, shot.shot_id)
        try:
            provider_request_id: str | None = None
            if mock:
                generate_mock_keyframe(
                    output,
                    width=width,
                    height=height,
                    label=shot.shot_id,
                )
            else:
                result = generate_fal_keyframe(
                    output,
                    api_key=settings.fal_key,
                    model=settings.fal_image_model,
                    prompt=prompt,
                    width=width,
                    height=height,
                )
                provider_request_id = result.provider_request_id
            results.append(
                KeyframeResult(
                    shot_id=shot.shot_id,
                    generation_mode="i2v",
                    status="success",
                    keyframe_path=str(output),
                    prompt=prompt,
                    provider_request_id=provider_request_id,
                )
            )
        except Exception as exc:  # noqa: BLE001
            results.append(
                KeyframeResult(
                    shot_id=shot.shot_id,
                    generation_mode="i2v",
                    status="failed",
                    prompt=prompt,
                    error_message=str(exc),
                )
            )

    report = KeyframeReport(job_id=job.job_id, results=results)
    write_json(job.reports_dir / "keyframe_report.json", report)
    return report
