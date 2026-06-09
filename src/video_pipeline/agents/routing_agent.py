"""Routing Agent — V2 assigns Kling first-last-frame to every shot."""

from __future__ import annotations

import math

from video_pipeline.providers.capabilities import get_provider_capabilities, keyframe_cost_for_mode
from video_pipeline.schemas import RouteDecision, RoutingPlan, ShotsDocument
from video_pipeline.schemas.storyboard import VideoModelName
from video_pipeline.storage import JobPaths, write_json

V2_MODEL: VideoModelName = "kling"
V2_MODE = "first_last_frame"
COST_PER_SECOND: dict[VideoModelName, float] = {
    "kling": 0.08,
    "mock": 0.0,
}


def route_shot_v2() -> tuple[VideoModelName, VideoModelName, str]:
    return V2_MODEL, V2_MODEL, "V2: Kling first-last-frame only"


def estimate_shot_cost(model: VideoModelName, duration_sec: float) -> float:
    billed_seconds = max(1, math.ceil(duration_sec))
    return round(billed_seconds * COST_PER_SECOND[model], 4)


def build_routing_plan(
    shots: ShotsDocument,
    *,
    max_job_cost_usd: float,
) -> RoutingPlan:
    routes: list[RouteDecision] = []
    caps = get_provider_capabilities(V2_MODEL)
    keyframe_cost = keyframe_cost_for_mode(V2_MODE)

    for shot in shots.shots:
        preferred, fallback, reason = route_shot_v2()
        video_cost = estimate_shot_cost(preferred, shot.duration_sec)
        routes.append(
            RouteDecision(
                shot_id=shot.shot_id,
                preferred_model=preferred,
                fallback_model=fallback,
                generation_mode=V2_MODE,
                generation_mode_reason="V2 pipeline requires first-last-frame",
                routing_reason=reason,
                estimated_keyframe_cost=keyframe_cost,
                estimated_cost_per_shot=round(video_cost + keyframe_cost, 4),
                estimated_duration_sec=shot.duration_sec,
                supports_t2v=caps.supports_t2v,
                supports_i2v=caps.supports_i2v,
                supports_first_last_frame=caps.supports_first_last_frame,
                supports_audio_generation=caps.supports_audio_generation,
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
