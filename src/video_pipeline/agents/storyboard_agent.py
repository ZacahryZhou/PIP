"""Storyboard Agent — produces shots.json (mock uses fixtures, else DeepSeek)."""

from __future__ import annotations

import json
from pathlib import Path

from video_pipeline.config import Settings, settings
from video_pipeline.schemas import ScriptPlan, ShotsDocument
from video_pipeline.storage import JobPaths, repo_root, write_json
from video_pipeline.utils.llm import deepseek_chat_json

from video_pipeline.agents.script_agent import default_fixtures_dir, _load_rule


def _build_storyboard_prompts(job: JobPaths, script: ScriptPlan) -> tuple[str, str]:
    storyboard_rules = _load_rule(job, "STORYBOARD.md")
    script_json = script.model_dump_json(indent=2)
    system = (
        "You are the Storyboard Agent for the PIP text-to-video pipeline. "
        "Split the script into shots and output strict JSON only.\n\n"
        f"{storyboard_rules}"
    )
    user = (
        "Convert this script plan into a shots document.\n"
        "Set preferred_model and fallback_model to null for every shot.\n"
        "Total shot durations must match the script within 1 second.\n\n"
        f"{script_json}"
    )
    return system, user


def run_storyboard_agent(
    job: JobPaths,
    script: ScriptPlan,
    *,
    mock: bool,
    fixtures_dir: Path | None = None,
    app_settings: Settings | None = None,
) -> ShotsDocument:
    if mock:
        fixtures = fixtures_dir or default_fixtures_dir()
        data = json.loads((fixtures / "shots.json").read_text(encoding="utf-8"))
        document = ShotsDocument.model_validate(data)
        write_json(job.shots_path, document)
        return document

    cfg = app_settings or settings
    if not cfg.deepseek_api_key:
        raise ValueError(
            "DEEPSEEK_API_KEY is required. Set it in .env or use --mock for local fixtures."
        )

    system, user = _build_storyboard_prompts(job, script)
    data = deepseek_chat_json(
        api_key=cfg.deepseek_api_key,
        base_url=cfg.deepseek_base_url,
        model=cfg.deepseek_model,
        system_prompt=system,
        user_prompt=user,
    )
    document = ShotsDocument.model_validate(data)
    write_json(job.shots_path, document)
    return document
