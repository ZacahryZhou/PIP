"""Early BGM generation after storyboard approval."""

from __future__ import annotations

from pathlib import Path

from video_pipeline.config import Settings
from video_pipeline.media.ffmpeg import convert_audio_to_wav, trim_or_loop_audio
from video_pipeline.pipeline.dialogue import collect_dialogue_text_specs
from video_pipeline.pipeline.music_library import select_library_track
from video_pipeline.providers.fal_audio import generate_fal_bgm
from video_pipeline.providers.mock_audio import generate_mock_bgm
from video_pipeline.schemas import BGMPrepReport, ScriptPlan, ShotsDocument
from video_pipeline.storage import JobPaths, write_json


def bgm_prep_report_path(job: JobPaths) -> Path:
    return job.reports_dir / "bgm_prep_report.json"


def prepared_bgm_track_path(job: JobPaths) -> Path:
    return job.root / "audio" / "bgm_prepared.wav"


def estimate_video_duration_sec(shots: ShotsDocument) -> float:
    return float(sum(shot.duration_sec for shot in shots.shots))


def load_bgm_prep_report(job: JobPaths) -> BGMPrepReport | None:
    path = bgm_prep_report_path(job)
    if not path.is_file():
        return None
    return BGMPrepReport.model_validate_json(path.read_text(encoding="utf-8"))


def generate_bgm_track_early(
    job: JobPaths,
    script: ScriptPlan,
    *,
    settings: Settings,
    duration_sec: float,
    has_dialogue: bool,
    mock: bool,
    output_path: Path,
) -> tuple[Path, dict[str, object]]:
    """Select or generate BGM after approval; trimmed to estimated storyboard duration."""
    audio_dir = job.root / "audio"
    audio_dir.mkdir(parents=True, exist_ok=True)
    report: dict[str, object] = {
        "mode": settings.pip_bgm_mode,
        "instrumental": has_dialogue,
        "music_mood": script.music_mood,
        "music_bpm": script.music_bpm,
        "estimated_duration_sec": duration_sec,
    }

    if mock:
        generate_mock_bgm(output_path, duration_sec=duration_sec, bpm=script.music_bpm)
        report["source"] = "mock"
        return output_path, report

    if settings.pip_bgm_mode == "library":
        library_path = select_library_track(
            Path(settings.pip_music_dir),
            music_mood=script.music_mood,
            music_bpm=script.music_bpm,
        )
        if library_path is not None:
            trim_or_loop_audio(library_path, output_path, duration_sec=duration_sec)
            report["source"] = str(library_path)
            return output_path, report

    raw_bgm = audio_dir / "bgm_track.mp3"
    generate_fal_bgm(
        raw_bgm,
        settings=settings,
        music_mood=script.music_mood,
        music_bpm=script.music_bpm,
        instrumental=has_dialogue,
    )
    bgm_wav = audio_dir / "bgm_track.wav"
    convert_audio_to_wav(raw_bgm, bgm_wav)
    trim_or_loop_audio(bgm_wav, output_path, duration_sec=duration_sec)
    report["source"] = settings.fal_bgm_model
    return output_path, report


def run_bgm_prep(
    job: JobPaths,
    script: ScriptPlan,
    shots: ShotsDocument,
    *,
    settings: Settings,
    mock: bool,
) -> BGMPrepReport:
    """Generate or select BGM after approval; final trim happens at postproduction."""
    bgm_mode = (settings.pip_bgm_mode or "off").strip().lower()
    if bgm_mode == "off":
        report = BGMPrepReport(
            job_id=job.job_id,
            mode="off",
            status="skipped",
            instrumental=bool(collect_dialogue_text_specs(script, shots)),
            music_mood=script.music_mood,
            music_bpm=script.music_bpm,
            estimated_duration_sec=estimate_video_duration_sec(shots),
        )
        write_json(bgm_prep_report_path(job), report.model_dump())
        return report

    audio_dir = job.root / "audio"
    audio_dir.mkdir(parents=True, exist_ok=True)

    prepared_path = prepared_bgm_track_path(job)
    existing = load_bgm_prep_report(job)
    if existing is not None and existing.status == "ok" and prepared_path.is_file():
        return existing

    has_dialogue = bool(collect_dialogue_text_specs(script, shots))
    duration_sec = estimate_video_duration_sec(shots)

    try:
        track_path, bgm_meta = generate_bgm_track_early(
            job,
            script,
            settings=settings,
            duration_sec=duration_sec,
            has_dialogue=has_dialogue,
            mock=mock,
            output_path=prepared_path,
        )
    except Exception as exc:  # noqa: BLE001
        report = BGMPrepReport(
            job_id=job.job_id,
            mode=settings.pip_bgm_mode,
            status="failed",
            instrumental=has_dialogue,
            music_mood=script.music_mood,
            music_bpm=script.music_bpm,
            estimated_duration_sec=duration_sec,
            error=str(exc),
        )
        write_json(bgm_prep_report_path(job), report.model_dump())
        return report

    report = BGMPrepReport(
        job_id=job.job_id,
        mode=str(bgm_meta.get("mode", settings.pip_bgm_mode)),
        status="ok",
        source=str(bgm_meta.get("source")) if bgm_meta.get("source") else None,
        instrumental=has_dialogue,
        music_mood=script.music_mood,
        music_bpm=script.music_bpm,
        estimated_duration_sec=duration_sec,
        bgm_track_path=str(track_path.relative_to(job.root)),
    )
    write_json(bgm_prep_report_path(job), report.model_dump())
    return report
