"""Create per-request job folder paths."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


JOB_SUBDIRS = (
    "input",
    "rules_snapshot",
    "script",
    "storyboard",
    "routing",
    "keyframes",
    "clips/raw",
    "clips/validated",
    "reports",
    "audio",
    "final",
)


@dataclass(frozen=True)
class JobPaths:
    job_id: str
    root: Path

    @property
    def input_dir(self) -> Path:
        return self.root / "input"

    @property
    def rules_snapshot_dir(self) -> Path:
        return self.root / "rules_snapshot"

    @property
    def script_dir(self) -> Path:
        return self.root / "script"

    @property
    def storyboard_dir(self) -> Path:
        return self.root / "storyboard"

    @property
    def routing_dir(self) -> Path:
        return self.root / "routing"

    @property
    def keyframes_dir(self) -> Path:
        return self.root / "keyframes"

    @property
    def clips_raw_dir(self) -> Path:
        return self.root / "clips" / "raw"

    @property
    def clips_validated_dir(self) -> Path:
        return self.root / "clips" / "validated"

    @property
    def reports_dir(self) -> Path:
        return self.root / "reports"

    @property
    def final_dir(self) -> Path:
        return self.root / "final"

    @property
    def gateway_payload_path(self) -> Path:
        return self.input_dir / "gateway_payload.json"

    @property
    def job_state_path(self) -> Path:
        return self.root / "job_state.json"

    @property
    def script_path(self) -> Path:
        return self.script_dir / "script.json"

    @property
    def shots_path(self) -> Path:
        return self.storyboard_dir / "shots.json"

    @property
    def routing_path(self) -> Path:
        return self.routing_dir / "routing.json"


def new_job_id(now: datetime | None = None) -> str:
    moment = now or datetime.now().astimezone()
    return f"job_{moment.strftime('%Y%m%d_%H%M%S')}"


def create_job_paths(storage_root: Path, job_id: str | None = None) -> JobPaths:
    job_id = job_id or new_job_id()
    root = storage_root / job_id
    return JobPaths(job_id=job_id, root=root)


def ensure_job_layout(job: JobPaths) -> JobPaths:
    for relative in JOB_SUBDIRS:
        (job.root / relative).mkdir(parents=True, exist_ok=True)
    return job
