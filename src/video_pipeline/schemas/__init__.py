"""Pydantic contracts for all pipeline stage boundaries."""

from video_pipeline.schemas.gateway import ChannelName, GatewayPayload
from video_pipeline.schemas.keyframe import KeyframeReport, KeyframeResult
from video_pipeline.schemas.generation import (
    GenerationAttempt,
    GenerationReport,
    ShotGenerationResult,
)
from video_pipeline.schemas.job import JobStage, JobState, JobStatus
from video_pipeline.schemas.qc import QCCheckResult, QCReport
from video_pipeline.schemas.routing import RouteDecision, RoutingPlan
from video_pipeline.schemas.script import DialogueLine, Scene, ScriptPlan
from video_pipeline.schemas.storyboard import GenerationMode, Shot, ShotSize, ShotsDocument

__all__ = [
    "ChannelName",
    "DialogueLine",
    "GatewayPayload",
    "GenerationAttempt",
    "GenerationReport",
    "KeyframeReport",
    "KeyframeResult",
    "JobStage",
    "JobState",
    "JobStatus",
    "QCCheckResult",
    "QCReport",
    "RouteDecision",
    "RoutingPlan",
    "Scene",
    "ScriptPlan",
    "GenerationMode",
    "Shot",
    "ShotSize",
    "ShotGenerationResult",
    "ShotsDocument",
]
