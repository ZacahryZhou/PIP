"""Tests for Ring 1 Intake Agent and clarification flow."""

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from video_pipeline.agents.intake_agent import detect_intake_gaps, run_intake_agent
from video_pipeline.agents.intake_clarification_agent import format_intake_clarification_message
from video_pipeline.orchestrator import PipelineOrchestrator
from video_pipeline.pipeline.intake import (
    apply_intake_resolutions,
    load_intake_clarification,
    load_intake_plan,
    parse_intake_clarification_reply,
)
from video_pipeline.schemas import GatewayPayload, IntakeGapResolution
from video_pipeline.storage import create_job_paths, ensure_job_layout, resolve_storage_root


def _payload(**overrides) -> GatewayPayload:
    base = {
        "raw_prompt": "Coffeefee healing short",
        "channel": "telegram",
        "user_id": "test",
        "timestamp": datetime.now(timezone.utc),
        "character_ids": ["coffeefee"],
    }
    base.update(overrides)
    return GatewayPayload.model_validate(base)


def test_detect_missing_character_reference_gap(tmp_path: Path) -> None:
    job = ensure_job_layout(create_job_paths(resolve_storage_root(str(tmp_path))))
    gaps = detect_intake_gaps(job, _payload())
    kinds = {gap.kind for gap in gaps}
    assert "character_reference" in kinds


def test_intake_clarification_message_lists_choices(tmp_path: Path) -> None:
    job = ensure_job_layout(create_job_paths(resolve_storage_root(str(tmp_path))))
    analysis = run_intake_agent(job, _payload())
    message = format_intake_clarification_message(list(analysis.gaps))
    assert "generate" in message
    assert "supplement" in message
    assert "intake done" in message


def test_parse_intake_clarification_reply() -> None:
    command, resolutions = parse_intake_clarification_reply("generate gap_1\nintake done")
    assert command == "done"
    assert len(resolutions) == 1
    assert resolutions[0].gap_id == "gap_1"

    command, resolutions = parse_intake_clarification_reply("generate 1")
    assert command == "partial"
    assert resolutions[0].gap_id == "gap_1"
    assert resolutions[0].choice == "system_generate"


def test_orchestrator_pauses_for_intake_clarification(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("JOB_STORAGE_DIR", str(tmp_path))
    from video_pipeline.config import Settings

    payload_file = tmp_path / "payload.json"
    payload_file.write_text(
        json.dumps(
            {
                "raw_prompt": "Coffeefee short",
                "channel": "telegram",
                "user_id": "1",
                "timestamp": "2026-06-08T12:00:00-07:00",
                "character_ids": ["coffeefee"],
            }
        ),
        encoding="utf-8",
    )

    orchestrator = PipelineOrchestrator(
        Settings(job_storage_dir=str(tmp_path), video_pipeline_mock=True)
    )
    job = orchestrator.run(
        payload_file,
        mock=False,
        auto_resolve_intake_gaps=False,
    )
    state = json.loads(job.job_state_path.read_text(encoding="utf-8"))
    assert state["status"] == "awaiting_intake_clarification"
    document = load_intake_clarification(job)
    assert document is not None
    assert document.user_message


def test_orchestrator_auto_resolves_intake_in_mock(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("JOB_STORAGE_DIR", str(tmp_path))
    from video_pipeline.config import Settings

    fixtures = Path(__file__).parent / "fixtures"
    orchestrator = PipelineOrchestrator(
        Settings(job_storage_dir=str(tmp_path), video_pipeline_mock=True)
    )
    job = orchestrator.run(
        fixtures / "gateway_payload.json",
        mock=True,
        stop_after="intake_done",
    )
    state = json.loads(job.job_state_path.read_text(encoding="utf-8"))
    assert state["status"] == "intake_done"
    plan = load_intake_plan(job)
    assert plan is not None
    assert plan.script_brief


def test_apply_intake_resolution_system_generate_style(tmp_path: Path) -> None:
    payload = _payload(style_preset=None, style_notes=None)
    job = ensure_job_layout(create_job_paths(resolve_storage_root(str(tmp_path))))
    gaps = detect_intake_gaps(job, payload)
    style_gap = next(g for g in gaps if g.kind == "style")
    updated = apply_intake_resolutions(
        payload,
        gaps,
        [
            IntakeGapResolution(
                gap_id=style_gap.gap_id,
                choice="system_generate",
            )
        ],
    )
    assert updated.style_notes
