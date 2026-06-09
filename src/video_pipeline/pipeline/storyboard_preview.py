"""Storyboard strip — per-shot start/end stills before video (V2)."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from video_pipeline.config import Settings
from video_pipeline.media.ffmpeg import parse_resolution
from video_pipeline.pipeline.approval import load_preview_document
from video_pipeline.pipeline.prompts import build_keyframe_end_prompt, build_keyframe_start_prompt, build_preview_prompt
from video_pipeline.pipeline.resume import preview_matches_approval
from video_pipeline.pipeline.scene_maps import load_scene_master_map
from video_pipeline.pipeline.stage_report import StageTimer, write_stage_report
from video_pipeline.providers.fal_image import generate_fal_keyframe
from video_pipeline.providers.mock import generate_mock_preview
from video_pipeline.schemas import ScriptPlan, ShotsDocument, StoryboardPreviewDocument, StoryboardPreviewItem
from video_pipeline.storage import JobPaths, write_json


def preview_start_path(job: JobPaths, shot_id: str, *, preview_version: int = 1) -> Path:
    suffix = "" if preview_version == 1 else f"_v{preview_version}"
    return job.preview_dir / f"{shot_id}_start{suffix}.png"


def preview_end_path(job: JobPaths, shot_id: str, *, preview_version: int = 1) -> Path:
    suffix = "" if preview_version == 1 else f"_v{preview_version}"
    return job.preview_dir / f"{shot_id}_end{suffix}.png"


def preview_image_path(job: JobPaths, shot_id: str, *, preview_version: int = 1) -> Path:
    return preview_start_path(job, shot_id, preview_version=preview_version)


def current_preview_version(job: JobPaths) -> int:
    if not job.storyboard_preview_path.is_file():
        return 1
    document = StoryboardPreviewDocument.model_validate_json(
        job.storyboard_preview_path.read_text(encoding="utf-8")
    )
    return document.preview_version


def _scene_for_shot(script: ScriptPlan, scene_id: str):
    for scene in script.scene_list:
        if scene.scene_id == scene_id:
            return scene
    return None


def run_storyboard_preview(
    job: JobPaths,
    script: ScriptPlan,
    shots: ShotsDocument,
    *,
    settings: Settings,
    mock: bool = False,
    preview_version: int | None = None,
) -> StoryboardPreviewDocument:
    version = preview_version or (current_preview_version(job) + 1 if job.storyboard_preview_path.is_file() else 1)
    if preview_version is None and preview_matches_approval(job, shots=shots):
        return load_preview_document(job)

    timer = StageTimer(
        job_id=job.job_id,
        stage="storyboard_preview",
        input_artifacts=[
            str(job.script_path.relative_to(job.root)),
            str(job.shots_path.relative_to(job.root)),
            str(job.reports_dir / "character_asset_report.json"),
            str(job.reports_dir / "scene_map_report.json"),
        ],
    )
    width, height = parse_resolution(settings.target_resolution)
    scene_masters = load_scene_master_map(job)
    items: list[StoryboardPreviewItem] = []
    failures: list[str] = []

    for shot in shots.shots:
        scene = _scene_for_shot(script, shot.scene_id)
        master = scene_masters.get(shot.scene_id)
        start_prompt = build_keyframe_start_prompt(
            shot,
            script,
            scene=scene,
            scene_master_path=master,
        )
        end_prompt = build_keyframe_end_prompt(
            shot,
            script,
            scene=scene,
            scene_master_path=master,
        )
        summary_prompt = build_preview_prompt(shot, script)
        start_output = preview_start_path(job, shot.shot_id, preview_version=version)
        end_output = preview_end_path(job, shot.shot_id, preview_version=version)

        try:
            for output, prompt, label in (
                (start_output, start_prompt, f"{shot.shot_id}|start"),
                (end_output, end_prompt, f"{shot.shot_id}|end"),
            ):
                if mock:
                    generate_mock_preview(
                        output,
                        width=width,
                        height=height,
                        label=label,
                    )
                else:
                    if not settings.fal_key:
                        raise ValueError("FAL_KEY is required for storyboard preview generation")
                    generate_fal_keyframe(
                        output,
                        api_key=settings.fal_key,
                        model=settings.fal_image_model,
                        prompt=prompt,
                        width=width,
                        height=height,
                    )
            items.append(
                StoryboardPreviewItem(
                    shot_id=shot.shot_id,
                    scene_id=shot.scene_id,
                    preview_image_path=str(start_output.relative_to(job.root)),
                    start_image_path=str(start_output.relative_to(job.root)),
                    end_image_path=str(end_output.relative_to(job.root)),
                    start_prompt=start_prompt,
                    end_prompt=end_prompt,
                    prompt=summary_prompt,
                    status="ok",
                )
            )
        except Exception as exc:  # noqa: BLE001
            failures.append(f"{shot.shot_id}: {exc}")
            items.append(
                StoryboardPreviewItem(
                    shot_id=shot.shot_id,
                    scene_id=shot.scene_id,
                    preview_image_path=str(start_output.relative_to(job.root)),
                    start_image_path=str(start_output.relative_to(job.root)),
                    end_image_path=str(end_output.relative_to(job.root)),
                    start_prompt=start_prompt,
                    end_prompt=end_prompt,
                    prompt=summary_prompt,
                    status="failed",
                )
            )

    document = StoryboardPreviewDocument(
        job_id=job.job_id,
        preview_version=version,
        items=items,
        created_at=datetime.now(timezone.utc),
    )
    write_json(job.storyboard_preview_path, document)
    status = "failed" if failures else "ok"
    envelope = timer.envelope(
        status=status,  # type: ignore[arg-type]
        output_artifacts=[
            str(job.storyboard_preview_path.relative_to(job.root)),
            str((job.reports_dir / "preview_report.json").relative_to(job.root)),
        ],
        errors=failures,
    )
    write_stage_report(
        job,
        job.reports_dir / "preview_report.json",
        envelope,
        {
            "preview_version": version,
            "item_count": len(items),
            "failed_shots": failures,
        },
    )
    if failures and all(item.status == "failed" for item in items):
        raise RuntimeError("All storyboard preview stills failed: " + "; ".join(failures))
    return document
