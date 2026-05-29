"""Parallel shot generation stage."""

from __future__ import annotations

from pathlib import Path

from video_pipeline.config import Settings
from video_pipeline.media.ffmpeg import parse_resolution
from video_pipeline.providers.mock import generate_mock_clip
from video_pipeline.schemas import GenerationAttempt, GenerationReport, RoutingPlan, ShotGenerationResult, ShotsDocument
from video_pipeline.storage import JobPaths, write_json


def raw_clip_path(job: JobPaths, shot_id: str, model: str, attempt: int = 1) -> Path:
    return job.clips_raw_dir / f"{shot_id}_{model}_attempt_{attempt}.mp4"


def run_generation(
    job: JobPaths,
    shots: ShotsDocument,
    routing: RoutingPlan,
    *,
    settings: Settings,
) -> GenerationReport:
    width, height = parse_resolution(settings.target_resolution)
    shot_by_id = {shot.shot_id: shot for shot in shots.shots}
    results: list[ShotGenerationResult] = []

    for route in routing.routes:
        shot = shot_by_id[route.shot_id]
        model = route.preferred_model
        output_path = raw_clip_path(job, shot.shot_id, model)
        try:
            generate_mock_clip(
                output_path,
                width=width,
                height=height,
                fps=settings.target_fps,
                duration_sec=shot.duration_sec,
                label=shot.shot_id,
            )
            attempt = GenerationAttempt(
                model=model,
                attempt_number=1,
                outcome="success",
                output_path=str(output_path),
            )
            results.append(
                ShotGenerationResult(
                    shot_id=shot.shot_id,
                    status="success",
                    selected_model=model,
                    output_path=str(output_path),
                    attempts=[attempt],
                )
            )
        except Exception as exc:  # noqa: BLE001 — report per-shot failure
            results.append(
                ShotGenerationResult(
                    shot_id=shot.shot_id,
                    status="failed",
                    selected_model=model,
                    attempts=[
                        GenerationAttempt(
                            model=model,
                            attempt_number=1,
                            outcome="failed",
                            error_message=str(exc),
                        )
                    ],
                )
            )

    succeeded = [item.shot_id for item in results if item.status == "success"]
    failed = [item.shot_id for item in results if item.status == "failed"]
    report = GenerationReport(
        job_id=job.job_id,
        results=results,
        succeeded_shot_ids=succeeded,
        failed_shot_ids=failed,
    )
    write_json(job.reports_dir / "generation_report.json", report)
    return report
