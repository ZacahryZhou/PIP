"""Human storyboard approval artifact."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


ApprovalStatus = Literal[
    "pending",
    "approved",
    "revision_requested",
    "cancelled",
    "timeout",
]


class StoryboardApprovalDocument(BaseModel):
    job_id: str = Field(min_length=1)
    preview_version: int = Field(ge=1)
    status: ApprovalStatus
    user_message: str | None = None
    approved_at: datetime | None = None
    revision_count: int = Field(default=0, ge=0)
