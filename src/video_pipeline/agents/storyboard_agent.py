"""Storyboard Agent — produces shots.json (mock uses fixtures)."""

from __future__ import annotations

import json
from pathlib import Path

from video_pipeline.schemas import ScriptPlan, ShotsDocument
from video_pipeline.storage import JobPaths, repo_root, write_json

from video_pipeline.agents.script_agent import default_fixtures_dir


def run_storyboard_agent(
    job: JobPaths,
    script: ScriptPlan,
    *,
    mock: bool,
    fixtures_dir: Path | None = None,
) -> ShotsDocument:
    del script  # real Claude path will use this later
    if not mock:
        raise NotImplementedError(
            "Storyboard Agent requires Claude API; use --mock for local runs"
        )

    fixtures = fixtures_dir or default_fixtures_dir()
    data = json.loads((fixtures / "shots.json").read_text(encoding="utf-8"))
    document = ShotsDocument.model_validate(data)
    write_json(job.shots_path, document)
    return document
