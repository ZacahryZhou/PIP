"""Storyboard Agent — produces shots.json (mock uses fixtures, else DeepSeek)."""

from __future__ import annotations

import json
from pathlib import Path

from video_pipeline.config import Settings, settings
from video_pipeline.schemas import ScriptPlan, ShotsDocument
from video_pipeline.schemas.intake import IntakePlan, SceneShotHint
from video_pipeline.storage import JobPaths, repo_root, write_json
from video_pipeline.utils.llm import deepseek_chat_json

from pydantic import ValidationError

from video_pipeline.agents.script_agent import _load_rule, default_fixtures_dir
from video_pipeline.pipeline.storyboard_validation import validate_storyboard_logic


def _format_scene_shot_hints(hints: list[SceneShotHint]) -> str:
    if not hints:
        return ""
    lines = ["Scene shot hints from Intake (must align shot count and camera progression):"]
    for hint in hints:
        lines.append(
            f"- {hint.scene_id}: {hint.expected_shots} shots; "
            f"camera={hint.camera_progression}; "
            f"characters={', '.join(hint.linked_character_ids) or 'none'}"
        )
    return "\n".join(lines)


def _record_scene_shot_hints(job: JobPaths, hints: list[SceneShotHint]) -> None:
    if not hints:
        return
    write_json(job.storyboard_dir / "scene_shot_hints.json", [hint.model_dump() for hint in hints])


def _build_storyboard_prompts(
    job: JobPaths,
    script: ScriptPlan,
    *,
    intake_plan: IntakePlan | None = None,
    revision_notes: str | None = None,
) -> tuple[str, str]:
    director = _load_rule(job, "DIRECTOR.md")
    storyboard_rules = _load_rule(job, "STORYBOARD.md")
    keyframe_rules = _load_rule(job, "KEYFRAME.md")
    visual = _load_rule(job, "VISUAL.md")
    characters = _load_rule(job, "CHARACTERS.md")
    script_json = script.model_dump_json(indent=2)
    system = (
        "You are the Storyboard Agent for PIP — a professional director breaking scenes into shots. "
        "Work scene-first: for each scene_id split ordered shots with continuity, camera progression, "
        "and emotion transition. Output strict JSON only.\n\n"
        f"{director}\n\n{storyboard_rules}\n\n{keyframe_rules}\n\n{visual}\n\n{characters}"
    )
    user = (
        "Convert this script plan into a shots document.\n"
        "Rules:\n"
        "- Respect scene_list order; set scene_order and shot_order_in_scene per shot.\n"
        "- Every shot after the first in a scene needs shot_continuity_from_previous.\n"
        "- Bind visual_style/color_palette to each scene's script values.\n"
        "- Set preview_desc, keyframe_start_desc, keyframe_end_desc per shot.\n"
        "- Set preferred_model and fallback_model to null for every shot.\n"
        "- Total shot durations must match script.total_duration_sec within 1 second.\n"
        "- Per scene duration must match script scene duration within 0.5 seconds.\n"
        "- Use varied shot_size across each scene (e.g. WS then CU).\n"
        "- Every character shot needs facial_expression, character_gaze, blocking.\n"
        "- In character_prompts, inherit script.color_tone as a short color anchor per VISUAL.md.\n"
        "- For each shot set generation_mode to t2v or i2v and generation_mode_reason (English).\n"
        "- Prefer i2v for CU/MCU/MS character shots with dialogue or low/medium motion.\n"
        "- Prefer t2v for high motion_intensity, EWS/WS establishing, or large camera travel.\n\n"
        f"{script_json}"
    )
    if intake_plan and intake_plan.scene_shot_hints:
        user += f"\n\n{_format_scene_shot_hints(intake_plan.scene_shot_hints)}\n"
    if revision_notes:
        user += (
            "\n\nUser revision notes — update the storyboard only; keep script.json scenes intact:\n"
            f"{revision_notes.strip()}\n"
        )
    return system, user


def run_storyboard_agent(
    job: JobPaths,
    script: ScriptPlan,
    *,
    mock: bool,
    fixtures_dir: Path | None = None,
    app_settings: Settings | None = None,
    revision_notes: str | None = None,
    intake_plan: IntakePlan | None = None,
) -> ShotsDocument:
    if intake_plan is None and job.intake_plan_path.is_file():
        intake_plan = IntakePlan.model_validate_json(
            job.intake_plan_path.read_text(encoding="utf-8")
        )
    if mock:
        fixtures = fixtures_dir or default_fixtures_dir()
        data = json.loads((fixtures / "shots.json").read_text(encoding="utf-8"))
        document = ShotsDocument.model_validate(data)
        logic_errors = validate_storyboard_logic(script, document)
        if logic_errors:
            raise ValueError("Fixture shots failed storyboard logic validation: " + "; ".join(logic_errors))
        if intake_plan and intake_plan.scene_shot_hints:
            _record_scene_shot_hints(job, intake_plan.scene_shot_hints)
        write_json(job.shots_path, document)
        return document

    cfg = app_settings or settings
    if not cfg.deepseek_api_key:
        raise ValueError(
            "DEEPSEEK_API_KEY is required. Set it in .env or use --mock for local fixtures."
        )

    system, user = _build_storyboard_prompts(
        job, script, intake_plan=intake_plan, revision_notes=revision_notes
    )
    last_error: str | None = None
    document: ShotsDocument | None = None
    for attempt in range(2):
        user_prompt = user
        if last_error:
            user_prompt = (
                f"{user}\n\nPrevious JSON failed validation:\n{last_error}\n"
                "Fix every invalid shot and return strict JSON only."
            )
        data = deepseek_chat_json(
            api_key=cfg.deepseek_api_key,
            base_url=cfg.deepseek_base_url,
            model=cfg.deepseek_model,
            system_prompt=system,
            user_prompt=user_prompt,
        )
        try:
            document = ShotsDocument.model_validate(data)
            logic_errors = validate_storyboard_logic(script, document)
            if logic_errors:
                last_error = "; ".join(logic_errors)
                if attempt == 1:
                    raise ValueError(last_error)
                continue
            break
        except ValidationError as exc:
            last_error = str(exc)
            if attempt == 1:
                raise

    if document is None:
        raise RuntimeError("Storyboard agent failed to produce a valid shots document")
    if intake_plan and intake_plan.scene_shot_hints:
        _record_scene_shot_hints(job, intake_plan.scene_shot_hints)
    write_json(job.shots_path, document)
    return document
