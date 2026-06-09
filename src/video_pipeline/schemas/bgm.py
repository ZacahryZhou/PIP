"""BGM prep report — documents source before final mix."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class BGMPrepReport(BaseModel):
    job_id: str = Field(min_length=1)
    mode: str = Field(min_length=1)
    status: Literal["ok", "failed", "skipped"]
    source: str | None = None
    instrumental: bool = False
    music_mood: str = ""
    music_bpm: int = 120
    estimated_duration_sec: float = 0.0
    bgm_track_path: str | None = None
    resumed: bool = False
    error: str | None = None
