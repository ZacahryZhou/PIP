"""Scene master map report — one visual anchor per scene_id."""

from typing import Literal

from pydantic import BaseModel, Field

SceneMapSource = Literal["user_reference", "generated"]
SceneMapStatus = Literal["ok", "failed"]


class SceneMapEntry(BaseModel):
    scene_id: str = Field(pattern=r"^scene_\d{3}$")
    master_image_path: str = Field(min_length=1)
    angle_image_paths: list[str] = Field(default_factory=list)
    pack_complete: bool = False
    source: SceneMapSource
    status: SceneMapStatus
    prompt: str | None = None
    provider_request_id: str | None = None
    error_message: str | None = None


class SceneMapReport(BaseModel):
    job_id: str = Field(min_length=1)
    entries: list[SceneMapEntry] = Field(default_factory=list)
