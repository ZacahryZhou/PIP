"""Character turnaround pack — multi-angle consistency assets (V2)."""

from __future__ import annotations

import shutil
from pathlib import Path

from video_pipeline.config import Settings
from video_pipeline.media.ffmpeg import parse_resolution
from video_pipeline.pipeline.stage_report import StageTimer, write_stage_report
from video_pipeline.providers.fal_image import generate_fal_keyframe
from video_pipeline.providers.mock import generate_mock_character_angle
from video_pipeline.pipeline.asset_context import resolve_character_ids, visual_style_bundle
from video_pipeline.schemas import (
    CharacterAssetEntry,
    CharacterAssetReport,
    GatewayPayload,
    ScriptPlan,
    ShotsDocument,
)
from video_pipeline.schemas.intake import IntakePlan
from video_pipeline.schemas.plot import PlotPlan
from video_pipeline.storage import JobPaths, write_json

CHARACTER_ANGLES = ("front", "side", "three_quarter")
REQUIRED_ANGLE_COUNT = len(CHARACTER_ANGLES)


def character_turnaround_dir(job: JobPaths, character_id: str) -> Path:
    return job.character_assets_dir / f"{character_id}_turnaround"


def character_asset_report_path(job: JobPaths) -> Path:
    return job.reports_dir / "character_asset_report.json"


def collect_character_ids(
    payload: GatewayPayload,
    intake_plan: IntakePlan | None = None,
    script: ScriptPlan | None = None,
    shots: ShotsDocument | None = None,
) -> list[str]:
    if intake_plan is not None:
        return resolve_character_ids(payload, intake_plan, script, shots)
    ids: set[str] = set(payload.character_ids)
    if script is not None:
        ids.update(script.characters_in_use)
    if shots is not None:
        for shot in shots.shots:
            if shot.has_characters:
                ids.update(shot.character_ids)
    return sorted(ids)


def resolve_user_character_reference(
    job: JobPaths,
    payload: GatewayPayload,
    character_id: str,
) -> Path | None:
    for ref in payload.character_reference_images:
        if ref.character_id != character_id:
            continue
        candidate = job.root / ref.path
        if candidate.is_file():
            return candidate
    for candidate in sorted(job.character_refs_dir.glob(f"{character_id}_ref.*")):
        if candidate.is_file():
            return candidate
    return None


def build_character_angle_prompt(
    character_id: str,
    angle: str,
    *,
    visual_style: str,
    color_tone: str,
    has_user_reference: bool,
) -> str:
    anchor = (
        "Match the uploaded reference identity, wardrobe, and proportions."
        if has_user_reference
        else f"Character {character_id} from script visual style."
    )
    return (
        f"{anchor} Turnaround {angle} view on neutral background. "
        f"{visual_style}. {color_tone}. "
        "Full body readable, consistent design, no text, cinematic reference sheet."
    )


def load_character_asset_report(job: JobPaths) -> CharacterAssetReport | None:
    path = character_asset_report_path(job)
    if not path.is_file():
        return None
    return CharacterAssetReport.model_validate_json(path.read_text(encoding="utf-8"))


def character_pack_complete(entry: CharacterAssetEntry) -> bool:
    return entry.status == "ok" and len(entry.angle_image_paths) >= REQUIRED_ANGLE_COUNT


def run_character_assets(
    job: JobPaths,
    payload: GatewayPayload,
    *,
    intake_plan: IntakePlan,
    script: ScriptPlan | None = None,
    shots: ShotsDocument | None = None,
    plot_plan: PlotPlan | None = None,
    settings: Settings,
    mock: bool = False,
) -> CharacterAssetReport:
    timer = StageTimer(
        job_id=job.job_id,
        stage="character_assets",
        input_artifacts=[
            str(job.intake_plan_path.relative_to(job.root)),
            str(job.gateway_payload_path.relative_to(job.root)),
        ],
    )
    if script is not None:
        timer.input_artifacts.append(str(job.script_path.relative_to(job.root)))
    job.character_assets_dir.mkdir(parents=True, exist_ok=True)
    width, height = parse_resolution(settings.target_resolution)
    visual_style, color_tone = visual_style_bundle(
        intake_plan=intake_plan,
        plot_plan=plot_plan,
        script=script,
    )
    existing = load_character_asset_report(job)
    existing_by_id = {entry.character_id: entry for entry in existing.entries} if existing else {}
    provider_requests = 0
    resumed_count = 0
    errors: list[str] = []
    entries: list[CharacterAssetEntry] = []

    for character_id in collect_character_ids(payload, intake_plan, script, shots):
        turnaround = character_turnaround_dir(job, character_id)
        turnaround.mkdir(parents=True, exist_ok=True)
        previous = existing_by_id.get(character_id)
        if previous is not None and character_pack_complete(previous):
            if all((job.root / rel).is_file() for rel in previous.angle_image_paths):
                entries.append(previous)
                resumed_count += 1
                continue

        user_ref = resolve_user_character_reference(job, payload, character_id)
        user_ref_rel = (
            str(user_ref.relative_to(job.root)) if user_ref is not None else None
        )
        source = "user_reference" if user_ref is not None else "generated"
        angle_paths: list[str] = []
        angle_failed = False

        for angle in CHARACTER_ANGLES:
            output = turnaround / f"{angle}.png"
            rel = str(output.relative_to(job.root))
            prompt = build_character_angle_prompt(
                character_id,
                angle,
                visual_style=visual_style,
                color_tone=color_tone,
                has_user_reference=user_ref is not None,
            )
            try:
                if mock:
                    generate_mock_character_angle(
                        output,
                        width=width,
                        height=height,
                        label=f"{character_id}|{angle}",
                    )
                else:
                    if not settings.fal_key:
                        raise ValueError("FAL_KEY is required for character asset generation")
                    generate_fal_keyframe(
                        output,
                        api_key=settings.fal_key,
                        model=settings.fal_image_model,
                        prompt=prompt,
                        width=width,
                        height=height,
                    )
                    provider_requests += 1
                angle_paths.append(rel)
            except Exception as exc:  # noqa: BLE001
                angle_failed = True
                errors.append(f"{character_id}/{angle}: {exc}")

        status = "ok" if not angle_failed and len(angle_paths) == REQUIRED_ANGLE_COUNT else "failed"
        entries.append(
            CharacterAssetEntry(
                character_id=character_id,
                user_reference_path=user_ref_rel,
                turnaround_dir=str(turnaround.relative_to(job.root)),
                angle_image_paths=angle_paths,
                source=source,
                status=status,
                error_message=None if status == "ok" else "Incomplete character turnaround pack",
            )
        )

    report = CharacterAssetReport(job_id=job.job_id, entries=entries)
    status = "failed" if any(entry.status == "failed" for entry in entries) else "ok"
    if resumed_count and status == "ok" and provider_requests == 0:
        status = "skipped"
    envelope = timer.envelope(
        status=status,  # type: ignore[arg-type]
        output_artifacts=[str(character_asset_report_path(job).relative_to(job.root))],
        errors=errors,
        provider_request_count=provider_requests,
        resumed=resumed_count > 0 and provider_requests == 0,
    )
    write_stage_report(
        job,
        character_asset_report_path(job),
        envelope,
        report.model_dump(),
    )
    return report
