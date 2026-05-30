"""Job state schema — orchestrator lifecycle tracking."""

from datetime import datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field

JobStatus = Literal[
    "received",
    "scripted",
    "storyboarded",
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
