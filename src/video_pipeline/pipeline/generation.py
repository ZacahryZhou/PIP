"""Parallel shot generation stage — t2v or i2v after optional keyframe."""

from __future__ import annotations

from pathlib import Path

from video_pipeline.config import Settings
from video_pipeline.media.ffmpeg import parse_resolution
from video_pipeline.pipeline.keyframe_generation import keyframe_path
from video_pipeline.pipeline.prompts import build_video_prompt
from video_pipeline.providers.fal_video import generate_fal_clip
from video_pipeline.providers.mock import generate_mock_clip
from video_pipeline.schemas import (
    GenerationAttempt,
    GenerationReport,
    KeyframeReport,
    RoutingPlan,
    ScriptPlan,
    ShotGenerationResult,
    ShotsDocument,
)
from video_pipeline.storage import JobPaths, write_json


def raw_clip_path(job: JobPaths, shot_id: str, model: str, attempt: int = 1) -> Path:
    return job.clips_raw_dir / f"{shot_id}_{model}_attempt_{attempt}.mp4"


def _load_keyframe_report(job: JobPaths) -> KeyframeReport | None:
    path = job.reports_dir / "keyframe_report.json"
    if not path.is_file():
        return None
    import json

    from video_pipeline.schemas.keyframe import KeyframeReport as KeyframeReportModel

    return KeyframeReportModel.model_validate(json.loads(path.read_text(encoding="utf-8")))


def run_generation(
    job: JobPaths,
    script: ScriptPlan,
    shots: ShotsDocument,
    routing: RoutingPlan,
    *,
    settings: Settings,
    mock: bool = False,
) -> GenerationReport:
    width, height = parse_resolution(settings.target_resolution)
    shot_by_id = {shot.shot_id: shot for shot in shots.shots}
    keyframe_report = _load_keyframe_report(job)
    keyframe_by_shot = {
        item.shot_id: item for item in (keyframe_report.results if keyframe_report else [])
    }
    results: list[ShotGenerationResult] = []

    for route in routing.routes:
        shot = shot_by_id[route.shot_id]
        mode = route.generation_mode
        keyframe_item = keyframe_by_shot.get(shot.shot_id)
        resolved_keyframe: str | None = None

        if mode == "i2v":
            if keyframe_item is None or keyframe_item.status != "success":
                results.append(
                    ShotGenerationResult(
                        shot_id=shot.shot_id,
                        status="failed",
                        generation_mode=mode,
                        selected_model=route.preferred_model,
                        attempts=[
                            GenerationAttempt(
                                model=route.preferred_model,
                                attempt_number=1,
                                outcome="failed",
                                error_message="Missing or failed keyframe for i2v shot",
                            )
                        ],
                    )
                )
                continue
            resolved_keyframe = keyframe_item.keyframe_path or str(keyframe_path(job, shot.shot_id))

        label = shot.shot_id if mode == "t2v" else f"{shot.shot_id}|i2v"
        prompt = build_video_prompt(shot, script)

        attempts: list[GenerationAttempt] = []
        models_to_try = [route.preferred_model] if mock else [route.preferred_model, route.fallback_model]
        seen_models: set[str] = set()
        try:
            for model in models_to_try:
                if model in seen_models:
                    continue
                seen_models.add(model)
                output_path = raw_clip_path(job, shot.shot_id, model, len(attempts) + 1)
                try:
                    provider_request_id: str | None = None
                    if mock:
                        generate_mock_clip(
                            output_path,
                            width=width,
                            height=height,
                            fps=settings.target_fps,
                            duration_sec=shot.duration_sec,
                            label=label,
                        )
                    else:
                        attempt_route = route.model_copy(update={"preferred_model": model})
                        result = generate_fal_clip(
                            output_path,
                            settings=settings,
                            route=attempt_route,
                            shot=shot,
                            prompt=prompt,
                            keyframe_path=resolved_keyframe,
                        )
                        provider_request_id = result.provider_request_id

                    attempts.append(
                        GenerationAttempt(
                            model=model,
                            attempt_number=len(attempts) + 1,
                            outcome="success",
                            output_path=str(output_path),
                            provider_request_id=provider_request_id,
                        )
                    )
                    results.append(
                        ShotGenerationResult(
                            shot_id=shot.shot_id,
                            status="success",
                            generation_mode=mode,
                            selected_model=model,
                            keyframe_path=resolved_keyframe,
                            output_path=str(output_path),
                            attempts=attempts,
                        )
                    )
                    break
                except Exception as exc:  # noqa: BLE001 — fallback to next model
                    attempts.append(
                        GenerationAttempt(
                            model=model,
                            attempt_number=len(attempts) + 1,
                            outcome="failed",
                            error_message=str(exc),
                        )
                    )
            else:
                results.append(
                    ShotGenerationResult(
                        shot_id=shot.shot_id,
                        status="failed",
                        generation_mode=mode,
                        selected_model=route.preferred_model,
                        keyframe_path=resolved_keyframe,
                        attempts=attempts,
                    )
                )
        except Exception as exc:  # noqa: BLE001 — report per-shot failure
            results.append(
                ShotGenerationResult(
                    shot_id=shot.shot_id,
                    status="failed",
                    generation_mode=mode,
                    selected_model=route.preferred_model,
                    keyframe_path=resolved_keyframe,
                    attempts=attempts
                    or [
                        GenerationAttempt(
                            model=route.preferred_model,
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
