"""Post-production — concatenate validated clips into final video."""

from __future__ import annotations

import shutil
from pathlib import Path

from video_pipeline.media.ffmpeg import concat_videos
from video_pipeline.schemas import ShotsDocument
from video_pipeline.storage import JobPaths

from video_pipeline.pipeline.quality_control import validated_clip_path


def run_postproduction(job: JobPaths, shots: ShotsDocument) -> Path:
    ordered = sorted(shots.shots, key=lambda shot: shot.shot_id)
    inputs = [validated_clip_path(job, shot.shot_id) for shot in ordered]
    missing = [str(path) for path in inputs if not path.is_file()]
    if missing:
        raise FileNotFoundError(f"Validated clips missing: {', '.join(missing)}")

    assembled = job.final_dir / "assembled_video.mp4"
    concat_videos(inputs, assembled)

    final_path = job.final_dir / "final.mp4"
    shutil.copy2(assembled, final_path)
    return final_path
