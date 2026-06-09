"""Scene master map generation tests."""

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

import pytest

from video_pipeline.config import Settings
from video_pipeline.gateway_assets import GatewayAssetBundle, StagedAsset, apply_gateway_assets
from video_pipeline.orchestrator import PipelineOrchestrator
from video_pipeline.pipeline.keyframe_generation import load_keyframe_prompts
from video_pipeline.pipeline.scene_maps import (
    load_scene_master_map,
    run_scene_maps,
    scene_master_path,
)
from video_pipeline.schemas import GatewayPayload, ScriptPlan, ShotsDocument
from video_pipeline.schemas.intake import IntakePlan
from video_pipeline.schemas.plot import PlotPlan
from video_pipeline.storage import create_job_paths, ensure_job_layout, resolve_storage_root, save_gateway_payload

FIXTURES_DIR = Path(__file__).parent / "fixtures"
PNG_1X1 = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
    b"\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00\x01\x01\x01\x00\x18\xdd\x8d\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
)


def test_mock_scene_maps_generate_master_per_scene(tmp_path: Path) -> None:
    orchestrator = PipelineOrchestrator(Settings(job_storage_dir=str(tmp_path)))
    job = orchestrator.run(
        FIXTURES_DIR / "gateway_payload.json",
        mock=True,
        stop_after="storyboarded",
        require_approval=False,
    )
    script = ScriptPlan.model_validate_json(job.script_path.read_text(encoding="utf-8"))
    shots = ShotsDocument.model_validate_json(job.shots_path.read_text(encoding="utf-8"))
    payload = GatewayPayload.model_validate_json(job.gateway_payload_path.read_text(encoding="utf-8"))
    intake_plan = IntakePlan.model_validate_json(job.intake_plan_path.read_text(encoding="utf-8"))
    plot_plan = PlotPlan.model_validate_json(job.plot_plan_path.read_text(encoding="utf-8"))

    report = run_scene_maps(
        job,
        payload,
        intake_plan=intake_plan,
        plot_plan=plot_plan,
        script=script,
        shots=shots,
        settings=Settings(job_storage_dir=str(tmp_path)),
        mock=True,
    )

    assert len(report.entries) == len(script.scene_list)
    assert all(entry.status == "ok" for entry in report.entries)
    for scene in script.scene_list:
        master = scene_master_path(job, scene.scene_id)
        assert master.is_file()
        entry = next(item for item in report.entries if item.scene_id == scene.scene_id)
        assert entry.source == "generated"

    masters = load_scene_master_map(job)
    assert set(masters) == {scene.scene_id for scene in script.scene_list}


def test_user_scene_reference_is_reused(tmp_path: Path) -> None:
    storage_root = resolve_storage_root(str(tmp_path / "jobs"))
    job = ensure_job_layout(create_job_paths(storage_root))
    payload = GatewayPayload(
        raw_prompt="test",
        channel="telegram",
        user_id="1",
        timestamp=datetime.now(timezone.utc),
    )
    staging = tmp_path / "upload.png"
    staging.write_bytes(PNG_1X1)
    bundle = GatewayAssetBundle(
        staged=(StagedAsset(kind="scene", ref_id="scene_001", source_path=staging),)
    )
    payload = apply_gateway_assets(job, payload, bundle)
    save_gateway_payload(job.gateway_payload_path, payload)

    script = ScriptPlan.model_validate_json((FIXTURES_DIR / "script.json").read_text(encoding="utf-8"))
    shots = ShotsDocument.model_validate_json((FIXTURES_DIR / "shots.json").read_text(encoding="utf-8"))
    from video_pipeline.agents.intake_agent import build_intake_plan

    intake_plan = build_intake_plan(job, payload)

    report = run_scene_maps(
        job,
        payload,
        intake_plan=intake_plan,
        script=script,
        shots=shots,
        settings=Settings(job_storage_dir=str(tmp_path)),
        mock=True,
    )

    scene_001 = next(entry for entry in report.entries if entry.scene_id == "scene_001")
    assert scene_001.source == "user_reference"
    assert scene_001.status == "ok"
    assert scene_master_path(job, "scene_001").read_bytes() == PNG_1X1


def test_orchestrator_stop_after_scene_maps_ready(tmp_path: Path) -> None:
    orchestrator = PipelineOrchestrator(Settings(job_storage_dir=str(tmp_path)))
    job = orchestrator.run(
        FIXTURES_DIR / "gateway_payload.json",
        mock=True,
        stop_after="scene_maps_ready",
        require_approval=False,
    )

    state = json.loads(job.job_state_path.read_text(encoding="utf-8"))
    assert state["status"] == "scene_maps_ready"
    assert (job.reports_dir / "scene_map_report.json").is_file()
    assert not (job.reports_dir / "keyframe_report.json").is_file()


def test_keyframe_prompt_mentions_scene_master(tmp_path: Path) -> None:
    if shutil.which("ffmpeg") is None:
        pytest.skip("ffmpeg not available")

    orchestrator = PipelineOrchestrator(Settings(job_storage_dir=str(tmp_path)))
    job = orchestrator.run(
        FIXTURES_DIR / "gateway_payload.json",
        mock=True,
        stop_after="keyframes",
        require_approval=False,
    )

    report = json.loads((job.reports_dir / "keyframe_report.json").read_text(encoding="utf-8"))
    prompts = load_keyframe_prompts(job)
    assert prompts is not None
    assert any("scene master reference" in item.start_prompt for item in prompts.items)
