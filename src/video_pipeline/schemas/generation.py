"""Generation result schema — per-shot video API outcomes."""

from typing import Literal

from pydantic import BaseModel, Field

from video_pipeline.schemas.storyboard import GenerationMode, VideoModelName

GenerationStatus = Literal["success", "failed", "skipped"]
AttemptOutcome = Literal["success", "failed"]


class GenerationAttempt(BaseModel):
    model: VideoModelName
    attempt_number: int = Field(ge=1)
    outcome: AttemptOutcome
    output_path: str | None = None
    error_code: str | None = None
    error_message: str | None = None
    provider_request_id: str | None = None


class ShotGenerationResult(BaseModel):
    shot_id: str = Field(pattern=r"^shot_\d{3}$")
    status: GenerationStatus
    generation_mode: GenerationMode | None = None
    selected_model: VideoModelName | None = None
    keyframe_path: str | None = None
    output_path: str | None = None
    attempts: list[GenerationAttempt] = Field(default_factory=list)


class GenerationReport(BaseModel):
    job_id: str = Field(min_length=1)
    results: list[ShotGenerationResult] = Field(default_factory=list)
    succeeded_shot_ids: list[str] = Field(default_factory=list)
    failed_shot_ids: list[str] = Field(default_factory=list)
