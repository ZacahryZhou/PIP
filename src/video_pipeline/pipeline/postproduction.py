"""Post-production — assemble video, subtitles, and mixed audio."""

from __future__ import annotations

from pathlib import Path

from video_pipeline.config import Settings
from video_pipeline.media.ffmpeg import concat_videos, mux_video_with_audio
from video_pipeline.pipeline.audio_post import run_audio_postproduction
from video_pipeline.pipeline.dialogue import collect_dialogue_lines
from video_pipeline.pipeline.paths import validated_clip_path
from video_pipeline.pipeline.subtitles import burn_subtitles_into_video, write_srt
from video_pipeline.pipeline.timeline import build_timeline, save_timeline
from video_pipeline.schemas import ScriptPlan, ShotsDocument
from video_pipeline.storage import JobPaths


def run_postproduction(
    job: JobPaths,
    script: ScriptPlan,
    shots: ShotsDocument,
    *,
    settings: Settings,
    mock: bool = False,
) -> Path:
    ordered = sorted(shots.shots, key=lambda shot: shot.shot_id)
    inputs = [validated_clip_path(job, shot.shot_id) for shot in ordered]
    missing = [str(path) for path in inputs if not path.is_file()]
    if missing:
        raise FileNotFoundError(f"Validated clips missing: {', '.join(missing)}")

    timeline = build_timeline(job, shots)
    save_timeline(job.final_dir / "timeline.json", timeline)

    assembled = job.final_dir / "assembled_video.mp4"
    concat_videos(inputs, assembled)

    dialogue_lines = collect_dialogue_lines(script, shots, timeline)
    language = settings.pip_default_language

    video_for_mux = assembled
    if dialogue_lines:
        srt_path = job.final_dir / "final.srt"
        write_srt(srt_path, dialogue_lines, language=language)
        subtitled = job.final_dir / "subtitled_video.mp4"
        burn_subtitles_into_video(
            assembled,
            srt_path,
            subtitled,
            language=language,
        )
        video_for_mux = subtitled

    mixed_audio, _mix_report = run_audio_postproduction(
        job,
        script,
        dialogue_lines,
        settings=settings,
        duration_sec=timeline.final_duration_sec,
        mock=mock,
    )

    final_path = job.final_dir / "final.mp4"
    mux_video_with_audio(video_for_mux, mixed_audio, final_path)
    return final_path
