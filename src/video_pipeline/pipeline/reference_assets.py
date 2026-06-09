"""Reference Agent — process other_reference_images from Intake; generate when missing."""

from __future__ import annotations

import shutil
from pathlib import Path

from video_pipeline.config import Settings
from video_pipeline.media.ffmpeg import parse_resolution
from video_pipeline.pipeline.stage_report import StageTimer, write_stage_report
from video_pipeline.providers.fal_image import generate_fal_keyframe
from video_pipeline.providers.mock import generate_mock_keyframe
from video_pipeline.schemas import GatewayPayload
from video_pipeline.schemas.intake import IntakePlan
from video_pipeline.schemas.reference_asset import ReferenceAssetEntry, ReferenceAssetReport
from video_pipeline.storage import JobPaths, write_json


def reference_assets_dir(job: JobPaths) -> Path:
    return job.assets_dir / "references"


def reference_asset_report_path(job: JobPaths) -> Path:
    return job.reports_dir / "reference_asset_report.json"


def load_reference_asset_report(job: JobPaths) -> ReferenceAssetReport | None:
    path = reference_asset_report_path(job)
    if not path.is_file():
        return None
    return ReferenceAssetReport.model_validate_json(path.read_text(encoding="utf-8"))


def _resolve_reference_file(job: JobPaths, rel_path: str | None) -> Path | None:
    if not rel_path:
        return None
    candidate = job.root / rel_path
    return candidate if candidate.is_file() else None


def run_reference_assets(
    job: JobPaths,
    intake_plan: IntakePlan,
    payload: GatewayPayload,
    *,
    settings: Settings,
    mock: bool = False,
) -> ReferenceAssetReport:
    timer = StageTimer(
        job_id=job.job_id,
        stage="reference_assets",
        input_artifacts=[
            str(job.intake_plan_path.relative_to(job.root)),
            str(job.gateway_payload_path.relative_to(job.root)),
        ],
    )
    out_dir = reference_assets_dir(job)
    out_dir.mkdir(parents=True, exist_ok=True)
    width, height = parse_resolution(settings.target_resolution)

    existing = load_reference_asset_report(job)
    existing_by_id = {entry.ref_id: entry for entry in existing.entries} if existing else {}
    entries: list[ReferenceAssetEntry] = []
    errors: list[str] = []
    provider_requests = 0

    jobs = list(intake_plan.reference_jobs)
    if not jobs and payload.other_reference_images:
        from video_pipeline.schemas.intake import ReferenceIntakeJob

        jobs = [
            ReferenceIntakeJob(
                ref_id=ref.ref_id,
                kind=ref.kind_hint or "other",
                reference_path=ref.path,
                linked_scene_id=ref.linked_scene_id,
                linked_character_id=ref.linked_character_id,
            )
            for ref in payload.other_reference_images
        ]

    if not jobs:
        report = ReferenceAssetReport(job_id=job.job_id, entries=[])
        write_json(reference_asset_report_path(job), report)
        envelope = timer.envelope(
            status="skipped",
            output_artifacts=[str(reference_asset_report_path(job).relative_to(job.root))],
            errors=[],
            provider_request_count=0,
            resumed=False,
        )
        write_stage_report(job, reference_asset_report_path(job), envelope, report.model_dump())
        return report

    for ref_job in jobs:
        previous = existing_by_id.get(ref_job.ref_id)
        if previous is not None and previous.status == "ok" and previous.asset_path:
            if (job.root / previous.asset_path).is_file():
                entries.append(previous)
                continue

        user_file = _resolve_reference_file(job, ref_job.reference_path)
        output = out_dir / f"{ref_job.ref_id}.png"
        rel_path = str(output.relative_to(job.root))

        try:
            if user_file is not None:
                shutil.copy2(user_file, output)
                entries.append(
                    ReferenceAssetEntry(
                        ref_id=ref_job.ref_id,
                        kind=ref_job.kind,
                        asset_path=rel_path,
                        source="user_upload",
                        status="ok",
                        linked_scene_id=ref_job.linked_scene_id,
                        linked_character_id=ref_job.linked_character_id,
                    )
                )
                continue

            prompt = (
                f"Reference image for {ref_job.kind}: {ref_job.notes or ref_job.ref_id}. "
                "Clean product-style reference, no text, cinematic."
            )
            if mock:
                generate_mock_keyframe(
                    output,
                    width=width,
                    height=height,
                    label=ref_job.ref_id,
                )
            else:
                if not settings.fal_key:
                    raise ValueError("FAL_KEY is required for reference asset generation")
                generate_fal_keyframe(
                    output,
                    api_key=settings.fal_key,
                    model=settings.fal_image_model,
                    prompt=prompt,
                    width=width,
                    height=height,
                )
                provider_requests += 1

            entries.append(
                ReferenceAssetEntry(
                    ref_id=ref_job.ref_id,
                    kind=ref_job.kind,
                    asset_path=rel_path,
                    source="generated",
                    status="ok",
                    linked_scene_id=ref_job.linked_scene_id,
                    linked_character_id=ref_job.linked_character_id,
                    prompt=prompt,
                )
            )
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{ref_job.ref_id}: {exc}")
            entries.append(
                ReferenceAssetEntry(
                    ref_id=ref_job.ref_id,
                    kind=ref_job.kind,
                    asset_path=None,
                    source="generated",
                    status="failed",
                    linked_scene_id=ref_job.linked_scene_id,
                    linked_character_id=ref_job.linked_character_id,
                    error_message=str(exc),
                )
            )

    report = ReferenceAssetReport(job_id=job.job_id, entries=entries)
    status = "failed" if any(entry.status == "failed" for entry in entries) else "ok"
    envelope = timer.envelope(
        status=status,  # type: ignore[arg-type]
        output_artifacts=[str(reference_asset_report_path(job).relative_to(job.root))],
        errors=errors,
        provider_request_count=provider_requests,
        resumed=False,
    )
    write_stage_report(job, reference_asset_report_path(job), envelope, report.model_dump())
    write_json(reference_asset_report_path(job), report)
    return report
