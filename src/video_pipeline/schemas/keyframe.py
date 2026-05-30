"""Keyframe generation report — one still image per i2v shot."""

from typing import Literal

from pydantic import BaseModel, Field

from video_pipeline.schemas.storyboard import GenerationMode

KeyframeStatus = Literal["success", "skipped", "failed"]


class KeyframeResult(BaseModel):
    shot_id: str = Field(pattern=r"^shot_\d{3}$")
    generation_mode: GenerationMode
    status: KeyframeStatus
    keyframe_path: str | None = None
    prompt: str | None = None
    error_message: str | None = None
    provider_request_id: str | None = None


class KeyframeReport(BaseModel):
    job_id: str = Field(min_length=1)
    results: list[KeyframeResult] = Field(default_factory=list)
