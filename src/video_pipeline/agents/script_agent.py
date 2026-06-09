"""Script Agent — produces script.json (mock uses fixtures, else DeepSeek)."""

from __future__ import annotations

import json
from pathlib import Path

from video_pipeline.config import Settings, settings
from video_pipeline.schemas import GatewayPayload, ScriptPlan
from video_pipeline.schemas.intake import IntakePlan
from video_pipeline.schemas.plot import PlotPlan
from video_pipeline.storage import JobPaths, repo_root, write_json
from video_pipeline.utils.llm import deepseek_chat_json


def default_fixtures_dir() -> Path:
    return repo_root() / "tests" / "fixtures"


def _load_rule(job: JobPaths, name: str) -> str:
    path = job.rules_snapshot_dir / name
    if path.is_file():
        return path.read_text(encoding="utf-8")
    fallback = repo_root() / "rules" / name
    return fallback.read_text(encoding="utf-8") if fallback.is_file() else ""


def _build_script_prompts(
    job: JobPaths,
    payload: GatewayPayload,
    intake_plan: IntakePlan | None = None,
    plot_plan: PlotPlan | None = None,
) -> tuple[str, str]:
    director = _load_rule(job, "DIRECTOR.md")
    master = _load_rule(job, "MASTER.md")
    visual = _load_rule(job, "VISUAL.md")
    characters = _load_rule(job, "CHARACTERS.md")
    music_library = _load_rule(job, "MUSIC_LIBRARY.md")
    system = (
        "You are the Script Agent for PIP — an award-winning short-form film director. "
        "Plan scene-level story first, then lock dialogue intent inside each scene. "
        "Output one strict JSON object only.\n\n"
        f"{director}\n\n{master}\n\n{visual}\n\n{music_library}\n\n{characters}"
    )
    if payload.has_script and payload.user_script_text:
        user = (
            "The user supplied a script. Normalize it into the MASTER JSON contract without "
            "changing story meaning.\n\n"
            f"User script:\n{payload.user_script_text}\n\n"
            f"Channel: {payload.channel}\n"
            f"Language: {payload.language}\n\n"
            "Steps:\n"
            "1. Split into scene_list with scene_order, scene_purpose, emotional arc per scene.\n"
            "2. Lock dialogue lines with start_sec/end_sec inside each scene.\n"
            "3. Set visual_style, color_palette, camera_intent per scene.\n"
            "4. Return JSON matching the MASTER contract."
        )
    else:
        user = (
            f"User request:\n{payload.raw_prompt}\n\n"
            f"Channel: {payload.channel}\n"
            f"Language: {payload.language}\n\n"
            "Steps:\n"
            "1. Define scene_list first (scene_order, scene_purpose, emotion_start/end).\n"
            "2. Choose characters from CHARACTERS.md (or define a new id if needed).\n"
            "3. Write each scene with action_summary, dialogue_intent, camera_intent, director_notes.\n"
            "4. Return JSON matching the MASTER contract."
        )
    if payload.style_preset or payload.style_notes:
        user += (
            f"\n\nStyle preset: {payload.style_preset or 'none'}\n"
            f"Style notes: {payload.style_notes or 'none'}"
        )
    if payload.target_duration_sec:
        user += f"\nTarget duration: {payload.target_duration_sec} seconds."
    if intake_plan and intake_plan.characters_for_script:
        user += (
            "\n\nIntake constraint: characters_in_use MUST be exactly this list "
            f"(no extra catalog defaults like hero): "
            f"{', '.join(intake_plan.characters_for_script)}"
        )
    if intake_plan and intake_plan.script_brief.strip():
        user += f"\n\nIntake script brief:\n{intake_plan.script_brief}"
    if plot_plan is not None:
        user += f"\n\nPlot Agent handoff (scene structure, style, camera, dialogue intent):\n{plot_plan.script_handoff}"
        if plot_plan.gaps_found:
            user += "\n\nPlot gaps to resolve in script output:\n" + "\n".join(
                f"- {gap}" for gap in plot_plan.gaps_found
            )
    return system, user


def run_script_agent(
    job: JobPaths,
    payload: GatewayPayload,
    *,
    mock: bool,
    fixtures_dir: Path | None = None,
    app_settings: Settings | None = None,
    intake_plan: IntakePlan | None = None,
    plot_plan: PlotPlan | None = None,
) -> ScriptPlan:
    if mock:
        fixtures = fixtures_dir or default_fixtures_dir()
        data = json.loads((fixtures / "script.json").read_text(encoding="utf-8"))
        plan = ScriptPlan.model_validate(data)
        write_json(job.script_path, plan)
        return plan

    cfg = app_settings or settings
    if not cfg.deepseek_api_key:
        raise ValueError(
            "DEEPSEEK_API_KEY is required. Set it in .env or use --mock for local fixtures."
        )

    system, user = _build_script_prompts(
        job, payload, intake_plan=intake_plan, plot_plan=plot_plan
    )
    data = deepseek_chat_json(
        api_key=cfg.deepseek_api_key,
        base_url=cfg.deepseek_base_url,
        model=cfg.deepseek_model,
        system_prompt=system,
        user_prompt=user,
    )
    plan = ScriptPlan.model_validate(data)
    write_json(job.script_path, plan)
    return plan
