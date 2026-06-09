"""Shared artifact path helpers (no stage imports)."""

from __future__ import annotations

from pathlib import Path

from video_pipeline.storage import JobPaths


def scene_map_report_path(job: JobPaths) -> Path:
    return job.reports_dir / "scene_map_report.json"


def keyframe_start_path(job: JobPaths, shot_id: str) -> Path:
    return job.keyframes_dir / f"{shot_id}_start.png"


def keyframe_end_path(job: JobPaths, shot_id: str) -> Path:
    return job.keyframes_dir / f"{shot_id}_end.png"


def validated_clip_path(job: JobPaths, shot_id: str) -> Path:
    return job.clips_validated_dir / f"{shot_id}.mp4"
