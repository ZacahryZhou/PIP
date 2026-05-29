"""Tests for deterministic routing rules."""

import json
from pathlib import Path

from video_pipeline.agents.routing_agent import build_routing_plan, route_shot
from video_pipeline.schemas import ShotsDocument


def load_shots() -> ShotsDocument:
    path = Path(__file__).parent / "fixtures" / "shots.json"
    return ShotsDocument.model_validate(json.loads(path.read_text(encoding="utf-8")))


def test_route_shot_high_motion_characters() -> None:
    shots = load_shots()
    preferred, fallback, reason = route_shot(shots.shots[0])
    assert preferred == "seedance"
    assert fallback == "kling"
    assert "high" in reason


def test_route_shot_realistic_medium_motion() -> None:
    shots = load_shots()
    preferred, fallback, reason = route_shot(shots.shots[3])
    assert preferred == "kling"
    assert fallback == "wan_t2v"
    assert reason == "scene_type=realistic"


def test_build_routing_plan_within_budget() -> None:
    shots = load_shots()
    plan = build_routing_plan(shots, max_job_cost_usd=5.0)
    assert len(plan.routes) == len(shots.shots)
    assert plan.should_continue is True
    assert plan.budget_message is None
    assert plan.total_estimated_cost == round(
        sum(route.estimated_cost_per_shot for route in plan.routes), 4
    )


def test_build_routing_plan_over_budget() -> None:
    shots = load_shots()
    plan = build_routing_plan(shots, max_job_cost_usd=0.5)
    assert plan.should_continue is False
    assert plan.budget_message is not None
