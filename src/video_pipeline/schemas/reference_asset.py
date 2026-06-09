"""Reference asset pack — props, style boards, mood refs from Intake."""

from typing import Literal

from pydantic import BaseModel, Field

ReferenceAssetSource = Literal["user_upload", "generated"]
ReferenceAssetStatus = Literal["ok", "failed", "skipped"]


class ReferenceAssetEntry(BaseModel):
    ref_id: str = Field(min_length=1)
    kind: str = Field(min_length=1)
    asset_path: str | None = None
    source: ReferenceAssetSource
    status: ReferenceAssetStatus
    linked_scene_id: str | None = None
    linked_character_id: str | None = None
    prompt: str | None = None
    error_message: str | None = None


class ReferenceAssetReport(BaseModel):
    job_id: str = Field(min_length=1)
    entries: list[ReferenceAssetEntry] = Field(default_factory=list)
