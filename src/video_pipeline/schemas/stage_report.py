"""Common stage report envelope for inspectable pipeline artifacts."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

StageStatus = Literal["ok", "failed", "skipped", "partial"]


class StageReportEnvelope(BaseModel):
    job_id: str = Field(min_length=1)
    stage: str = Field(min_length=1)
    status: StageStatus
    started_at: str
    finished_at: str
    duration_ms: int = Field(ge=0)
    input_artifacts: list[str] = Field(default_factory=list)
    output_artifacts: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    provider_request_count: int = Field(default=0, ge=0)
    resumed: bool = False
