"""Validate pipeline JSON contracts against Pydantic schemas."""

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from video_pipeline.schemas import (
    GatewayPayload,
    RoutingPlan,
    ScriptPlan,
    ShotsDocument,
    StoryboardApprovalDocument,
    StoryboardPreviewDocument,
)
from video_pipeline.pipeline.storyboard_validation import validate_storyboard_logic

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def load_json(name: str) -> dict:
    return json.loads((FIXTURES_DIR / name).read_text(encoding="utf-8"))


def test_gateway_payload_fixture_valid() -> None:
    payload = GatewayPayload.model_validate(load_json("gateway_payload.json"))
    assert payload.channel == "telegram"
    assert "cyberpunk" in payload.raw_prompt.lower()


def test_script_plan_fixture_valid() -> None:
    script = ScriptPlan.model_validate(load_json("script.json"))
    assert script.total_duration_sec == 30
    assert len(script.scene_list) == 3
    scene_total = sum(scene.duration_sec for scene in script.scene_list)
    assert abs(scene_total - script.total_duration_sec) <= 1.0


def test_shots_document_fixture_valid() -> None:
    shots_doc = ShotsDocument.model_validate(load_json("shots.json"))
    assert len(shots_doc.shots) == 6
    assert shots_doc.total_duration_sec == 30
    for shot in shots_doc.shots:
        assert shot.preferred_model is None
        assert shot.fallback_model is None


def test_routing_plan_fixture_valid() -> None:
    routing = RoutingPlan.model_validate(load_json("routing.json"))
    assert routing.should_continue is True
    assert len(routing.routes) == 6
    assert routing.total_estimated_cost == pytest.approx(3.15)


def test_shots_duration_matches_script_fixture() -> None:
    script = ScriptPlan.model_validate(load_json("script.json"))
    shots_doc = ShotsDocument.model_validate(load_json("shots.json"))
    assert abs(shots_doc.total_duration_sec - script.total_duration_sec) <= 1.0


def test_invalid_gateway_payload_rejected() -> None:
    data = load_json("invalid_gateway_payload.json")
    with pytest.raises(ValidationError) as exc_info:
        GatewayPayload.model_validate(data)
    errors = exc_info.value.errors()
    assert any(
        error["loc"] == ("raw_prompt",) or error.get("type") == "value_error"
        for error in errors
    )


def test_shot_duration_over_limit_rejected() -> None:
    data = load_json("shots.json")
    data["shots"][0]["duration_sec"] = 9
    with pytest.raises(ValidationError):
        ShotsDocument.model_validate(data)


def test_routing_cost_mismatch_rejected() -> None:
    data = load_json("routing.json")
    data["total_estimated_cost"] = 999.0
    with pytest.raises(ValidationError):
        RoutingPlan.model_validate(data)


def test_gateway_accepts_user_script_without_raw_prompt() -> None:
    payload = GatewayPayload.model_validate(
        {
            "raw_prompt": "",
            "user_script_text": "Scene 1: Hero runs through rain.",
            "has_script": True,
            "channel": "telegram",
            "user_id": "123456",
            "timestamp": "2026-05-28T17:30:00-07:00",
        }
    )
    assert payload.has_script is True
    assert payload.user_script_text is not None


def test_script_plan_normalizes_scene_first_fields() -> None:
    script = ScriptPlan.model_validate(load_json("script.json"))
    assert script.scene_list[0].scene_order == 1
    assert script.scene_list[0].scene_purpose
    assert script.scene_list[0].visual_style == script.visual_style


def test_shots_document_normalizes_order_fields() -> None:
    shots_doc = ShotsDocument.model_validate(load_json("shots.json"))
    assert shots_doc.shots[0].scene_order == 1
    assert shots_doc.shots[0].shot_order_in_scene == 1
    assert shots_doc.shots[1].shot_order_in_scene == 2


def test_storyboard_logic_validation_passes_fixture() -> None:
    script = ScriptPlan.model_validate(load_json("script.json"))
    shots_doc = ShotsDocument.model_validate(load_json("shots.json"))
    assert validate_storyboard_logic(script, shots_doc) == []


def test_storyboard_preview_and_approval_schemas() -> None:
    preview = StoryboardPreviewDocument.model_validate(
        {
            "job_id": "job_test",
            "preview_version": 1,
            "created_at": "2026-05-28T17:30:00-07:00",
            "items": [
                {
                    "shot_id": "shot_001",
                    "scene_id": "scene_001",
                    "preview_image_path": "preview/shot_001_start.png",
                    "start_image_path": "preview/shot_001_start.png",
                    "end_image_path": "preview/shot_001_end.png",
                    "start_prompt": "hero in neon alley, first frame",
                    "end_prompt": "hero in neon alley, last frame",
                    "prompt": "hero in neon alley",
                }
            ],
        }
    )
    assert preview.items[0].status == "ok"

    approval = StoryboardApprovalDocument.model_validate(
        {
            "job_id": "job_test",
            "preview_version": 1,
            "status": "pending",
        }
    )
    assert approval.revision_count == 0
