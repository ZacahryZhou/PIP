from __future__ import annotations

import shutil
from pathlib import Path

from video_pipeline.agents.keyframe_prompt_agent import run_keyframe_prompt_agent
from video_pipeline.config import Settings
from video_pipeline.media.ffmpeg import parse_resolution
from video_pipeline.pipeline.approval import load_preview_document
from video_pipeline.pipeline.asset_binding import load_shot_asset_binding_map, primary_conditioning_path
from video_pipeline.pipeline.resume import keyframe_entry_complete, load_keyframe_report
from video_pipeline.pipeline.stage_report import StageTimer, write_stage_report
from video_pipeline.pipeline.scene_maps import load_scene_master_map
from video_pipeline.providers.fal_image import generate_fal_keyframe
from video_pipeline.providers.mock import generate_mock_keyframe
from video_pipeline.schemas import KeyframePromptsDocument, KeyframeReport, KeyframeResult, RoutingPlan, ScriptPlan, ShotsDocument
from video_pipeline.storage import JobPaths


def keyframe_start_path(job: JobPaths, shot_id: str) -> Path:
    return job.keyframes_dir / f"{shot_id}_start.png"


def keyframe_end_path(job: JobPaths, shot_id: str) -> Path:
    return job.keyframes_dir / f"{shot_id}_end.png"


def keyframe_path(job: JobPaths, shot_id: str) -> Path:
    """Legacy single-frame path — kept for backward compatibility."""
    return job.keyframes_dir / f"{shot_id}_keyframe.png"


def _preview_frames_for_shot(job: JobPaths, shot_id: str) -> tuple[Path | None, Path | None]:
    try:
        preview = load_preview_document(job)
    except FileNotFoundError:
        return None, None
    for item in preview.items:
        if item.shot_id != shot_id or item.status != "ok":
            continue
        start = job.root / item.start_image_path
        end = job.root / item.end_image_path
        start_path = start if start.is_file() else None
        end_path = end if end.is_file() else None
        return start_path, end_path
    return None, None


def _generate_still(
    output: Path,
    *,
    prompt: str,
    settings: Settings,
    mock: bool,
    width: int,
    height: int,
    label: str,
    reference_image_path: Path | None = None,
) -> str | None:
    if mock:
        generate_mock_keyframe(output, width=width, height=height, label=label)
        return None
    if not settings.fal_key:
        raise ValueError("FAL_KEY is required for keyframe generation")
    result = generate_fal_keyframe(
        output,
        api_key=settings.fal_key,
        model=settings.fal_image_model,
        prompt=prompt,
        width=width,
        height=height,
        reference_image_path=reference_image_path,
    )
    return result.provider_request_id


def run_keyframe_generation(
    job: JobPaths,
    script: ScriptPlan,
    shots: ShotsDocument,
    routing: RoutingPlan,
    *,
    settings: Settings,
    mock: bool = False,
) -> KeyframeReport:
    timer = StageTimer(
        job_id=job.job_id,
        stage="keyframes",
        input_artifacts=[
            str(job.routing_path.relative_to(job.root)),
            str(job.reports_dir / "scene_map_report.json"),
        ],
    )
    width, height = parse_resolution(settings.target_resolution)
    shot_by_id = {shot.shot_id: shot for shot in shots.shots}
    scene_masters = load_scene_master_map(job)
    binding_map = load_shot_asset_binding_map(job)
    job.keyframes_dir.mkdir(parents=True, exist_ok=True)
    existing_report = load_keyframe_report(job)
    existing_by_shot = {item.shot_id: item for item in existing_report.results} if existing_report else {}
    provider_requests = 0
    resumed_count = 0
    errors: list[str] = []

    prompts_doc = run_keyframe_prompt_agent(
        job,
        script,
        shots,
        scene_masters=scene_masters,
        settings=settings,
        mock=mock,
    )
    prompt_by_shot = {item.shot_id: item for item in prompts_doc.items}
    results: list[KeyframeResult] = []

    for route in routing.routes:
        shot = shot_by_id[route.shot_id]
        if route.generation_mode != "first_last_frame":
            results.append(
                KeyframeResult(
                    shot_id=shot.shot_id,
                    generation_mode=route.generation_mode,
                    status="failed",
                    error_message="V2 pipeline requires first_last_frame",
                )
            )
            continue

        previous = existing_by_shot.get(shot.shot_id)
        if (
            previous is not None
            and previous.status == "success"
            and keyframe_entry_complete(
                job,
                shot_id=shot.shot_id,
                generation_mode=route.generation_mode,
            )
        ):
            results.append(previous)
            resumed_count += 1
            continue

        entry = prompt_by_shot[shot.shot_id]
        binding = binding_map.get(shot.shot_id)
        reference_path = (
            primary_conditioning_path(job, shot, binding) if binding is not None else None
        )
        start_output = keyframe_start_path(job, shot.shot_id)
        end_output = keyframe_end_path(job, shot.shot_id)
        legacy_output = keyframe_path(job, shot.shot_id)
        reused_preview = False
        provider_request_id: str | None = None

        try:
            preview_start, preview_end = _preview_frames_for_shot(job, shot.shot_id)
            if preview_start is not None:
                shutil.copy2(preview_start, start_output)
                reused_preview = True
            else:
                provider_request_id = _generate_still(
                    start_output,
                    prompt=entry.start_prompt,
                    settings=settings,
                    mock=mock,
                    width=width,
                    height=height,
                    label=f"{shot.shot_id}|start",
                    reference_image_path=reference_path,
                )
                if provider_request_id is not None:
                    provider_requests += 1

            end_path_str: str | None = None
            if preview_end is not None:
                shutil.copy2(preview_end, end_output)
                end_path_str = str(end_output)
            else:
                end_provider_id = _generate_still(
                    end_output,
                    prompt=entry.end_prompt,
                    settings=settings,
                    mock=mock,
                    width=width,
                    height=height,
                    label=f"{shot.shot_id}|end",
                    reference_image_path=reference_path,
                )
                if end_provider_id is not None:
                    provider_requests += 1
                end_path_str = str(end_output)

            shutil.copy2(start_output, legacy_output)

            results.append(
                KeyframeResult(
                    shot_id=shot.shot_id,
                    generation_mode=route.generation_mode,
                    status="success",
                    start_frame_path=str(start_output),
                    end_frame_path=end_path_str,
                    keyframe_path=str(start_output),
                    start_prompt=entry.start_prompt,
                    end_prompt=entry.end_prompt,
                    reused_preview_as_start=reused_preview,
                    prompt=entry.start_prompt,
                    provider_request_id=provider_request_id,
                )
            )
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{shot.shot_id}: {exc}")
            results.append(
                KeyframeResult(
                    shot_id=shot.shot_id,
                    generation_mode=route.generation_mode,
                    status="failed",
                    start_prompt=entry.start_prompt,
                    end_prompt=entry.end_prompt,
                    prompt=entry.start_prompt,
                    error_message=str(exc),
                )
            )

    report = KeyframeReport(job_id=job.job_id, results=results)
    status = "failed" if any(item.status == "failed" for item in results) else "ok"
    if resumed_count and status == "ok" and provider_requests == 0:
        status = "skipped"
    envelope = timer.envelope(
        status=status,  # type: ignore[arg-type]
        output_artifacts=[
            str((job.reports_dir / "keyframe_report.json").relative_to(job.root)),
            str((job.keyframes_dir / "keyframe_prompts.json").relative_to(job.root)),
        ],
        errors=errors,
        provider_request_count=provider_requests,
        resumed=resumed_count > 0 and provider_requests == 0,
    )
    write_stage_report(
        job,
        job.reports_dir / "keyframe_report.json",
        envelope,
        report.model_dump(),
    )
    return report


def load_keyframe_prompts(job: JobPaths) -> KeyframePromptsDocument | None:
    path = job.keyframes_dir / "keyframe_prompts.json"
    if not path.is_file():
        return None
    return KeyframePromptsDocument.model_validate_json(path.read_text(encoding="utf-8"))
