"""Tests for job folder layout and rules snapshot."""

import json
from datetime import datetime, timezone
from pathlib import Path

from video_pipeline.schemas import GatewayPayload, JobState
from video_pipeline.storage import (
    copy_rules_snapshot,
    create_job_paths,
    ensure_job_layout,
    save_gateway_payload,
    save_job_state,
)


def test_ensure_job_layout_creates_subdirs(tmp_path: Path) -> None:
    job = ensure_job_layout(create_job_paths(tmp_path, job_id="job_test_layout"))
    for name in (
        "input",
        "rules_snapshot",
        "script",
        "storyboard",
        "routing",
        "clips/raw",
        "clips/validated",
        "reports",
        "final",
    ):
        assert (job.root / name).is_dir()


def test_save_gateway_payload_and_rules_snapshot(tmp_path: Path) -> None:
    job = ensure_job_layout(create_job_paths(tmp_path, job_id="job_test_artifacts"))
    payload = GatewayPayload.model_validate(
        {
            "raw_prompt": "test",
            "channel": "telegram",
            "user_id": "1",
            "timestamp": "2026-05-28T17:30:00-07:00",
        }
    )
    save_gateway_payload(job.gateway_payload_path, payload)
    copied = copy_rules_snapshot(job.root)
    assert job.gateway_payload_path.is_file()
    assert len(copied) >= 1
    assert (job.rules_snapshot_dir / "MASTER.md").is_file()


def test_save_job_state(tmp_path: Path) -> None:
    job = ensure_job_layout(create_job_paths(tmp_path, job_id="job_test_state"))
    state = JobState(
        job_id=job.job_id,
        status="received",
        updated_at=datetime.now(timezone.utc),
        current_stage="received",
    )
    save_job_state(job.job_state_path, state)
    loaded = json.loads(job.job_state_path.read_text(encoding="utf-8"))
    assert loaded["status"] == "received"
