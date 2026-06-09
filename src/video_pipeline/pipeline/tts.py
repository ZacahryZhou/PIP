"""Early TTS generation — runs in parallel with scene maps / keyframes / video."""

from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from video_pipeline.config import Settings
from video_pipeline.pipeline.dialogue import collect_dialogue_text_specs, DialogueTextSpec
from video_pipeline.pipeline.stage_report import StageTimer, write_stage_report
from video_pipeline.providers.tts.base import TTSRequest, resolve_tts_provider
from video_pipeline.schemas import ScriptPlan, ShotsDocument, TTSManifest, TTSManifestEntry, TTSReport
from video_pipeline.schemas.tts import DialogueTextSpec as DialogueTextSpecModel
from video_pipeline.storage import JobPaths, write_json


def tts_manifest_path(job: JobPaths) -> Path:
    return job.root / "audio" / "tts_manifest.json"


def tts_report_path(job: JobPaths) -> Path:
    return job.reports_dir / "tts_report.json"


def vo_segment_path(job: JobPaths, line_id: str) -> Path:
    return job.root / "audio" / f"vo_{line_id}.wav"


def load_tts_manifest(job: JobPaths) -> TTSManifest | None:
    path = tts_manifest_path(job)
    if not path.is_file():
        return None
    return TTSManifest.model_validate_json(path.read_text(encoding="utf-8"))


def _manifest_is_complete(job: JobPaths, manifest: TTSManifest) -> bool:
    if not manifest.segments:
        return True
    for entry in manifest.segments:
        if entry.status != "ok":
            return False
        if not entry.wav_path:
            return False
        wav = job.root / entry.wav_path
        if not wav.is_file():
            return False
    return True


def _synthesize_line(
    job: JobPaths,
    spec: DialogueTextSpec,
    *,
    settings: Settings,
    mock: bool,
    voice: str,
    language: str,
    provider_name: str,
) -> TTSManifestEntry:
    output_path = vo_segment_path(job, spec.line_id)
    provider = resolve_tts_provider(settings=settings, mock=mock)
    request = TTSRequest(
        text=spec.text,
        voice=voice,
        language=language,
        output_path=output_path,
        estimated_duration_sec=spec.estimated_duration_sec,
    )
    try:
        result = provider.synthesize(request)
        return TTSManifestEntry(
            line_id=spec.line_id,
            text=spec.text,
            wav_path=str(result.output_path.relative_to(job.root)),
            status="ok",
            duration_sec=result.duration_sec,
            provider=result.provider or provider_name,
        )
    except Exception as exc:  # noqa: BLE001 — retry once below
        try:
            result = provider.synthesize(request)
            return TTSManifestEntry(
                line_id=spec.line_id,
                text=spec.text,
                wav_path=str(result.output_path.relative_to(job.root)),
                status="ok",
                duration_sec=result.duration_sec,
                provider=result.provider or provider_name,
            )
        except Exception as retry_exc:  # noqa: BLE001
            return TTSManifestEntry(
                line_id=spec.line_id,
                text=spec.text,
                wav_path=None,
                status="failed",
                provider=provider_name,
                error=str(retry_exc),
            )


def run_tts_prep(
    job: JobPaths,
    script: ScriptPlan,
    shots: ShotsDocument,
    *,
    settings: Settings,
    mock: bool,
) -> TTSReport:
    """Generate per-line VO wav files after storyboard approval."""
    started = time.monotonic()
    timer = StageTimer(job_id=job.job_id, stage="tts", input_artifacts=[str(job.shots_path.relative_to(job.root))])
    audio_dir = job.root / "audio"
    audio_dir.mkdir(parents=True, exist_ok=True)

    voice = (
        settings.fal_tts_voice
        if (settings.pip_tts_provider or "fal").strip().lower() == "fal"
        else settings.elevenlabs_voice_id
    )
    language = settings.pip_default_language
    provider_name = "mock" if mock else (settings.pip_tts_provider or "fal").strip().lower()

    existing = load_tts_manifest(job)
    if existing is not None and _manifest_is_complete(job, existing):
        report = TTSReport(
            job_id=job.job_id,
            provider=existing.provider,
            status="ok" if existing.segments else "skipped",
            segment_count=len(existing.segments),
            failed_line_ids=[
                entry.line_id for entry in existing.segments if entry.status == "failed"
            ],
            manifest_path=str(tts_manifest_path(job).relative_to(job.root)),
            resumed=True,
            elapsed_sec=time.monotonic() - started,
        )
        envelope = timer.envelope(
            status=report.status,  # type: ignore[arg-type]
            output_artifacts=[report.manifest_path, str(tts_report_path(job).relative_to(job.root))],
            resumed=True,
        )
        write_stage_report(job, tts_report_path(job), envelope, report.model_dump())
        return report

    line_specs = collect_dialogue_text_specs(script, shots)
    if not line_specs:
        manifest = TTSManifest(
            job_id=job.job_id,
            provider=provider_name,
            voice=voice,
            language=language,
            lines=[],
            segments=[],
        )
        write_json(tts_manifest_path(job), manifest.model_dump())
        report = TTSReport(
            job_id=job.job_id,
            provider=provider_name,
            status="skipped",
            segment_count=0,
            manifest_path=str(tts_manifest_path(job).relative_to(job.root)),
            elapsed_sec=time.monotonic() - started,
        )
        envelope = timer.envelope(
            status="skipped",
            output_artifacts=[report.manifest_path, str(tts_report_path(job).relative_to(job.root))],
        )
        write_stage_report(job, tts_report_path(job), envelope, report.model_dump())
        return report

    model_specs = [
        DialogueTextSpecModel(
            line_id=spec.line_id,
            speaker=spec.speaker,
            text=spec.text,
            source=spec.source,
            estimated_duration_sec=spec.estimated_duration_sec,
        )
        for spec in line_specs
    ]

    segments: list[TTSManifestEntry] = []
    max_workers = min(len(line_specs), max(1, settings.max_concurrent_shots))
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(
                _synthesize_line,
                job,
                spec,
                settings=settings,
                mock=mock,
                voice=voice,
                language=language,
                provider_name=provider_name,
            ): spec.line_id
            for spec in line_specs
        }
        for future in as_completed(futures):
            segments.append(future.result())

    segments.sort(key=lambda entry: entry.line_id)
    failed_line_ids = [entry.line_id for entry in segments if entry.status == "failed"]

    manifest = TTSManifest(
        job_id=job.job_id,
        provider=provider_name,
        voice=voice,
        language=language,
        lines=model_specs,
        segments=segments,
    )
    write_json(tts_manifest_path(job), manifest.model_dump())

    status = "failed" if failed_line_ids else "ok"
    report = TTSReport(
        job_id=job.job_id,
        provider=provider_name,
        status=status,
        segment_count=len(segments),
        failed_line_ids=failed_line_ids,
        manifest_path=str(tts_manifest_path(job).relative_to(job.root)),
        elapsed_sec=time.monotonic() - started,
    )
    envelope = timer.envelope(
        status=status,  # type: ignore[arg-type]
        output_artifacts=[report.manifest_path, str(tts_report_path(job).relative_to(job.root))],
        errors=[f"{line_id}: failed" for line_id in failed_line_ids],
        provider_request_count=0 if mock else len([entry for entry in segments if entry.status == "ok"]),
    )
    write_stage_report(job, tts_report_path(job), envelope, report.model_dump())
    return report
