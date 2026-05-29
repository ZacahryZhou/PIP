"""Tests for CLI orchestrator received stage."""

import json
from pathlib import Path

from video_pipeline.orchestrator import PipelineOrchestrator


def test_run_stop_after_received(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("JOB_STORAGE_DIR", str(tmp_path))
    from video_pipeline.config import Settings

    payload_file = tmp_path / "gateway_payload.json"
    payload_file.write_text(
        json.dumps(
            {
                "raw_prompt": "A short test video",
                "channel": "telegram",
                "user_id": "99",
                "timestamp": "2026-05-28T17:30:00-07:00",
            }
        ),
        encoding="utf-8",
    )

    orchestrator = PipelineOrchestrator(
        Settings(job_storage_dir=str(tmp_path), video_pipeline_mock=True)
    )
    job = orchestrator.run(payload_file, mock=True, stop_after="received")

    assert job.root.is_dir()
    assert job.gateway_payload_path.is_file()
    assert job.job_state_path.is_file()
    assert (job.rules_snapshot_dir / "MASTER.md").is_file()

    state = json.loads(job.job_state_path.read_text(encoding="utf-8"))
    assert state["status"] == "received"
    assert state["current_stage"] == "received"


def test_run_stop_after_routed(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("JOB_STORAGE_DIR", str(tmp_path))
    from video_pipeline.config import Settings
    from video_pipeline.schemas import RoutingPlan, ScriptPlan, ShotsDocument

    fixtures = Path(__file__).parent / "fixtures"
    payload_file = fixtures / "gateway_payload.json"

    orchestrator = PipelineOrchestrator(
        Settings(job_storage_dir=str(tmp_path), video_pipeline_mock=True)
    )
    job = orchestrator.run(payload_file, mock=True, stop_after="routed")

    assert ScriptPlan.model_validate(
        json.loads(job.script_path.read_text(encoding="utf-8"))
    )
    shots = ShotsDocument.model_validate(
        json.loads(job.shots_path.read_text(encoding="utf-8"))
    )
    assert all(shot.preferred_model is None for shot in shots.shots)

    routing = RoutingPlan.model_validate(
        json.loads(job.routing_path.read_text(encoding="utf-8"))
    )
    assert routing.should_continue is True
    assert len(routing.routes) == len(shots.shots)

    state = json.loads(job.job_state_path.read_text(encoding="utf-8"))
    assert state["status"] == "routed"
