"""Tests for V2 routing — Kling first-last-frame only."""

import json
from pathlib import Path

from video_pipeline.agents.routing_agent import build_routing_plan, route_shot_v2
from video_pipeline.schemas import ShotsDocument


def load_shots() -> ShotsDocument:
    path = Path(__file__).parent / "fixtures" / "shots.json"
    return ShotsDocument.model_validate(json.loads(path.read_text(encoding="utf-8")))


def test_route_shot_v2_is_kling_first_last() -> None:
    preferred, fallback, reason = route_shot_v2()
    assert preferred == "kling"
    assert fallback == "kling"
    assert "first-last" in reason.lower()


def test_build_routing_plan_all_first_last_frame() -> None:
    shots = load_shots()
    plan = build_routing_plan(shots, max_job_cost_usd=50.0)
    assert len(plan.routes) == len(shots.shots)
    assert all(route.preferred_model == "kling" for route in plan.routes)
    assert all(route.generation_mode == "first_last_frame" for route in plan.routes)
    assert plan.should_continue is True


def test_build_routing_plan_over_budget() -> None:
    shots = load_shots()
    plan = build_routing_plan(shots, max_job_cost_usd=0.5)
    assert plan.should_continue is False
    assert plan.budget_message is not None
