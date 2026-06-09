"""Storyboard preview still manifest."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


PreviewItemStatus = Literal["ok", "failed", "skipped"]


class StoryboardPreviewItem(BaseModel):
    shot_id: str = Field(pattern=r"^shot_\d{3}$")
    scene_id: str = Field(pattern=r"^scene_\d{3}$")
    preview_image_path: str = Field(min_length=1)
    start_image_path: str = Field(min_length=1)
    end_image_path: str = Field(min_length=1)
    start_prompt: str = Field(min_length=1)
    end_prompt: str = Field(min_length=1)
    prompt: str = Field(min_length=1)
    status: PreviewItemStatus = "ok"


class StoryboardPreviewDocument(BaseModel):
    job_id: str = Field(min_length=1)
    preview_version: int = Field(ge=1)
    items: list[StoryboardPreviewItem] = Field(min_length=1)
    created_at: datetime
