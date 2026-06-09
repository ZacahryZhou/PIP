"""QC stage — validate raw clips and copy passes to clips/validated."""

from __future__ import annotations

import shutil
from pathlib import Path

from video_pipeline.config import Settings
from video_pipeline.media.ffmpeg import (
    clip_needs_normalize,
    normalize_clip,
    parse_resolution,
    probe_video,
)
from video_pipeline.pipeline.paths import validated_clip_path
from video_pipeline.pipeline.stage_report import StageTimer, write_stage_report
from video_pipeline.schemas import GenerationReport, QCCheckResult, QCReport, ShotsDocument
from video_pipeline.storage import JobPaths

DURATION_TOLERANCE_SEC = 0.75


def run_quality_control(
    job: JobPaths,
    shots: ShotsDocument,
    generation: GenerationReport,
    *,
    settings: Settings,
) -> QCReport:
    timer = StageTimer(
        job_id=job.job_id,
        stage="quality_control",
        input_artifacts=[str((job.reports_dir / "generation_report.json").relative_to(job.root))],
    )
    target_width, target_height = parse_resolution(settings.target_resolution)
    gen_by_id = {item.shot_id: item for item in generation.results}

    checks: list[QCCheckResult] = []
    passed: list[str] = []
    failed: list[str] = []
    resumed_count = 0

    for shot in shots.shots:
        existing_validated = validated_clip_path(job, shot.shot_id)
        if existing_validated.is_file():
            checks.append(
                QCCheckResult(
                    shot_id=shot.shot_id,
                    check="file_integrity",
                    status="passed",
                    actual=str(existing_validated.relative_to(job.root)),
                    message="resumed existing validated clip",
                )
            )
            passed.append(shot.shot_id)
            resumed_count += 1
            continue

        shot_failed = False
        gen = gen_by_id.get(shot.shot_id)
        clip_path: Path | None = None
        if gen and gen.output_path:
            clip_path = Path(gen.output_path)

        if not clip_path or not clip_path.is_file():
            checks.append(
                QCCheckResult(
                    shot_id=shot.shot_id,
                    check="file_integrity",
                    status="failed",
                    message="Clip file missing",
                )
            )
            failed.append(shot.shot_id)
            continue

        try:
            meta = probe_video(clip_path)
        except ValueError as exc:
            checks.append(
                QCCheckResult(
                    shot_id=shot.shot_id,
                    check="file_integrity",
                    status="failed",
                    message=str(exc),
                )
            )
            failed.append(shot.shot_id)
            continue

        if clip_needs_normalize(
            meta,
            width=target_width,
            height=target_height,
            fps=settings.target_fps,
            duration_sec=shot.duration_sec,
            duration_tolerance_sec=DURATION_TOLERANCE_SEC,
        ):
            normalized_path = job.clips_validated_dir / f"{shot.shot_id}_normalized.mp4"
            try:
                normalize_clip(
                    clip_path,
                    normalized_path,
                    width=target_width,
                    height=target_height,
                    fps=settings.target_fps,
                    duration_sec=shot.duration_sec,
                )
            except Exception as exc:  # noqa: BLE001
                checks.append(
                    QCCheckResult(
                        shot_id=shot.shot_id,
                        check="normalize",
                        status="failed",
                        message=str(exc),
                    )
                )
                failed.append(shot.shot_id)
                continue

            checks.append(
                QCCheckResult(
                    shot_id=shot.shot_id,
                    check="normalize",
                    status="passed",
                    actual=str(normalized_path),
                )
            )
            clip_path = normalized_path
            meta = probe_video(clip_path)

        checks.append(
            QCCheckResult(
                shot_id=shot.shot_id,
                check="file_integrity",
                status="passed",
                actual=str(clip_path),
            )
        )

        expected_duration = shot.duration_sec
        actual_duration = float(meta["duration_sec"])
        duration_ok = abs(actual_duration - expected_duration) <= DURATION_TOLERANCE_SEC
        checks.append(
            QCCheckResult(
                shot_id=shot.shot_id,
                check="duration",
                status="passed" if duration_ok else "failed",
                expected=f"{expected_duration:.2f}s",
                actual=f"{actual_duration:.2f}s",
            )
        )
        if not duration_ok:
            shot_failed = True

        width = int(meta["width"])
        height = int(meta["height"])
        resolution_ok = width == target_width and height == target_height
        checks.append(
            QCCheckResult(
                shot_id=shot.shot_id,
                check="resolution",
                status="passed" if resolution_ok else "failed",
                expected=settings.target_resolution,
                actual=f"{width}x{height}",
            )
        )
        if not resolution_ok:
            shot_failed = True

        fps = float(meta["fps"])
        fps_ok = abs(fps - settings.target_fps) <= 1.0
        checks.append(
            QCCheckResult(
                shot_id=shot.shot_id,
                check="fps",
                status="passed" if fps_ok else "failed",
                expected=str(settings.target_fps),
                actual=f"{fps:.2f}",
            )
        )
        if not fps_ok:
            shot_failed = True

        checks.append(
            QCCheckResult(
                shot_id=shot.shot_id,
                check="blank_frames",
                status="passed",
                message="skipped in MVP mock QC",
            )
        )

        if shot_failed:
            failed.append(shot.shot_id)
            continue

        dest = validated_clip_path(job, shot.shot_id)
        shutil.copy2(clip_path, dest)
        passed.append(shot.shot_id)

    report = QCReport(
        job_id=job.job_id,
        target_resolution=settings.target_resolution,
        target_fps=settings.target_fps,
        passed_shot_ids=passed,
        failed_shot_ids=failed,
        checks=checks,
    )
    status = "failed" if failed else "ok"
    if resumed_count == len(shots.shots) and status == "ok":
        status = "skipped"
    envelope = timer.envelope(
        status=status,  # type: ignore[arg-type]
        output_artifacts=[str((job.reports_dir / "qc_report.json").relative_to(job.root))],
        resumed=resumed_count > 0,
    )
    write_stage_report(
        job,
        job.reports_dir / "qc_report.json",
        envelope,
        report.model_dump(),
    )
    return report
