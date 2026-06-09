"""TTS prep manifest and report schemas."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class DialogueTextSpec(BaseModel):
    line_id: str = Field(min_length=1)
    speaker: str = Field(min_length=1)
    text: str = Field(min_length=1)
    source: str = Field(min_length=1)
    estimated_duration_sec: float = Field(gt=0)


class TTSManifestEntry(BaseModel):
    line_id: str = Field(min_length=1)
    text: str = Field(min_length=1)
    wav_path: str | None = None
    status: Literal["ok", "failed", "skipped"]
    duration_sec: float | None = None
    provider: str | None = None
    error: str | None = None


class TTSManifest(BaseModel):
    job_id: str = Field(min_length=1)
    provider: str = Field(min_length=1)
    voice: str = Field(min_length=1)
    language: str = Field(min_length=1)
    lines: list[DialogueTextSpec] = Field(default_factory=list)
    segments: list[TTSManifestEntry] = Field(default_factory=list)


class TTSReport(BaseModel):
    job_id: str = Field(min_length=1)
    provider: str = Field(min_length=1)
    status: Literal["ok", "failed", "skipped"]
    segment_count: int = 0
    failed_line_ids: list[str] = Field(default_factory=list)
    manifest_path: str
    resumed: bool = False
    elapsed_sec: float | None = None
