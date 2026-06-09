"""Parallel shot generation stage — t2v or i2v after optional keyframe."""

from __future__ import annotations

from pathlib import Path

from video_pipeline.config import Settings
from video_pipeline.media.ffmpeg import parse_resolution
from video_pipeline.pipeline.keyframe_generation import keyframe_end_path, keyframe_path, keyframe_start_path
from video_pipeline.pipeline.asset_binding import load_shot_asset_binding_map, video_reference_paths
from video_pipeline.pipeline.prompts import build_video_prompt
from video_pipeline.pipeline.resume import generation_output_path, load_generation_report
from video_pipeline.pipeline.stage_report import StageTimer, write_stage_report
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
from video_pipeline.storage import JobPaths


def raw_clip_path(job: JobPaths, shot_id: str, model: str, attempt: int = 1) -> Path:
    return job.clips_raw_dir / f"{shot_id}_{model}_attempt_{attempt}.mp4"


def _load_keyframe_report(job: JobPaths) -> KeyframeReport | None:
    path = job.reports_dir / "keyframe_report.json"
    if not path.is_file():
        return None
    import json

    from video_pipeline.schemas.keyframe import KeyframeReport as KeyframeReportModel

    payload = json.loads(path.read_text(encoding="utf-8"))
    return KeyframeReportModel.model_validate({k: v for k, v in payload.items() if k != "stage"})


def run_generation(
    job: JobPaths,
    script: ScriptPlan,
    shots: ShotsDocument,
    routing: RoutingPlan,
    *,
    settings: Settings,
    mock: bool = False,
) -> GenerationReport:
    timer = StageTimer(
        job_id=job.job_id,
        stage="generation",
        input_artifacts=[
            str(job.routing_path.relative_to(job.root)),
            str(job.reports_dir / "keyframe_report.json"),
        ],
    )
    width, height = parse_resolution(settings.target_resolution)
    shot_by_id = {shot.shot_id: shot for shot in shots.shots}
    keyframe_report = _load_keyframe_report(job)
    binding_map = load_shot_asset_binding_map(job)
    keyframe_by_shot = {
        item.shot_id: item for item in (keyframe_report.results if keyframe_report else [])
    }
    existing_report = load_generation_report(job)
    existing_by_shot = {item.shot_id: item for item in existing_report.results} if existing_report else {}
    results: list[ShotGenerationResult] = []
    provider_requests = 0
    resumed_count = 0
    errors: list[str] = []

    for route in routing.routes:
        shot = shot_by_id[route.shot_id]
        previous = existing_by_shot.get(shot.shot_id)
        if (
            previous is not None
            and previous.status == "success"
            and generation_output_path(job, shot.shot_id, previous) is not None
        ):
            results.append(previous)
            resumed_count += 1
            continue

        mode = route.generation_mode
        keyframe_item = keyframe_by_shot.get(shot.shot_id)
        resolved_keyframe: str | None = None
        resolved_end: str | None = None

        if mode != "first_last_frame":
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
                            error_message=f"Unsupported generation mode {mode} in V2 pipeline",
                        )
                    ],
                )
            )
            continue

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
                            error_message="Missing or failed keyframes for first-last-frame shot",
                        )
                    ],
                )
            )
            continue

        resolved_keyframe = (
            keyframe_item.start_frame_path
            or keyframe_item.keyframe_path
            or str(keyframe_start_path(job, shot.shot_id))
        )
        resolved_end = keyframe_item.end_frame_path or str(keyframe_end_path(job, shot.shot_id))

        label = f"{shot.shot_id}|{mode}"
        prompt = build_video_prompt(shot, script)
        binding = binding_map.get(shot.shot_id)
        reference_paths: list[str] | None = None
        if binding is not None:
            refs = video_reference_paths(job, binding)
            if refs:
                reference_paths = [str(path) for path in refs]

        attempts: list[GenerationAttempt] = []
        models_to_try = [route.preferred_model]
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
                            end_keyframe_path=resolved_end,
                            reference_image_paths=reference_paths,
                        )
                        provider_request_id = result.provider_request_id
                        provider_requests += 1

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
            errors.append(f"{shot.shot_id}: {exc}")
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
    status = "failed" if failed else "ok"
    if resumed_count and status == "ok" and provider_requests == 0:
        status = "skipped"
    envelope = timer.envelope(
        status=status,  # type: ignore[arg-type]
        output_artifacts=[str((job.reports_dir / "generation_report.json").relative_to(job.root))],
        errors=errors,
        provider_request_count=provider_requests,
        resumed=resumed_count > 0 and provider_requests == 0,
    )
    write_stage_report(
        job,
        job.reports_dir / "generation_report.json",
        envelope,
        report.model_dump(),
    )
    return report
