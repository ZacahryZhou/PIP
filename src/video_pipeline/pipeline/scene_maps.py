"""Scene consistency pack — master + multi-angle establishing views (V2)."""

from __future__ import annotations

import shutil
from pathlib import Path

from video_pipeline.config import Settings
from video_pipeline.media.ffmpeg import parse_resolution
from video_pipeline.pipeline.paths import scene_map_report_path
from video_pipeline.pipeline.resume import load_scene_map_report
from video_pipeline.pipeline.stage_report import StageTimer, write_stage_report
from video_pipeline.providers.fal_image import generate_fal_keyframe
from video_pipeline.providers.mock import generate_mock_scene_angle, generate_mock_scene_master
from video_pipeline.pipeline.asset_context import resolve_scenes_for_maps, visual_style_bundle
from video_pipeline.schemas import GatewayPayload, Scene, SceneMapEntry, SceneMapReport, ScriptPlan, ShotsDocument
from video_pipeline.schemas.intake import IntakePlan
from video_pipeline.schemas.plot import PlotPlan
from video_pipeline.storage import JobPaths

SCENE_ANGLES = ("wide", "medium", "detail")
REQUIRED_SCENE_ANGLE_COUNT = len(SCENE_ANGLES)


def scene_master_path(job: JobPaths, scene_id: str) -> Path:
    return job.scene_maps_dir / f"{scene_id}_master.png"


def scene_angles_dir(job: JobPaths, scene_id: str) -> Path:
    return job.scene_maps_dir / f"{scene_id}_angles"


def scene_pack_complete(entry: SceneMapEntry) -> bool:
    return (
        entry.status == "ok"
        and entry.pack_complete
        and len(entry.angle_image_paths) >= REQUIRED_SCENE_ANGLE_COUNT
    )


def build_scene_master_prompt(scene: Scene, *, visual_style: str, color_tone: str) -> str:
    parts = [
        f"Master establishing environment for {scene.location} at {scene.time_of_day}",
        scene.action_summary,
        scene.visual_style or visual_style,
        scene.color_palette or color_tone,
        f"camera intent: {scene.camera_intent or scene.camera_notes}",
        f"emotional tone: {scene.emotional_beat}",
        "cinematic scene reference, stable background, no hero close-up, wide readable composition",
    ]
    return ". ".join(part.strip() for part in parts if part and part.strip())


def build_scene_angle_prompt(
    scene: Scene,
    angle: str,
    *,
    visual_style: str,
    color_tone: str,
    has_user_reference: bool,
) -> str:
    anchor = (
        "Match the uploaded scene reference palette, layout, and lighting."
        if has_user_reference
        else build_scene_master_prompt(scene, visual_style=visual_style, color_tone=color_tone)
    )
    return (
        f"{anchor} Alternate {angle} establishing view of the same location. "
        "Consistent environment, no new props, cinematic reference sheet."
    )


def resolve_user_scene_reference(
    job: JobPaths,
    payload: GatewayPayload,
    scene_id: str,
) -> Path | None:
    for ref in payload.scene_reference_images:
        if ref.scene_id != scene_id:
            continue
        candidate = job.root / ref.path
        if candidate.is_file():
            return candidate

    for candidate in sorted(job.scene_refs_dir.glob(f"{scene_id}_ref.*")):
        if candidate.is_file():
            return candidate
    return None


def load_scene_master_map(job: JobPaths) -> dict[str, Path]:
    report_path = scene_map_report_path(job)
    if not report_path.is_file():
        return {}

    report = SceneMapReport.model_validate_json(report_path.read_text(encoding="utf-8"))
    masters: dict[str, Path] = {}
    for entry in report.entries:
        if entry.status != "ok":
            continue
        path = job.root / entry.master_image_path
        if path.is_file():
            masters[entry.scene_id] = path
    return masters


def _ensure_scene_master(
    job: JobPaths,
    scene: Scene,
    payload: GatewayPayload,
    *,
    visual_style: str,
    color_tone: str,
    settings: Settings,
    mock: bool,
    width: int,
    height: int,
) -> tuple[Path, str, str | None, str | None]:
    output = scene_master_path(job, scene.scene_id)
    user_ref = resolve_user_scene_reference(job, payload, scene.scene_id)
    prompt: str | None = None
    provider_request_id: str | None = None

    if user_ref is not None:
        shutil.copy2(user_ref, output)
        return output, "user_reference", prompt, provider_request_id

    prompt = build_scene_master_prompt(scene, visual_style=visual_style, color_tone=color_tone)
    if mock:
        generate_mock_scene_master(
            output,
            width=width,
            height=height,
            label=scene.scene_id,
        )
    else:
        if not settings.fal_key:
            raise ValueError("FAL_KEY is required for scene master generation")
        result = generate_fal_keyframe(
            output,
            api_key=settings.fal_key,
            model=settings.fal_image_model,
            prompt=prompt,
            width=width,
            height=height,
        )
        provider_request_id = result.provider_request_id
    return output, "generated", prompt, provider_request_id


def run_scene_maps(
    job: JobPaths,
    payload: GatewayPayload,
    *,
    intake_plan: IntakePlan,
    plot_plan: PlotPlan | None = None,
    script: ScriptPlan | None = None,
    shots: ShotsDocument | None = None,
    settings: Settings,
    mock: bool = False,
) -> SceneMapReport:
    del shots
    timer = StageTimer(
        job_id=job.job_id,
        stage="scene_maps",
        input_artifacts=[
            str(job.intake_plan_path.relative_to(job.root)),
            str(job.gateway_payload_path.relative_to(job.root)),
        ],
    )
    if script is not None:
        timer.input_artifacts.append(str(job.script_path.relative_to(job.root)))
    job.scene_maps_dir.mkdir(parents=True, exist_ok=True)
    width, height = parse_resolution(settings.target_resolution)
    visual_style, color_tone = visual_style_bundle(
        intake_plan=intake_plan,
        plot_plan=plot_plan,
        script=script,
    )
    entries: list[SceneMapEntry] = []
    existing = load_scene_map_report(job)
    existing_by_scene = {entry.scene_id: entry for entry in existing.entries} if existing else {}
    provider_requests = 0
    resumed_count = 0
    errors: list[str] = []

    ordered_scenes = resolve_scenes_for_maps(intake_plan, plot_plan, script)

    for scene in ordered_scenes:
        previous = existing_by_scene.get(scene.scene_id)
        if previous is not None and scene_pack_complete(previous):
            if (job.root / previous.master_image_path).is_file() and all(
                (job.root / rel).is_file() for rel in previous.angle_image_paths
            ):
                entries.append(previous)
                resumed_count += 1
                continue

        user_ref = resolve_user_scene_reference(job, payload, scene.scene_id)
        has_user_reference = user_ref is not None
        master_output = scene_master_path(job, scene.scene_id)
        master_rel = str(master_output.relative_to(job.root))
        source = "user_reference" if has_user_reference else "generated"
        prompt: str | None = None
        provider_request_id: str | None = None

        try:
            master_output, source, prompt, provider_request_id = _ensure_scene_master(
                job,
                scene,
                payload,
                visual_style=visual_style,
                color_tone=color_tone,
                settings=settings,
                mock=mock,
                width=width,
                height=height,
            )
            if provider_request_id is not None:
                provider_requests += 1

            angles_dir = scene_angles_dir(job, scene.scene_id)
            angles_dir.mkdir(parents=True, exist_ok=True)
            angle_paths: list[str] = []
            angle_failed = False
            for angle in SCENE_ANGLES:
                angle_output = angles_dir / f"{angle}.png"
                angle_prompt = build_scene_angle_prompt(
                    scene,
                    angle,
                    visual_style=visual_style,
                    color_tone=color_tone,
                    has_user_reference=has_user_reference,
                )
                if mock:
                    generate_mock_scene_angle(
                        angle_output,
                        width=width,
                        height=height,
                        label=f"{scene.scene_id}|{angle}",
                    )
                else:
                    if not settings.fal_key:
                        raise ValueError("FAL_KEY is required for scene angle generation")
                    generate_fal_keyframe(
                        angle_output,
                        api_key=settings.fal_key,
                        model=settings.fal_image_model,
                        prompt=angle_prompt,
                        width=width,
                        height=height,
                    )
                    provider_requests += 1
                angle_paths.append(str(angle_output.relative_to(job.root)))

            entries.append(
                SceneMapEntry(
                    scene_id=scene.scene_id,
                    master_image_path=str(master_output.relative_to(job.root)),
                    angle_image_paths=angle_paths,
                    pack_complete=len(angle_paths) == REQUIRED_SCENE_ANGLE_COUNT,
                    source=source,
                    status="ok",
                    prompt=prompt,
                    provider_request_id=provider_request_id,
                )
            )
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{scene.scene_id}: {exc}")
            entries.append(
                SceneMapEntry(
                    scene_id=scene.scene_id,
                    master_image_path=master_rel,
                    angle_image_paths=[],
                    pack_complete=False,
                    source=source,
                    status="failed",
                    prompt=prompt,
                    error_message=str(exc),
                )
            )

    report = SceneMapReport(job_id=job.job_id, entries=entries)
    status = "failed" if any(entry.status == "failed" for entry in entries) else "ok"
    if resumed_count and status == "ok" and provider_requests == 0:
        status = "skipped"
    envelope = timer.envelope(
        status=status,  # type: ignore[arg-type]
        output_artifacts=[str(scene_map_report_path(job).relative_to(job.root))],
        errors=errors,
        provider_request_count=provider_requests,
        resumed=resumed_count > 0 and provider_requests == 0,
    )
    write_stage_report(
        job,
        scene_map_report_path(job),
        envelope,
        report.model_dump(),
    )
    return report
