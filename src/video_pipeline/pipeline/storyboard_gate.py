"""Storyboard gate — block video until V2 asset + preview requirements are met."""

from __future__ import annotations

from dataclasses import dataclass, field

from video_pipeline.pipeline.approval import load_approval_document
from video_pipeline.pipeline.character_assets import (
    character_pack_complete,
    load_character_asset_report,
)
from video_pipeline.pipeline.resume import load_scene_map_report
from video_pipeline.pipeline.scene_maps import scene_pack_complete
from video_pipeline.schemas import ShotsDocument
from video_pipeline.storage import JobPaths


@dataclass(frozen=True)
class StoryboardGateResult:
    passed: bool
    blocking_reasons: list[str] = field(default_factory=list)


def validate_storyboard_gate(
    job: JobPaths,
    shots: ShotsDocument,
    *,
    require_user_approval: bool = True,
) -> StoryboardGateResult:
    reasons: list[str] = []

    character_report = load_character_asset_report(job)
    if character_report is None:
        reasons.append("Missing character_asset_report.json")
    else:
        needed_characters = {
            character_id
            for shot in shots.shots
            if shot.has_characters
            for character_id in shot.character_ids
        }
        report_by_id = {entry.character_id: entry for entry in character_report.entries}
        for character_id in sorted(needed_characters):
            entry = report_by_id.get(character_id)
            if entry is None or not character_pack_complete(entry):
                reasons.append(f"Incomplete character pack for {character_id}")

    scene_report = load_scene_map_report(job)
    if scene_report is None:
        reasons.append("Missing scene_map_report.json")
    else:
        needed_scenes = {shot.scene_id for shot in shots.shots}
        report_by_scene = {entry.scene_id: entry for entry in scene_report.entries}
        for scene_id in sorted(needed_scenes):
            entry = report_by_scene.get(scene_id)
            if entry is None or not scene_pack_complete(entry):
                reasons.append(f"Incomplete scene pack for {scene_id}")

    preview_path = job.storyboard_preview_path
    if not preview_path.is_file():
        reasons.append("Missing storyboard_preview.json")
    else:
        from video_pipeline.schemas import StoryboardPreviewDocument

        preview = StoryboardPreviewDocument.model_validate_json(
            preview_path.read_text(encoding="utf-8")
        )
        preview_by_shot = {item.shot_id: item for item in preview.items}
        for shot in shots.shots:
            item = preview_by_shot.get(shot.shot_id)
            if item is None or item.status != "ok":
                reasons.append(f"Missing storyboard preview for {shot.shot_id}")
                continue
            for rel in (item.start_image_path, item.end_image_path):
                if not (job.root / rel).is_file():
                    reasons.append(f"Missing preview frame {rel} for {shot.shot_id}")

    if require_user_approval:
        try:
            approval = load_approval_document(job)
        except FileNotFoundError:
            approval = None
        if approval is None or approval.status != "approved":
            reasons.append("Storyboard not approved by user")

    return StoryboardGateResult(passed=not reasons, blocking_reasons=reasons)
