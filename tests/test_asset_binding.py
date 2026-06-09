"""Shot asset binding — link character/scene packs to storyboard shots."""

import json
import shutil
from pathlib import Path

import pytest

from video_pipeline.config import Settings
from video_pipeline.orchestrator import PipelineOrchestrator
from video_pipeline.pipeline.asset_binding import (
    build_shot_asset_bindings,
    load_shot_asset_binding_report,
    primary_conditioning_path,
    references_for_shot,
    run_asset_binding,
    shot_asset_binding_report_path,
)
from video_pipeline.pipeline.character_assets import run_character_assets
from video_pipeline.pipeline.reference_assets import run_reference_assets
from video_pipeline.pipeline.scene_maps import run_scene_maps
from video_pipeline.schemas import IntakePlan, ScriptPlan, ShotsDocument
from video_pipeline.schemas.reference_asset import ReferenceAssetEntry


FIXTURES_DIR = Path(__file__).parent / "fixtures"


def _prepare_job(tmp_path: Path):
    orchestrator = PipelineOrchestrator(Settings(job_storage_dir=str(tmp_path)))
    job = orchestrator.run(
        FIXTURES_DIR / "gateway_payload.json",
        mock=True,
        stop_after="storyboarded",
        require_approval=False,
    )
    script = ScriptPlan.model_validate_json(job.script_path.read_text(encoding="utf-8"))
    shots = ShotsDocument.model_validate_json(job.shots_path.read_text(encoding="utf-8"))
    intake_plan = IntakePlan.model_validate_json(job.intake_plan_path.read_text(encoding="utf-8"))
    payload = json.loads(job.gateway_payload_path.read_text(encoding="utf-8"))
    from video_pipeline.schemas import GatewayPayload

    gateway = GatewayPayload.model_validate(payload)
    run_character_assets(
        job,
        gateway,
        intake_plan=intake_plan,
        script=script,
        shots=shots,
        settings=Settings(job_storage_dir=str(tmp_path)),
        mock=True,
    )
    run_scene_maps(
        job,
        gateway,
        intake_plan=intake_plan,
        script=script,
        shots=shots,
        settings=Settings(job_storage_dir=str(tmp_path)),
        mock=True,
    )
    return job, script, shots, gateway, intake_plan


def test_run_asset_binding_writes_report_and_mutates_shots(tmp_path: Path) -> None:
    job, script, shots, _, _ = _prepare_job(tmp_path)
    report, bound_shots = run_asset_binding(job, script, shots)

    assert shot_asset_binding_report_path(job).is_file()
    assert len(report.entries) == len(shots.shots)
    assert len(report.by_scene) >= 1
    for group in report.by_scene:
        assert group.scene_id.startswith("scene_")
        assert group.shot_ids

    bound = load_shot_asset_binding_report(job)
    assert bound is not None
    first_shot = bound_shots.shots[0]
    assert first_shot.scene_reference_image_path is not None
    if first_shot.has_characters:
        assert first_shot.character_reference_image_paths


def test_primary_conditioning_prefers_character_reference(tmp_path: Path) -> None:
    job, script, shots, _, _ = _prepare_job(tmp_path)
    report = build_shot_asset_bindings(job, shots)
    character_shot = next(shot for shot in shots.shots if shot.has_characters)
    binding = next(entry for entry in report.entries if entry.shot_id == character_shot.shot_id)
    path = primary_conditioning_path(job, character_shot, binding)
    assert path is not None
    assert path.is_file()


def test_orchestrator_writes_binding_before_preview(tmp_path: Path) -> None:
    if shutil.which("ffmpeg") is None:
        pytest.skip("ffmpeg not available")

    orchestrator = PipelineOrchestrator(Settings(job_storage_dir=str(tmp_path)))
    job = orchestrator.run(
        FIXTURES_DIR / "gateway_payload.json",
        mock=True,
        stop_after="preview_ready",
        require_approval=False,
    )

    assert shot_asset_binding_report_path(job).is_file()
    shots = ShotsDocument.model_validate_json(job.shots_path.read_text(encoding="utf-8"))
    assert any(shot.scene_reference_image_path for shot in shots.shots)


def test_reference_assets_bind_to_shot_by_scene(tmp_path: Path) -> None:
    job, script, shots, _, _ = _prepare_job(tmp_path)
    scene_id = shots.shots[0].scene_id
    ref_rel = "assets/references/prop_cup.png"
    ref_path = job.root / ref_rel
    ref_path.parent.mkdir(parents=True, exist_ok=True)
    ref_path.write_bytes(b"fake")

    from video_pipeline.schemas.reference_asset import ReferenceAssetReport
    from video_pipeline.storage import write_json as write_job_json

    write_job_json(
        job.reports_dir / "reference_asset_report.json",
        ReferenceAssetReport(
            job_id=job.job_id,
            entries=[
                ReferenceAssetEntry(
                    ref_id="prop_cup",
                    kind="prop",
                    asset_path=ref_rel,
                    source="generated",
                    status="ok",
                    linked_scene_id=scene_id,
                )
            ],
        ),
    )

    report = build_shot_asset_bindings(job, shots)
    shot_binding = next(item for item in report.entries if item.shot_id == shots.shots[0].shot_id)
    assert any(ref.ref_id == "prop_cup" for ref in shot_binding.reference_bindings)

    _, bound_shots = run_asset_binding(job, script, shots)
    bound_shot = bound_shots.shots[0]
    assert "prop_cup" in bound_shot.other_reference_ids
    assert ref_rel in bound_shot.other_reference_image_paths
