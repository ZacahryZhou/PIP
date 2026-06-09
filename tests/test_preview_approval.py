"""Storyboard preview and approval gate tests."""

import json
import shutil
from pathlib import Path

import pytest

from video_pipeline.config import Settings
from video_pipeline.orchestrator import PipelineOrchestrator
from video_pipeline.pipeline.approval import load_approval_document, load_preview_document
from video_pipeline.pipeline.delivery import build_preview_callback, parse_preview_callback
from video_pipeline.pipeline.storyboard_preview import run_storyboard_preview
from video_pipeline.schemas import ScriptPlan, ShotsDocument


FIXTURES_DIR = Path(__file__).parent / "fixtures"


def test_preview_callback_roundtrip() -> None:
    data = build_preview_callback("approve", "job_20260530_010101", 2)
    assert parse_preview_callback(data) == ("approve", "job_20260530_010101", 2)
    assert parse_preview_callback("invalid") is None


def test_mock_storyboard_preview_writes_manifest(tmp_path: Path) -> None:
    if shutil.which("ffmpeg") is None:
        pytest.skip("ffmpeg not available")

    orchestrator = PipelineOrchestrator(Settings(job_storage_dir=str(tmp_path)))
    job = orchestrator.run(
        FIXTURES_DIR / "gateway_payload.json",
        mock=True,
        stop_after="storyboarded",
        require_approval=False,
    )
    script = ScriptPlan.model_validate_json(job.script_path.read_text(encoding="utf-8"))
    shots = ShotsDocument.model_validate_json(job.shots_path.read_text(encoding="utf-8"))

    preview = run_storyboard_preview(
        job,
        script,
        shots,
        settings=Settings(job_storage_dir=str(tmp_path)),
        mock=True,
    )

    assert preview.preview_version == 1
    assert len(preview.items) == 6
    assert job.storyboard_preview_path.is_file()
    assert (job.reports_dir / "preview_report.json").is_file()
    for item in preview.items:
        assert (job.root / item.preview_image_path).is_file()
        assert (job.root / item.start_image_path).is_file()
        assert (job.root / item.end_image_path).is_file()


def test_orchestrator_stops_at_approval_without_routing(tmp_path: Path) -> None:
    orchestrator = PipelineOrchestrator(Settings(job_storage_dir=str(tmp_path)))
    job = orchestrator.run(
        FIXTURES_DIR / "gateway_payload.json",
        mock=True,
        require_approval=True,
    )

    state = json.loads(job.job_state_path.read_text(encoding="utf-8"))
    assert state["status"] == "awaiting_storyboard_approval"
    assert job.storyboard_preview_path.is_file()
    assert not job.routing_path.is_file()
    assert not list(job.clips_raw_dir.glob("*.mp4"))

    approval = load_approval_document(job)
    assert approval is not None
    assert approval.status == "pending"
    load_preview_document(job)


def test_orchestrator_resume_after_approval_delivers(tmp_path: Path) -> None:
    if shutil.which("ffmpeg") is None:
        pytest.skip("ffmpeg not available")

    orchestrator = PipelineOrchestrator(Settings(job_storage_dir=str(tmp_path)))
    job = orchestrator.run(
        FIXTURES_DIR / "gateway_payload.json",
        mock=True,
        require_approval=True,
    )
    preview = load_preview_document(job)
    orchestrator.approve_job(job, preview_version=preview.preview_version)
    job = orchestrator.continue_after_approval(job, mock=True)

    state = json.loads(job.job_state_path.read_text(encoding="utf-8"))
    assert state["status"] == "delivered"
    assert job.final_dir.joinpath("final.mp4").is_file()
    assert job.routing_path.is_file()


def test_stop_after_preview_ready(tmp_path: Path) -> None:
    orchestrator = PipelineOrchestrator(Settings(job_storage_dir=str(tmp_path)))
    job = orchestrator.run(
        FIXTURES_DIR / "gateway_payload.json",
        mock=True,
        stop_after="preview_ready",
        require_approval=True,
    )

    state = json.loads(job.job_state_path.read_text(encoding="utf-8"))
    assert state["status"] == "preview_ready"
    assert load_approval_document(job) is None


def test_revise_storyboard_increments_preview_version(tmp_path: Path) -> None:
    orchestrator = PipelineOrchestrator(Settings(job_storage_dir=str(tmp_path)))
    job = orchestrator.run(
        FIXTURES_DIR / "gateway_payload.json",
        mock=True,
        require_approval=True,
    )
    preview_v1 = load_preview_document(job)
    orchestrator.request_revision(job, preview_version=preview_v1.preview_version)

    job = orchestrator.revise_storyboard(job, "Make shots wider and slower.", mock=True)
    preview_v2 = load_preview_document(job)

    assert preview_v2.preview_version == preview_v1.preview_version + 1
    state = json.loads(job.job_state_path.read_text(encoding="utf-8"))
    assert state["status"] == "awaiting_storyboard_approval"
    approval = load_approval_document(job)
    assert approval is not None
    assert approval.status == "pending"
    assert approval.revision_count == 1
