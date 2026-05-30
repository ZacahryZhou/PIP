"""Routing Agent — deterministic model assignment from ROUTING.md rules."""

from __future__ import annotations

import math

from video_pipeline.schemas import RouteDecision, RoutingPlan, Shot, ShotsDocument
from video_pipeline.schemas.storyboard import VideoModelName
from video_pipeline.storage import JobPaths, write_json

COST_PER_SECOND: dict[VideoModelName, float] = {
    "seedance": 0.10,
    "kling": 0.08,
    "wan_t2v": 0.03,
    "premium_api": 0.20,
    "mock": 0.0,
}

KEYFRAME_COST_USD = 0.15


def route_shot(shot: Shot) -> tuple[VideoModelName, VideoModelName, str]:
    """Apply ROUTING.md priority: first matching rule wins."""
    if shot.has_characters and shot.motion_intensity == "high":
        return (
            "seedance",
            "kling",
            "has_characters=true and motion_intensity=high",
        )
    if shot.scene_type in ("creative", "abstract"):
        return (
            "premium_api",
            "kling",
            f"scene_type={shot.scene_type}",
        )
    if shot.scene_type == "realistic":
        return ("kling", "wan_t2v", "scene_type=realistic")
    if shot.scene_type == "simple" or shot.motion_intensity == "low":
        if shot.scene_type == "simple" and shot.motion_intensity == "low":
            reason = "scene_type=simple and motion_intensity=low"
        elif shot.scene_type == "simple":
            reason = "scene_type=simple"
        else:
            reason = "motion_intensity=low"
        return ("wan_t2v", "kling", reason)
    return ("kling", "wan_t2v", "default fallback")


def estimate_shot_cost(model: VideoModelName, duration_sec: float) -> float:
    billed_seconds = max(1, math.ceil(duration_sec))
    return round(billed_seconds * COST_PER_SECOND[model], 4)


def build_routing_plan(
    shots: ShotsDocument,
    *,
    max_job_cost_usd: float,
) -> RoutingPlan:
    routes: list[RouteDecision] = []
    for shot in shots.shots:
        preferred, fallback, reason = route_shot(shot)
        keyframe_cost = KEYFRAME_COST_USD if shot.generation_mode == "i2v" else 0.0
        video_cost = estimate_shot_cost(preferred, shot.duration_sec)
        routes.append(
            RouteDecision(
                shot_id=shot.shot_id,
                preferred_model=preferred,
                fallback_model=fallback,
                generation_mode=shot.generation_mode,
                generation_mode_reason=shot.generation_mode_reason,
                routing_reason=reason,
                estimated_keyframe_cost=keyframe_cost,
                estimated_cost_per_shot=round(video_cost + keyframe_cost, 4),
                estimated_duration_sec=shot.duration_sec,
            )
        )

    total = round(sum(route.estimated_cost_per_shot for route in routes), 4)
    should_continue = total <= max_job_cost_usd
    budget_message: str | None = None
    if not should_continue:
        budget_message = (
            f"Estimated cost ${total:.2f} exceeds budget ${max_job_cost_usd:.2f}. "
            "Generation stopped."
        )

    return RoutingPlan(
        routes=routes,
        total_estimated_cost=total,
        currency="USD",
        should_continue=should_continue,
        budget_message=budget_message,
    )


def run_routing_agent(
    job: JobPaths,
    shots: ShotsDocument,
    *,
    max_job_cost_usd: float,
) -> RoutingPlan:
    plan = build_routing_plan(shots, max_job_cost_usd=max_job_cost_usd)
    write_json(job.routing_path, plan)
    return plan
