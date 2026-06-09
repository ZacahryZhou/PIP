"""Resume logic and stage report tests."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from video_pipeline.config import Settings
from video_pipeline.orchestrator import PipelineOrchestrator, RESUMABLE_STATUSES
from video_pipeline.pipeline.approval import load_approval_document
from video_pipeline.pipeline.generation import run_generation
from video_pipeline.pipeline.resume import (
    load_routing_plan,
    scene_maps_complete,
    validated_clips_complete,
)
from video_pipeline.pipeline.scene_maps import run_scene_maps
from video_pipeline.schemas import GatewayPayload, RoutingPlan, ScriptPlan, ShotsDocument
from video_pipeline.schemas.intake import IntakePlan
from video_pipeline.schemas.plot import PlotPlan
from video_pipeline.storage import create_job_paths, ensure_job_layout, resolve_storage_root

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def _load_script_shots_payload(job):
    script = ScriptPlan.model_validate_json(job.script_path.read_text(encoding="utf-8"))
    shots = ShotsDocument.model_validate_json(job.shots_path.read_text(encoding="utf-8"))
    payload = GatewayPayload.model_validate_json(job.gateway_payload_path.read_text(encoding="utf-8"))
    return script, shots, payload


def _load_job_inputs(job):
    script, shots, payload = _load_script_shots_payload(job)
    routing = RoutingPlan.model_validate_json(job.routing_path.read_text(encoding="utf-8"))
    return script, shots, payload, routing


def test_scene_maps_resume_skips_existing_masters(tmp_path: Path) -> None:
    orchestrator = PipelineOrchestrator(Settings(job_storage_dir=str(tmp_path)))
    job = orchestrator.run(
        FIXTURES_DIR / "gateway_payload.json",
        mock=True,
        stop_after="scripted",
        require_approval=False,
    )
    script = ScriptPlan.model_validate_json(job.script_path.read_text(encoding="utf-8"))
    payload = GatewayPayload.model_validate_json(job.gateway_payload_path.read_text(encoding="utf-8"))
    settings = Settings(job_storage_dir=str(tmp_path))
    intake_plan = IntakePlan.model_validate_json(job.intake_plan_path.read_text(encoding="utf-8"))
    plot_plan = PlotPlan.model_validate_json(job.plot_plan_path.read_text(encoding="utf-8"))

    first = run_scene_maps(
        job,
        payload,
        intake_plan=intake_plan,
        plot_plan=plot_plan,
        script=script,
        settings=settings,
        mock=True,
    )
    first_report = json.loads((job.reports_dir / "scene_map_report.json").read_text(encoding="utf-8"))
    assert first_report.get("resumed") is False

    second = run_scene_maps(
        job,
        payload,
        intake_plan=intake_plan,
        plot_plan=plot_plan,
        script=script,
        settings=settings,
        mock=True,
    )
    second_report = json.loads((job.reports_dir / "scene_map_report.json").read_text(encoding="utf-8"))

    assert scene_maps_complete(job, script)
    assert second_report["resumed"] is True
    assert second_report["provider_request_count"] == 0
    assert len(second.entries) == len(first.entries)


def test_generation_resume_skips_existing_clips(tmp_path: Path) -> None:
    if shutil.which("ffmpeg") is None:
        pytest.skip("ffmpeg not available")

    orchestrator = PipelineOrchestrator(Settings(job_storage_dir=str(tmp_path)))
    job = orchestrator.run(
        FIXTURES_DIR / "gateway_payload.json",
        mock=True,
        stop_after="keyframes",
        require_approval=False,
    )
    script, shots, _, routing = _load_job_inputs(job)
    settings = Settings(job_storage_dir=str(tmp_path))

    first = run_generation(job, script, shots, routing, settings=settings, mock=True)
    first_report = json.loads((job.reports_dir / "generation_report.json").read_text(encoding="utf-8"))
    assert first_report.get("resumed") is False

    second = run_generation(job, script, shots, routing, settings=settings, mock=True)
    second_report = json.loads((job.reports_dir / "generation_report.json").read_text(encoding="utf-8"))

    assert second_report["resumed"] is True
    assert second_report["provider_request_count"] == 0
    assert second.succeeded_shot_ids == first.succeeded_shot_ids


def test_resume_job_from_scene_maps_ready(tmp_path: Path) -> None:
    if shutil.which("ffmpeg") is None:
        pytest.skip("ffmpeg not available")

    orchestrator = PipelineOrchestrator(Settings(job_storage_dir=str(tmp_path)))
    job = orchestrator.run(
        FIXTURES_DIR / "gateway_payload.json",
        mock=True,
        stop_after="scene_maps_ready",
        require_approval=False,
    )

    resumed = orchestrator.resume_job(job, mock=True)
    state = json.loads(resumed.job_state_path.read_text(encoding="utf-8"))
    assert state["status"] == "delivered"
    assert validated_clips_complete(resumed, ShotsDocument.model_validate_json(resumed.shots_path.read_text()))
    routing_report = json.loads(resumed.routing_path.read_text(encoding="utf-8"))
    assert routing_report["should_continue"] is True
    assert load_routing_plan(resumed) is not None


def test_resume_job_after_approval_uses_existing_routing(tmp_path: Path) -> None:
    if shutil.which("ffmpeg") is None:
        pytest.skip("ffmpeg not available")

    orchestrator = PipelineOrchestrator(Settings(job_storage_dir=str(tmp_path)))
    job = orchestrator.run(
        FIXTURES_DIR / "gateway_payload.json",
        mock=True,
        require_approval=True,
    )
    preview = json.loads(job.storyboard_preview_path.read_text(encoding="utf-8"))
    orchestrator.approve_job(job, preview_version=preview["preview_version"])
    job = orchestrator.resume_job(job, mock=True)

    state = json.loads(job.job_state_path.read_text(encoding="utf-8"))
    assert state["status"] == "delivered"
    assert load_approval_document(job) is not None


def test_stage_reports_include_envelope_fields(tmp_path: Path) -> None:
    orchestrator = PipelineOrchestrator(Settings(job_storage_dir=str(tmp_path)))
    job = orchestrator.run(
        FIXTURES_DIR / "gateway_payload.json",
        mock=True,
        stop_after="scene_maps_ready",
        require_approval=False,
    )
    report = json.loads((job.reports_dir / "scene_map_report.json").read_text(encoding="utf-8"))
    for field in (
        "job_id",
        "stage",
        "status",
        "started_at",
        "finished_at",
        "duration_ms",
        "input_artifacts",
        "output_artifacts",
    ):
        assert field in report


def test_resume_status_set_covers_post_approval_states() -> None:
    assert "storyboard_approved" in RESUMABLE_STATUSES
    assert "failed_qc" in RESUMABLE_STATUSES
    assert "failed_generation" in RESUMABLE_STATUSES
    assert "scripted" in RESUMABLE_STATUSES
    assert "storyboarded" in RESUMABLE_STATUSES


def test_resume_job_from_scripted(tmp_path: Path) -> None:
    if shutil.which("ffmpeg") is None:
        pytest.skip("ffmpeg not available")

    orchestrator = PipelineOrchestrator(Settings(job_storage_dir=str(tmp_path)))
    job = orchestrator.run(
        FIXTURES_DIR / "gateway_payload.json",
        mock=True,
        stop_after="scripted",
        require_approval=False,
    )
    state = json.loads(job.job_state_path.read_text(encoding="utf-8"))
    assert state["status"] in {"scripted", "reference_assets_ready"}
    assert not job.shots_path.is_file()

    resumed = orchestrator.resume_job(job, mock=True, require_approval=False)
    state = json.loads(resumed.job_state_path.read_text(encoding="utf-8"))
    assert state["status"] == "delivered"
    assert resumed.shots_path.is_file()


def test_resume_job_from_storyboarded(tmp_path: Path) -> None:
    orchestrator = PipelineOrchestrator(Settings(job_storage_dir=str(tmp_path)))
    job = orchestrator.run(
        FIXTURES_DIR / "gateway_payload.json",
        mock=True,
        stop_after="storyboarded",
        require_approval=False,
    )
    state = json.loads(job.job_state_path.read_text(encoding="utf-8"))
    assert state["status"] == "storyboarded"
    assert job.shots_path.is_file()

    resumed = orchestrator.resume_job(job, mock=True, require_approval=False)
    state = json.loads(resumed.job_state_path.read_text(encoding="utf-8"))
    assert state["status"] == "delivered"
