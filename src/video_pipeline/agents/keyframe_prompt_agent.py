"""Keyframe Prompt Agent — deterministic start/end prompts for image generation."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from video_pipeline.pipeline.prompts import build_keyframe_end_prompt, build_keyframe_start_prompt
from video_pipeline.pipeline.stage_report import StageTimer, write_stage_report
from video_pipeline.schemas import KeyframePromptEntry, KeyframePromptsDocument, ScriptPlan, ShotsDocument
from video_pipeline.storage import JobPaths, repo_root, write_json


def _load_rule(job: JobPaths, name: str) -> str:
    path = job.rules_snapshot_dir / name
    if path.is_file():
        return path.read_text(encoding="utf-8")
    fallback = repo_root() / "rules" / name
    return fallback.read_text(encoding="utf-8") if fallback.is_file() else ""


def keyframe_prompts_path(job: JobPaths) -> Path:
    return job.keyframes_dir / "keyframe_prompts.json"


def keyframe_prompt_report_path(job: JobPaths) -> Path:
    return job.reports_dir / "keyframe_prompt_report.json"


def run_keyframe_prompt_agent(
    job: JobPaths,
    script: ScriptPlan,
    shots: ShotsDocument,
    *,
    scene_masters: dict[str, Path] | None = None,
    mock: bool = True,
) -> KeyframePromptsDocument:
    del mock  # deterministic formatting for now; DeepSeek optional later
    timer = StageTimer(
        job_id=job.job_id,
        stage="keyframe_prompts",
        input_artifacts=[
            str(job.script_path.relative_to(job.root)),
            str(job.shots_path.relative_to(job.root)),
        ],
    )
    _load_rule(job, "KEYFRAME.md")
    scenes_by_id = {scene.scene_id: scene for scene in script.scene_list}
    masters = scene_masters or {}
    items: list[KeyframePromptEntry] = []

    for shot in shots.shots:
        scene = scenes_by_id.get(shot.scene_id)
        master_path = masters.get(shot.scene_id)
        rel_master = str(master_path.relative_to(job.root)) if master_path else None
        items.append(
            KeyframePromptEntry(
                shot_id=shot.shot_id,
                scene_id=shot.scene_id,
                start_prompt=build_keyframe_start_prompt(
                    shot,
                    script,
                    scene=scene,
                    scene_master_path=master_path,
                ),
                end_prompt=build_keyframe_end_prompt(
                    shot,
                    script,
                    scene=scene,
                    scene_master_path=master_path,
                ),
                scene_master_path=rel_master,
            )
        )

    document = KeyframePromptsDocument(job_id=job.job_id, items=items)
    job.keyframes_dir.mkdir(parents=True, exist_ok=True)
    prompts_path = keyframe_prompts_path(job)
    write_json(prompts_path, document)
    envelope = timer.envelope(
        status="ok",
        output_artifacts=[
            str(prompts_path.relative_to(job.root)),
            str(keyframe_prompt_report_path(job).relative_to(job.root)),
        ],
    )
    write_stage_report(
        job,
        keyframe_prompt_report_path(job),
        envelope,
        document.model_dump(),
    )
    return document
