"""Resume helpers — skip paid artifacts when files validate."""

from __future__ import annotations

from pathlib import Path

from video_pipeline.pipeline.approval import load_approval_document, load_preview_document
from video_pipeline.pipeline.paths import keyframe_end_path, keyframe_start_path, scene_map_report_path, validated_clip_path
from video_pipeline.pipeline.tts import load_tts_manifest
from video_pipeline.schemas import (
    GatewayPayload,
    RoutingPlan,
    SceneMapReport,
    ScriptPlan,
    ShotsDocument,
    StoryboardApprovalDocument,
)


def load_routing_plan(job) -> RoutingPlan | None:
    if not job.routing_path.is_file():
        return None
    return RoutingPlan.model_validate_json(job.routing_path.read_text(encoding="utf-8"))


def _keyframe_start_path(job, shot_id: str) -> Path:
    return keyframe_start_path(job, shot_id)


def _keyframe_end_path(job, shot_id: str) -> Path:
    return keyframe_end_path(job, shot_id)


def preview_matches_approval(
    job,
    *,
    shots: ShotsDocument,
    approval: StoryboardApprovalDocument | None = None,
) -> bool:
    if not job.storyboard_preview_path.is_file():
        return False
    try:
        preview = load_preview_document(job)
    except FileNotFoundError:
        return False

    approval_doc = approval or load_approval_document(job)
    if approval_doc is not None and approval_doc.preview_version != preview.preview_version:
        return False

    shot_ids = {shot.shot_id for shot in shots.shots}
    preview_ids = {item.shot_id for item in preview.items}
    if shot_ids != preview_ids:
        return False

    for item in preview.items:
        if item.status != "ok":
            return False
        frame_paths = [
            rel
            for rel in (item.start_image_path, item.end_image_path, item.preview_image_path)
            if rel
        ]
        if not frame_paths:
            return False
        for rel in frame_paths:
            if not (job.root / rel).is_file():
                return False
    return True


def scene_maps_complete(job, script: ScriptPlan) -> bool:
    report_path = scene_map_report_path(job)
    if not report_path.is_file():
        return False
    report = SceneMapReport.model_validate_json(report_path.read_text(encoding="utf-8"))
    expected = {scene.scene_id for scene in script.scene_list}
    ok_scenes = {
        entry.scene_id
        for entry in report.entries
        if entry.status == "ok" and (job.root / entry.master_image_path).is_file()
    }
    return expected <= ok_scenes


def load_scene_map_report(job) -> SceneMapReport | None:
    path = scene_map_report_path(job)
    if not path.is_file():
        return None
    return SceneMapReport.model_validate_json(path.read_text(encoding="utf-8"))


def keyframe_entry_complete(
    job,
    *,
    shot_id: str,
    generation_mode: str,
) -> bool:
    start = _keyframe_start_path(job, shot_id)
    if not start.is_file():
        return False
    if generation_mode == "first_last_frame":
        return _keyframe_end_path(job, shot_id).is_file()
    return True


def load_keyframe_report(job):
    path = job.reports_dir / "keyframe_report.json"
    if not path.is_file():
        return None
    from video_pipeline.schemas import KeyframeReport

    return KeyframeReport.model_validate_json(path.read_text(encoding="utf-8"))


def keyframes_complete(job, routing: RoutingPlan) -> bool:
    report = load_keyframe_report(job)
    if report is None:
        return False
    by_shot = {item.shot_id: item for item in report.results}
    for route in routing.routes:
        if route.generation_mode == "t2v":
            continue
        item = by_shot.get(route.shot_id)
        if item is None or item.status != "success":
            return False
        if not keyframe_entry_complete(
            job,
            shot_id=route.shot_id,
            generation_mode=route.generation_mode,
        ):
            return False
    return True


def load_generation_report(job):
    path = job.reports_dir / "generation_report.json"
    if not path.is_file():
        return None
    from video_pipeline.schemas import GenerationReport

    return GenerationReport.model_validate_json(path.read_text(encoding="utf-8"))


def generation_output_path(job, shot_id: str, result) -> Path | None:
    if not result.output_path:
        return None
    candidate = Path(result.output_path)
    if not candidate.is_absolute():
        candidate = job.root / candidate
    return candidate if candidate.is_file() else None


def raw_clips_complete(job, shots: ShotsDocument, routing: RoutingPlan) -> bool:
    report = load_generation_report(job)
    if report is None:
        return False
    by_shot = {item.shot_id: item for item in report.results}
    for shot in shots.shots:
        item = by_shot.get(shot.shot_id)
        if item is None or item.status != "success":
            return False
        if generation_output_path(job, shot.shot_id, item) is None:
            return False
    return True


def validated_clips_complete(job, shots: ShotsDocument) -> bool:
    for shot in shots.shots:
        if not validated_clip_path(job, shot.shot_id).is_file():
            return False
    return True


def tts_complete(job) -> bool:
    manifest = load_tts_manifest(job)
    if manifest is None:
        return False
    if not manifest.segments:
        return True
    for entry in manifest.segments:
        if entry.status != "ok" or not entry.wav_path:
            return False
        if not (job.root / entry.wav_path).is_file():
            return False
    return True


def resolve_gateway_payload(job) -> GatewayPayload:
    return GatewayPayload.model_validate_json(job.gateway_payload_path.read_text(encoding="utf-8"))
