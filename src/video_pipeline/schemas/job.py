"""Job state schema — orchestrator lifecycle tracking."""

from datetime import datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field

JobStatus = Literal[
    "received",
    "assets_collected",
    "awaiting_intake_clarification",
    "intake_done",
    "plot_done",
    "failed_intake",
    "scripted",
    "reference_assets_ready",
    "storyboarded",
    "preview_started",
    "preview_ready",
    "awaiting_storyboard_approval",
    "storyboard_revision_requested",
    "storyboard_approved",
    "routed",
    "keyframes_started",
    "keyframes",
    "generation_started",
    "generated",
    "qc_started",
    "validated",
    "assembled",
    "delivered",
    "failed_validation",
    "failed_keyframes",
    "failed_generation",
    "failed_qc",
    "failed_postproduction",
    "failed_delivery",
    "cancelled_budget",
    "cancelled_timeout",
    "cancelled_user",
    "failed_assets",
    "failed_preview",
    "character_assets_started",
    "character_assets_ready",
    "failed_character_assets",
    "storyboard_gate_passed",
    "failed_storyboard_gate",
    "scene_maps_started",
    "scene_maps_ready",
    "failed_scene_maps",
    "tts_started",
    "tts_ready",
    "failed_tts",
]


class JobStage(str, Enum):
    RECEIVED = "received"
    SCRIPTED = "scripted"
    STORYBOARDED = "storyboarded"
    ROUTED = "routed"
    KEYFRAMES_STARTED = "keyframes_started"
    KEYFRAMES = "keyframes"
    GENERATION_STARTED = "generation_started"
    GENERATED = "generated"
    QC_STARTED = "qc_started"
    VALIDATED = "validated"
    ASSEMBLED = "assembled"
    DELIVERED = "delivered"


class JobState(BaseModel):
    job_id: str = Field(min_length=1)
    status: JobStatus
    updated_at: datetime
    current_stage: str = Field(min_length=1)
    error_message: str | None = None
    artifact_paths: dict[str, str] = Field(default_factory=dict)
