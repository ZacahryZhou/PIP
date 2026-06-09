"""Keyframe Prompt Agent — LLM-enhanced start/end prompts with template fallback."""

from __future__ import annotations

from pathlib import Path

from video_pipeline.config import Settings
from video_pipeline.pipeline.prompts import build_keyframe_end_prompt, build_keyframe_start_prompt
from video_pipeline.pipeline.stage_report import StageTimer, write_stage_report
from video_pipeline.schemas import KeyframePromptEntry, KeyframePromptsDocument, ScriptPlan, ShotsDocument
from video_pipeline.storage import JobPaths, repo_root, write_json
from video_pipeline.utils.llm import deepseek_chat_json


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


def _template_entry_for_shot(
    job: JobPaths,
    shot,
    script: ScriptPlan,
    *,
    scenes_by_id: dict,
    masters: dict[str, Path],
) -> KeyframePromptEntry:
    scene = scenes_by_id.get(shot.scene_id)
    master_path = masters.get(shot.scene_id)
    rel_master = str(master_path.relative_to(job.root)) if master_path else None
    return KeyframePromptEntry(
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
        prompt_source="template",
    )


def _build_llm_shot_context(
    shot,
    script: ScriptPlan,
    *,
    scene,
) -> dict[str, object]:
    dialogue = [line.text for line in shot.dialogue] if shot.dialogue else []
    scene_dialogue = [line.text for line in scene.dialogue] if scene and scene.dialogue else []
    return {
        "shot_id": shot.shot_id,
        "scene_id": shot.scene_id,
        "subject": shot.subject,
        "action": shot.action,
        "duration_sec": shot.duration_sec,
        "shot_size": shot.shot_size,
        "camera_angle": shot.camera_angle,
        "camera_move": shot.camera_move,
        "mood": shot.mood,
        "facial_expression": shot.facial_expression,
        "character_gaze": shot.character_gaze,
        "blocking": shot.blocking,
        "keyframe_start_desc": shot.keyframe_start_desc,
        "keyframe_end_desc": shot.keyframe_end_desc,
        "preview_desc": shot.preview_desc,
        "character_prompts": shot.character_prompts,
        "style_tags": shot.style_tags,
        "dialogue": dialogue,
        "scene_location": scene.location if scene else None,
        "scene_time_of_day": scene.time_of_day if scene else None,
        "scene_action_summary": scene.action_summary if scene else None,
        "scene_emotional_beat": scene.emotional_beat if scene else None,
        "scene_dialogue": scene_dialogue,
        "visual_style": script.visual_style,
        "color_tone": script.color_tone,
    }


def _generate_prompts_via_llm(
    job: JobPaths,
    script: ScriptPlan,
    shots: ShotsDocument,
    *,
    scenes_by_id: dict,
    settings: Settings,
) -> dict[str, tuple[str, str]]:
    keyframe_rules = _load_rule(job, "KEYFRAME.md")
    shot_payloads = [
        _build_llm_shot_context(shot, script, scene=scenes_by_id.get(shot.scene_id))
        for shot in shots.shots
    ]
    system_prompt = (
        "You write image-generation prompts for fal.ai Nano Banana Pro (still frames).\n"
        "Return strict JSON only with shape:\n"
        '{"items":[{"shot_id":"shot_001","start_prompt":"...","end_prompt":"..."}]}\n'
        "Rules:\n"
        "- One start_prompt and one end_prompt per shot_id in the input list.\n"
        "- English, concise, cinematic, comma-separated descriptors.\n"
        "- Preserve story facts, characters, location, and dialogue intent.\n"
        "- start_prompt = first frame of the shot; end_prompt = last frame of the shot.\n"
        "- Do not include subtitles, text overlays, or watermarks.\n"
        f"\n{keyframe_rules[:2000]}"
    )
    user_prompt = (
        "Generate provider-ready start/end prompts for each shot.\n"
        f"Script visual_style: {script.visual_style}\n"
        f"Script color_tone: {script.color_tone}\n"
        f"Shots JSON:\n{shot_payloads}"
    )
    data = deepseek_chat_json(
        api_key=settings.deepseek_api_key,
        base_url=settings.deepseek_base_url,
        model=settings.deepseek_model,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
    )
    raw_items = data.get("items")
    if not isinstance(raw_items, list):
        raise ValueError("LLM keyframe prompt response missing items list")

    parsed: dict[str, tuple[str, str]] = {}
    for raw in raw_items:
        if not isinstance(raw, dict):
            continue
        shot_id = raw.get("shot_id")
        start = raw.get("start_prompt")
        end = raw.get("end_prompt")
        if (
            isinstance(shot_id, str)
            and isinstance(start, str)
            and isinstance(end, str)
            and start.strip()
            and end.strip()
        ):
            parsed[shot_id] = (start.strip(), end.strip())
    if not parsed:
        raise ValueError("LLM keyframe prompt response contained no valid items")
    return parsed


def run_keyframe_prompt_agent(
    job: JobPaths,
    script: ScriptPlan,
    shots: ShotsDocument,
    *,
    scene_masters: dict[str, Path] | None = None,
    settings: Settings | None = None,
    mock: bool = False,
) -> KeyframePromptsDocument:
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
    llm_prompts: dict[str, tuple[str, str]] | None = None
    llm_error: str | None = None
    provider_requests = 0

    use_llm = (
        not mock
        and settings is not None
        and bool(settings.deepseek_api_key.strip())
    )
    if use_llm:
        try:
            llm_prompts = _generate_prompts_via_llm(
                job,
                script,
                shots,
                scenes_by_id=scenes_by_id,
                settings=settings,  # type: ignore[arg-type]
            )
            provider_requests = 1
        except Exception as exc:  # noqa: BLE001
            llm_error = str(exc)
            llm_prompts = None

    items: list[KeyframePromptEntry] = []
    for shot in shots.shots:
        template = _template_entry_for_shot(
            job,
            shot,
            script,
            scenes_by_id=scenes_by_id,
            masters=masters,
        )
        if llm_prompts and shot.shot_id in llm_prompts:
            start_prompt, end_prompt = llm_prompts[shot.shot_id]
            items.append(
                template.model_copy(
                    update={
                        "start_prompt": start_prompt,
                        "end_prompt": end_prompt,
                        "prompt_source": "llm",
                    }
                )
            )
        else:
            items.append(template)

    prompt_source_counts = {
        "llm": sum(1 for item in items if item.prompt_source == "llm"),
        "template": sum(1 for item in items if item.prompt_source == "template"),
    }
    document = KeyframePromptsDocument(job_id=job.job_id, items=items)
    job.keyframes_dir.mkdir(parents=True, exist_ok=True)
    prompts_path = keyframe_prompts_path(job)
    write_json(prompts_path, document)
    status = "ok" if not llm_error or prompt_source_counts["llm"] else "ok"
    envelope = timer.envelope(
        status=status,  # type: ignore[arg-type]
        output_artifacts=[
            str(prompts_path.relative_to(job.root)),
            str(keyframe_prompt_report_path(job).relative_to(job.root)),
        ],
        errors=[llm_error] if llm_error else [],
        provider_request_count=provider_requests,
    )
    write_stage_report(
        job,
        keyframe_prompt_report_path(job),
        envelope,
        {
            **document.model_dump(),
            "prompt_source_counts": prompt_source_counts,
            "llm_fallback_reason": llm_error,
        },
    )
    return document
