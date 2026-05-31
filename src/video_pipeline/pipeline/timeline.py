"""Build final timeline from validated clips (hard-cut MVP)."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from video_pipeline.media.ffmpeg import probe_video
from video_pipeline.pipeline.quality_control import validated_clip_path
from video_pipeline.schemas import ShotsDocument
from video_pipeline.storage import JobPaths


@dataclass(frozen=True)
class TimelineShot:
    shot_id: str
    source_clip: str
    start_sec: float
    end_sec: float
    transition_out: str = "hard_cut"


@dataclass(frozen=True)
class TimelineDocument:
    shots: list[TimelineShot]
    final_duration_sec: float


def build_timeline(job: JobPaths, shots: ShotsDocument) -> TimelineDocument:
    ordered = sorted(shots.shots, key=lambda shot: shot.shot_id)
    entries: list[TimelineShot] = []
    cursor = 0.0

    for shot in ordered:
        clip_path = validated_clip_path(job, shot.shot_id)
        meta = probe_video(clip_path)
        duration = float(meta["duration_sec"])
        if duration <= 0:
            duration = float(shot.duration_sec)

        start = cursor
        end = cursor + duration
        entries.append(
            TimelineShot(
                shot_id=shot.shot_id,
                source_clip=str(clip_path.relative_to(job.root)),
                start_sec=start,
                end_sec=end,
            )
        )
        cursor = end

    return TimelineDocument(shots=entries, final_duration_sec=cursor)


def save_timeline(path: Path, timeline: TimelineDocument) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "shots": [asdict(entry) for entry in timeline.shots],
        "final_duration_sec": timeline.final_duration_sec,
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def load_timeline(path: Path) -> TimelineDocument:
    payload = json.loads(path.read_text(encoding="utf-8"))
    shots = [TimelineShot(**item) for item in payload["shots"]]
    return TimelineDocument(shots=shots, final_duration_sec=float(payload["final_duration_sec"]))
