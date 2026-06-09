"""Keyframe prompt agent and start/end keyframe tests."""

import json
import shutil
from pathlib import Path

import pytest

from video_pipeline.config import Settings
from video_pipeline.orchestrator import PipelineOrchestrator
from video_pipeline.pipeline.approval import load_preview_document
from video_pipeline.pipeline.keyframe_generation import (
    keyframe_end_path,
    keyframe_start_path,
    load_keyframe_prompts,
    run_keyframe_generation,
)
from video_pipeline.providers.capabilities import resolve_generation_mode
from video_pipeline.schemas import ScriptPlan, ShotsDocument


FIXTURES_DIR = Path(__file__).parent / "fixtures"


def test_keyframe_prompts_artifact_written(tmp_path: Path) -> None:
    orchestrator = PipelineOrchestrator(Settings(job_storage_dir=str(tmp_path)))
    job = orchestrator.run(
        FIXTURES_DIR / "gateway_payload.json",
        mock=True,
        stop_after="keyframes",
        require_approval=False,
    )

    prompts = load_keyframe_prompts(job)
    assert prompts is not None
    assert len(prompts.items) == 6
    assert (job.keyframes_dir / "keyframe_prompts.json").is_file()
    assert "first frame of shot" in prompts.items[1].start_prompt
    assert "last frame of shot" in prompts.items[1].end_prompt


def test_resolve_generation_mode_fallback() -> None:
    mode, reason = resolve_generation_mode("first_last_frame", "wan_t2v")
    assert mode == "t2v"
    assert "fallback" in reason

    mode, _ = resolve_generation_mode("first_last_frame", "kling")
    assert mode == "first_last_frame"


def test_start_end_keyframes_for_first_last_shots(tmp_path: Path) -> None:
    orchestrator = PipelineOrchestrator(Settings(job_storage_dir=str(tmp_path)))
    job = orchestrator.run(
        FIXTURES_DIR / "gateway_payload.json",
        mock=True,
        stop_after="keyframes",
        require_approval=False,
    )

    report = json.loads((job.reports_dir / "keyframe_report.json").read_text(encoding="utf-8"))
    fl = [item for item in report["results"] if item["generation_mode"] == "first_last_frame"]
    assert len(fl) == 6
    for item in fl:
        assert item["status"] == "success"
        assert item["start_frame_path"]
        assert item["end_frame_path"]
        assert Path(item["start_frame_path"]).name.endswith("_start.png")
        assert keyframe_start_path(job, item["shot_id"]).is_file()
        assert keyframe_end_path(job, item["shot_id"]).is_file()


def test_preview_reused_as_start_when_available(tmp_path: Path) -> None:
    if shutil.which("ffmpeg") is None:
        pytest.skip("ffmpeg not available")

    orchestrator = PipelineOrchestrator(Settings(job_storage_dir=str(tmp_path)))
    job = orchestrator.run(
        FIXTURES_DIR / "gateway_payload.json",
        mock=True,
        require_approval=True,
    )
    preview = load_preview_document(job)
    preview_item = preview.items[1]
    preview_bytes = (job.root / preview_item.preview_image_path).read_bytes()

    orchestrator.approve_job(job, preview_version=preview.preview_version)
    job = orchestrator.continue_after_approval(job, mock=True, stop_after="keyframes")

    report = json.loads((job.reports_dir / "keyframe_report.json").read_text(encoding="utf-8"))
    reused = next(item for item in report["results"] if item["shot_id"] == preview_item.shot_id)
    assert reused["reused_preview_as_start"] is True
    assert keyframe_start_path(job, preview_item.shot_id).read_bytes() == preview_bytes
