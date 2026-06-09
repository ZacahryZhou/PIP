"""Write standardized stage metadata onto report JSON files."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from video_pipeline.schemas.stage_report import StageReportEnvelope, StageStatus
from video_pipeline.storage import JobPaths, write_json


@dataclass
class StageTimer:
    job_id: str
    stage: str
    input_artifacts: list[str] = field(default_factory=list)
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    _monotonic_start: float = field(default_factory=time.monotonic)

    def envelope(
        self,
        *,
        status: StageStatus,
        output_artifacts: list[str] | None = None,
        warnings: list[str] | None = None,
        errors: list[str] | None = None,
        provider_request_count: int = 0,
        resumed: bool = False,
    ) -> StageReportEnvelope:
        finished = datetime.now(timezone.utc)
        duration_ms = int((time.monotonic() - self._monotonic_start) * 1000)
        return StageReportEnvelope(
            job_id=self.job_id,
            stage=self.stage,
            status=status,
            started_at=self.started_at.isoformat(),
            finished_at=finished.isoformat(),
            duration_ms=duration_ms,
            input_artifacts=list(self.input_artifacts),
            output_artifacts=list(output_artifacts or []),
            warnings=list(warnings or []),
            errors=list(errors or []),
            provider_request_count=provider_request_count,
            resumed=resumed,
        )


def merge_stage_report(path: Path, envelope: StageReportEnvelope, payload: dict[str, Any]) -> None:
    merged = {**payload, **envelope.model_dump()}
    write_json(path, merged)


def write_stage_report(
    job: JobPaths,
    path: Path,
    envelope: StageReportEnvelope,
    payload: dict[str, Any],
) -> None:
    job.reports_dir.mkdir(parents=True, exist_ok=True)
    merge_stage_report(path, envelope, payload)
