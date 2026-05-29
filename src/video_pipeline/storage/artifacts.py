"""Read and write JSON artifacts under a job folder."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from video_pipeline.schemas import GatewayPayload, JobState

RULE_FILES = (
    "MASTER.md",
    "CHARACTERS.md",
    "STORYBOARD.md",
    "ROUTING.md",
    "POSTPROD.md",
)


def repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def resolve_storage_root(storage_dir: str) -> Path:
    path = Path(storage_dir)
    if path.is_absolute():
        return path
    return repo_root() / path


def write_json(path: Path, data: BaseModel | dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(data, BaseModel):
        payload = data.model_dump(mode="json")
    else:
        payload = data
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return path


def copy_rules_snapshot(job_root: Path, rules_dir: Path | None = None) -> list[Path]:
    source = rules_dir or (repo_root() / "rules")
    target = job_root / "rules_snapshot"
    target.mkdir(parents=True, exist_ok=True)
    copied: list[Path] = []
    for name in RULE_FILES:
        src = source / name
        if not src.exists():
            continue
        dest = target / name
        shutil.copy2(src, dest)
        copied.append(dest)
    return copied


def save_gateway_payload(path: Path, payload: GatewayPayload) -> Path:
    return write_json(path, payload)


def save_job_state(path: Path, state: JobState) -> Path:
    return write_json(path, state)
