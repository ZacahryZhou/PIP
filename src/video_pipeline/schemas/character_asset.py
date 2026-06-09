"""Character consistency pack — turnaround / multi-angle references."""

from typing import Literal

from pydantic import BaseModel, Field

CharacterAssetSource = Literal["user_reference", "generated"]
CharacterAssetStatus = Literal["ok", "failed"]


class CharacterAssetEntry(BaseModel):
    character_id: str = Field(min_length=1)
    user_reference_path: str | None = None
    turnaround_dir: str = Field(min_length=1)
    angle_image_paths: list[str] = Field(default_factory=list)
    source: CharacterAssetSource
    status: CharacterAssetStatus
    prompt: str | None = None
    error_message: str | None = None


class CharacterAssetReport(BaseModel):
    job_id: str = Field(min_length=1)
    entries: list[CharacterAssetEntry] = Field(default_factory=list)
