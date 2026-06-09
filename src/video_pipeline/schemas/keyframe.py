"""Keyframe generation report — start/end stills per shot."""

from typing import Literal

from pydantic import BaseModel, Field

from video_pipeline.schemas.storyboard import GenerationMode

KeyframeStatus = Literal["success", "skipped", "failed"]


class KeyframeResult(BaseModel):
    shot_id: str = Field(pattern=r"^shot_\d{3}$")
    generation_mode: GenerationMode
    status: KeyframeStatus
    start_frame_path: str | None = None
    end_frame_path: str | None = None
    keyframe_path: str | None = None
    start_prompt: str | None = None
    end_prompt: str | None = None
    reused_preview_as_start: bool = False
    prompt: str | None = None
    error_message: str | None = None
    provider_request_id: str | None = None


class KeyframeReport(BaseModel):
    job_id: str = Field(min_length=1)
    results: list[KeyframeResult] = Field(default_factory=list)
