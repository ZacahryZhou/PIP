"""Build VO, BGM, and final audio mix."""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from video_pipeline.config import Settings
from video_pipeline.media.ffmpeg import (
    build_vo_track,
    convert_audio_to_wav,
    mix_bgm_and_vo,
    trim_or_loop_audio,
)
from video_pipeline.pipeline.dialogue import TimedDialogueLine
from video_pipeline.pipeline.music_library import select_library_track
from video_pipeline.providers.fal_audio import generate_fal_bgm, generate_fal_tts
from video_pipeline.providers.mock_audio import generate_mock_bgm, generate_mock_tts_segment
from video_pipeline.schemas import ScriptPlan
from video_pipeline.storage import JobPaths


def _audio_dir(job: JobPaths) -> Path:
    path = job.root / "audio"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _generate_tts_segment(
    output_path: Path,
    *,
    settings: Settings,
    text: str,
    duration_sec: float,
    mock: bool,
) -> Path:
    if mock:
        return generate_mock_tts_segment(output_path, duration_sec=duration_sec)

    raw_path = output_path.with_suffix(output_path.suffix + ".raw")
    generate_fal_tts(raw_path, settings=settings, text=text)
    return convert_audio_to_wav(raw_path, output_path)


def _generate_bgm_track(
    job: JobPaths,
    script: ScriptPlan,
    *,
    settings: Settings,
    duration_sec: float,
    has_dialogue: bool,
    mock: bool,
) -> tuple[Path, dict[str, object]]:
    audio_dir = _audio_dir(job)
    bgm_wav = audio_dir / "bgm_track.wav"
    report: dict[str, object] = {
        "mode": settings.pip_bgm_mode,
        "instrumental": has_dialogue,
        "music_mood": script.music_mood,
        "music_bpm": script.music_bpm,
    }

    if mock:
        generate_mock_bgm(bgm_wav, duration_sec=duration_sec, bpm=script.music_bpm)
        report["source"] = "mock"
        return bgm_wav, report

    if settings.pip_bgm_mode == "library":
        library_path = select_library_track(
            Path(settings.pip_music_dir),
            music_mood=script.music_mood,
            music_bpm=script.music_bpm,
        )
        if library_path is not None:
            trimmed = audio_dir / "bgm_track_trimmed.wav"
            trim_or_loop_audio(library_path, trimmed, duration_sec=duration_sec)
            report["source"] = str(library_path)
            return trimmed, report

    raw_bgm = audio_dir / "bgm_track.mp3"
    generate_fal_bgm(
        raw_bgm,
        settings=settings,
        music_mood=script.music_mood,
        music_bpm=script.music_bpm,
        instrumental=has_dialogue,
    )
    convert_audio_to_wav(raw_bgm, bgm_wav)
    trimmed = audio_dir / "bgm_track_trimmed.wav"
    trim_or_loop_audio(bgm_wav, trimmed, duration_sec=duration_sec)
    report["source"] = settings.fal_bgm_model
    return trimmed, report


def build_vo_manifest(
    lines: list[TimedDialogueLine],
    segments: list[dict[str, object]],
) -> dict[str, object]:
    return {
        "lines": [asdict(line) for line in lines],
        "segments": segments,
    }


def run_audio_postproduction(
    job: JobPaths,
    script: ScriptPlan,
    dialogue_lines: list[TimedDialogueLine],
    *,
    settings: Settings,
    duration_sec: float,
    mock: bool,
) -> tuple[Path, dict[str, object]]:
    audio_dir = _audio_dir(job)
    has_dialogue = bool(dialogue_lines)
    segment_records: list[dict[str, object]] = []
    vo_segments: list[tuple[Path, float]] = []

    for line in dialogue_lines:
        segment_path = audio_dir / f"vo_{line.line_id}.wav"
        duration = max(0.2, line.end_sec - line.start_sec)
        try:
            _generate_tts_segment(
                segment_path,
                settings=settings,
                text=line.text,
                duration_sec=duration,
                mock=mock,
            )
            status = "ok"
        except Exception:  # noqa: BLE001 — retry once per AUDIO.md
            try:
                _generate_tts_segment(
                    segment_path,
                    settings=settings,
                    text=line.text,
                    duration_sec=duration,
                    mock=mock,
                )
                status = "ok"
            except Exception as retry_exc:  # noqa: BLE001
                status = "failed"
                segment_records.append(
                    {
                        "line_id": line.line_id,
                        "path": None,
                        "status": status,
                        "error": str(retry_exc),
                    }
                )
                continue

        vo_segments.append((segment_path, line.start_sec))
        segment_records.append(
            {
                "line_id": line.line_id,
                "path": str(segment_path.relative_to(job.root)),
                "status": status,
                "start_sec": line.start_sec,
                "end_sec": line.end_sec,
            }
        )

    vo_manifest_path = audio_dir / "vo_manifest.json"
    vo_manifest_path.write_text(
        json.dumps(
            build_vo_manifest(dialogue_lines, segment_records),
            indent=2,
        ),
        encoding="utf-8",
    )

    vo_track_path: Path | None = None
    if vo_segments:
        vo_track_path = audio_dir / "vo_track.wav"
        build_vo_track(vo_segments, vo_track_path, total_duration_sec=duration_sec)

    bgm_track_path, bgm_report = _generate_bgm_track(
        job,
        script,
        settings=settings,
        duration_sec=duration_sec,
        has_dialogue=has_dialogue,
        mock=mock,
    )

    bgm_volume = 0.35 if has_dialogue else 1.0
    mixed_path = audio_dir / "mixed_audio.wav"
    mix_bgm_and_vo(
        bgm_track_path,
        vo_track_path,
        mixed_path,
        bgm_volume=bgm_volume,
        fade_out_sec=1.5,
        total_duration_sec=duration_sec,
    )

    mix_report = {
        "bgm_volume": bgm_volume,
        "fade_out_sec": 1.5,
        "has_dialogue": has_dialogue,
        "vo_track": str(vo_track_path.relative_to(job.root)) if vo_track_path else None,
        "bgm_track": str(bgm_track_path.relative_to(job.root)),
        "mixed_audio": str(mixed_path.relative_to(job.root)),
        "bgm": bgm_report,
        "vo_segments": segment_records,
    }
    mix_report_path = audio_dir / "mix_report.json"
    mix_report_path.write_text(json.dumps(mix_report, indent=2), encoding="utf-8")
    return mixed_path, mix_report
