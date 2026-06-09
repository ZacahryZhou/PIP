"""Build VO, BGM, and final audio mix."""

from __future__ import annotations

import json
import shutil
from dataclasses import asdict
from pathlib import Path

from video_pipeline.config import Settings
from video_pipeline.media.ffmpeg import (
    build_vo_track,
    mix_bgm_and_vo,
    trim_or_loop_audio,
)
from video_pipeline.pipeline.dialogue import TimedDialogueLine
from video_pipeline.pipeline.bgm_prep import (
    generate_bgm_track_early,
    load_bgm_prep_report,
    prepared_bgm_track_path,
)
from video_pipeline.pipeline.tts import load_tts_manifest, vo_segment_path
from video_pipeline.providers.tts.base import TTSRequest, resolve_tts_provider
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
    provider = resolve_tts_provider(settings=settings, mock=mock)
    voice = settings.elevenlabs_voice_id
    language = settings.pip_default_language
    request = TTSRequest(
        text=text,
        voice=voice,
        language=language,
        output_path=output_path,
        estimated_duration_sec=duration_sec,
    )
    provider.synthesize(request)
    return output_path


def _generate_bgm_track(
    job: JobPaths,
    script: ScriptPlan,
    *,
    settings: Settings,
    duration_sec: float,
    has_dialogue: bool,
    mock: bool,
) -> tuple[Path, dict[str, object]]:
    prepared = prepared_bgm_track_path(job)
    if prepared.is_file():
        trimmed = _audio_dir(job) / "bgm_track_trimmed.wav"
        trim_or_loop_audio(prepared, trimmed, duration_sec=duration_sec)
        report: dict[str, object] = {
            "mode": settings.pip_bgm_mode,
            "instrumental": has_dialogue,
            "music_mood": script.music_mood,
            "music_bpm": script.music_bpm,
            "source": "prepared",
            "prepared_path": str(prepared.relative_to(job.root)),
        }
        prep = load_bgm_prep_report(job)
        if prep is not None and prep.source:
            report["source"] = prep.source
        return trimmed, report

    output_path = _audio_dir(job) / "bgm_track_trimmed.wav"
    track_path, report = generate_bgm_track_early(
        job,
        script,
        settings=settings,
        duration_sec=duration_sec,
        has_dialogue=has_dialogue,
        mock=mock,
        output_path=output_path,
    )
    return track_path, report


def build_vo_manifest(
    lines: list[TimedDialogueLine],
    segments: list[dict[str, object]],
) -> dict[str, object]:
    return {
        "lines": [asdict(line) for line in lines],
        "segments": segments,
    }


def _resolve_tts_segment(
    job: JobPaths,
    line: TimedDialogueLine,
    *,
    settings: Settings,
    mock: bool,
    tts_by_line: dict[str, str],
) -> tuple[Path | None, dict[str, object]]:
    segment_path = vo_segment_path(job, line.line_id)
    duration = max(0.2, line.end_sec - line.start_sec)

    if line.line_id in tts_by_line:
        existing = job.root / tts_by_line[line.line_id]
        if existing.is_file():
            return existing, {
                "line_id": line.line_id,
                "path": str(existing.relative_to(job.root)),
                "status": "ok",
                "start_sec": line.start_sec,
                "end_sec": line.end_sec,
                "source": "tts_manifest",
            }

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
            return None, {
                "line_id": line.line_id,
                "path": None,
                "status": "failed",
                "error": str(retry_exc),
            }

    return segment_path, {
        "line_id": line.line_id,
        "path": str(segment_path.relative_to(job.root)),
        "status": status,
        "start_sec": line.start_sec,
        "end_sec": line.end_sec,
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

    tts_manifest = load_tts_manifest(job)
    tts_by_line: dict[str, str] = {}
    if tts_manifest is not None:
        for entry in tts_manifest.segments:
            if entry.status == "ok" and entry.wav_path:
                tts_by_line[entry.line_id] = entry.wav_path

    for line in dialogue_lines:
        segment_path, record = _resolve_tts_segment(
            job,
            line,
            settings=settings,
            mock=mock,
            tts_by_line=tts_by_line,
        )
        segment_records.append(record)
        if segment_path is not None and record.get("status") == "ok":
            vo_segments.append((segment_path, line.start_sec))

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

    bgm_mode = (settings.pip_bgm_mode or "off").strip().lower()
    if bgm_mode == "off":
        mixed_path = audio_dir / "mixed_audio.wav"
        if vo_track_path is not None:
            shutil.copy2(vo_track_path, mixed_path)
        else:
            from video_pipeline.providers.mock_audio import generate_mock_tts_segment

            generate_mock_tts_segment(mixed_path, duration_sec=duration_sec)
        mix_report = {
            "bgm_mode": "off",
            "has_dialogue": has_dialogue,
            "vo_track": str(vo_track_path.relative_to(job.root)) if vo_track_path else None,
            "mixed_audio": str(mixed_path.relative_to(job.root)),
            "vo_segments": segment_records,
        }
        mix_report_path = audio_dir / "mix_report.json"
        mix_report_path.write_text(json.dumps(mix_report, indent=2), encoding="utf-8")
        return mixed_path, mix_report

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
        "tts_manifest": str((audio_dir / "tts_manifest.json").relative_to(job.root))
        if (audio_dir / "tts_manifest.json").is_file()
        else None,
    }
    mix_report_path = audio_dir / "mix_report.json"
    mix_report_path.write_text(json.dumps(mix_report, indent=2), encoding="utf-8")
    return mixed_path, mix_report
