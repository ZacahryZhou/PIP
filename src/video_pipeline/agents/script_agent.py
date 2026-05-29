"""Script Agent — produces script.json (mock uses fixtures)."""

from __future__ import annotations

import json
from pathlib import Path

from video_pipeline.schemas import GatewayPayload, ScriptPlan
from video_pipeline.storage import JobPaths, repo_root, write_json


def default_fixtures_dir() -> Path:
    return repo_root() / "tests" / "fixtures"


def run_script_agent(
    job: JobPaths,
    payload: GatewayPayload,
    *,
    mock: bool,
    fixtures_dir: Path | None = None,
) -> ScriptPlan:
    del payload  # real Claude path will use this later
    if not mock:
        raise NotImplementedError("Script Agent requires Claude API; use --mock for local runs")

    fixtures = fixtures_dir or default_fixtures_dir()
    data = json.loads((fixtures / "script.json").read_text(encoding="utf-8"))
    plan = ScriptPlan.model_validate(data)
    write_json(job.script_path, plan)
    return plan
