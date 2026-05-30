"""Script Agent — produces script.json (mock uses fixtures, else DeepSeek)."""

from __future__ import annotations

import json
from pathlib import Path

from video_pipeline.config import Settings, settings
from video_pipeline.schemas import GatewayPayload, ScriptPlan
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


def _build_script_prompts(job: JobPaths, payload: GatewayPayload) -> tuple[str, str]:
    director = _load_rule(job, "DIRECTOR.md")
    master = _load_rule(job, "MASTER.md")
    visual = _load_rule(job, "VISUAL.md")
    characters = _load_rule(job, "CHARACTERS.md")
    music_library = _load_rule(job, "MUSIC_LIBRARY.md")
    system = (
        "You are the Script Agent for PIP — an award-winning short-form film director. "
        "Plan scene-level story, staging, emotional beats, and camera intent. "
        "Output one strict JSON object only.\n\n"
        f"{director}\n\n{master}\n\n{visual}\n\n{music_library}\n\n{characters}"
    )
    user = (
        f"User request:\n{payload.raw_prompt}\n\n"
        f"Channel: {payload.channel}\n\n"
        "Steps:\n"
        "1. Infer the core story and emotional arc from the user request.\n"
        "2. Choose characters from CHARACTERS.md (or define a new id if needed).\n"
        "3. Write each scene with concrete visible action, emotional_beat, director_notes, camera_notes.\n"
        "4. Return JSON matching the MASTER contract."
    )
    return system, user


def run_script_agent(
    job: JobPaths,
    payload: GatewayPayload,
    *,
    mock: bool,
    fixtures_dir: Path | None = None,
    app_settings: Settings | None = None,
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

    system, user = _build_script_prompts(job, payload)
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
