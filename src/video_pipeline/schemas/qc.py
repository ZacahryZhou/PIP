"""Quality control schema — clip validation reports."""

from typing import Literal

from pydantic import BaseModel, Field

CheckName = Literal[
    "duration",
    "resolution",
    "fps",
    "blank_frames",
    "file_integrity",
    "normalize",
]
CheckStatus = Literal["passed", "failed"]


class QCCheckResult(BaseModel):
    shot_id: str = Field(pattern=r"^shot_\d{3}$")
    check: CheckName
    status: CheckStatus
    expected: str | None = None
    actual: str | None = None
    message: str | None = None


class QCReport(BaseModel):
    job_id: str = Field(min_length=1)
    target_resolution: str = Field(default="1920x1080")
    target_fps: int = Field(default=24, ge=1)
    passed_shot_ids: list[str] = Field(default_factory=list)
    failed_shot_ids: list[str] = Field(default_factory=list)
    checks: list[QCCheckResult] = Field(default_factory=list)

    @property
    def all_passed(self) -> bool:
        return len(self.failed_shot_ids) == 0
