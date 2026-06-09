"""Bind character/scene/reference asset packs to each storyboard shot (script scene partition)."""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

from video_pipeline.pipeline.character_assets import load_character_asset_report
from video_pipeline.pipeline.reference_assets import load_reference_asset_report
from video_pipeline.pipeline.resume import load_scene_map_report
from video_pipeline.pipeline.stage_report import StageTimer, write_stage_report
from video_pipeline.schemas import ScriptPlan, Shot, ShotsDocument
from video_pipeline.schemas.asset_binding import (
    CharacterShotBinding,
    ReferenceShotBinding,
    SceneAssetGroup,
    ShotAssetBinding,
    ShotAssetBindingReport,
)
from video_pipeline.schemas.character_asset import CharacterAssetEntry
from video_pipeline.schemas.intake import SceneShotHint
from video_pipeline.schemas.reference_asset import ReferenceAssetEntry
from video_pipeline.storage import JobPaths, write_json

ANGLE_PRIORITY = ("front", "three_quarter", "side")


def shot_asset_binding_report_path(job: JobPaths) -> Path:
    return job.reports_dir / "shot_asset_binding.json"


def character_reference_paths(entry: CharacterAssetEntry) -> list[str]:
    """Ordered refs for a character pack — user upload first, then turnaround angles."""
    paths: list[str] = []
    if entry.user_reference_path:
        paths.append(entry.user_reference_path)
    angle_by_name: dict[str, str] = {}
    for rel in entry.angle_image_paths:
        angle_by_name[Path(rel).stem] = rel
    for angle in ANGLE_PRIORITY:
        rel = angle_by_name.get(angle)
        if rel is not None and rel not in paths:
            paths.append(rel)
    for rel in entry.angle_image_paths:
        if rel not in paths:
            paths.append(rel)
    return paths


def _load_scene_shot_hints(job: JobPaths) -> dict[str, SceneShotHint]:
    path = job.storyboard_dir / "scene_shot_hints.json"
    if not path.is_file():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    hints = [SceneShotHint.model_validate(item) for item in payload]
    return {hint.scene_id: hint for hint in hints}


def references_for_shot(
    shot: Shot,
    reference_entries: list[ReferenceAssetEntry],
    *,
    scene_hint_ref_ids: set[str] | None = None,
) -> list[ReferenceAssetEntry]:
    """Match Reference Agent assets to a shot by scene, character, or Intake hint."""
    matched: list[ReferenceAssetEntry] = []
    seen: set[str] = set()
    for entry in reference_entries:
        if entry.status != "ok" or not entry.asset_path:
            continue
        if entry.ref_id in seen:
            continue
        linked_scene = entry.linked_scene_id == shot.scene_id
        linked_character = (
            entry.linked_character_id is not None
            and entry.linked_character_id in shot.character_ids
        )
        linked_hint = scene_hint_ref_ids is not None and entry.ref_id in scene_hint_ref_ids
        if linked_scene or linked_character or linked_hint:
            matched.append(entry)
            seen.add(entry.ref_id)
    return matched


def build_shot_asset_bindings(
    job: JobPaths,
    shots: ShotsDocument,
) -> ShotAssetBindingReport:
    character_report = load_character_asset_report(job)
    scene_report = load_scene_map_report(job)
    reference_report = load_reference_asset_report(job)
    scene_shot_hints = _load_scene_shot_hints(job)

    characters_by_id = {
        entry.character_id: entry for entry in (character_report.entries if character_report else [])
    }
    reference_entries = reference_report.entries if reference_report else []

    scene_master_by_id: dict[str, str] = {}
    if scene_report is not None:
        for entry in scene_report.entries:
            if entry.status == "ok":
                scene_master_by_id[entry.scene_id] = entry.master_image_path

    entries: list[ShotAssetBinding] = []
    for shot in shots.shots:
        character_bindings: list[CharacterShotBinding] = []
        for character_id in shot.character_ids:
            entry = characters_by_id.get(character_id)
            refs = character_reference_paths(entry) if entry is not None else []
            character_bindings.append(
                CharacterShotBinding(character_id=character_id, reference_image_paths=refs)
            )

        hint = scene_shot_hints.get(shot.scene_id)
        hint_ref_ids = set(hint.linked_reference_ids) if hint else None
        reference_bindings = [
            ReferenceShotBinding(
                ref_id=entry.ref_id,
                kind=entry.kind,
                asset_path=entry.asset_path,  # type: ignore[arg-type]
            )
            for entry in references_for_shot(
                shot,
                reference_entries,
                scene_hint_ref_ids=hint_ref_ids,
            )
        ]

        entries.append(
            ShotAssetBinding(
                shot_id=shot.shot_id,
                scene_id=shot.scene_id,
                character_ids=list(shot.character_ids),
                scene_master_path=scene_master_by_id.get(shot.scene_id),
                character_bindings=character_bindings,
                reference_bindings=reference_bindings,
            )
        )

    by_scene_map: dict[str, list[str]] = defaultdict(list)
    scene_characters: dict[str, set[str]] = defaultdict(set)
    scene_references: dict[str, set[str]] = defaultdict(set)
    for binding in entries:
        by_scene_map[binding.scene_id].append(binding.shot_id)
        scene_characters[binding.scene_id].update(binding.character_ids)
        for ref in binding.reference_bindings:
            scene_references[binding.scene_id].add(ref.ref_id)

    by_scene = [
        SceneAssetGroup(
            scene_id=scene_id,
            shot_ids=shot_ids,
            scene_master_path=scene_master_by_id.get(scene_id),
            character_ids=sorted(scene_characters[scene_id]),
            reference_ids=sorted(scene_references[scene_id]),
        )
        for scene_id, shot_ids in sorted(by_scene_map.items())
    ]
    return ShotAssetBindingReport(job_id=job.job_id, entries=entries, by_scene=by_scene)


def load_shot_asset_binding_report(job: JobPaths) -> ShotAssetBindingReport | None:
    path = shot_asset_binding_report_path(job)
    if not path.is_file():
        return None
    return ShotAssetBindingReport.model_validate_json(path.read_text(encoding="utf-8"))


def load_shot_asset_binding_map(job: JobPaths) -> dict[str, ShotAssetBinding]:
    report = load_shot_asset_binding_report(job)
    if report is None:
        return {}
    return {entry.shot_id: entry for entry in report.entries}


def apply_bindings_to_shots(job: JobPaths, shots: ShotsDocument, report: ShotAssetBindingReport) -> ShotsDocument:
    binding_by_shot = {entry.shot_id: entry for entry in report.entries}
    updated_shots = []
    for shot in shots.shots:
        binding = binding_by_shot.get(shot.shot_id)
        if binding is None:
            updated_shots.append(shot)
            continue
        char_paths = [
            rel
            for cb in binding.character_bindings
            for rel in cb.reference_image_paths
        ]
        ref_paths = [ref.asset_path for ref in binding.reference_bindings]
        updated_shots.append(
            shot.model_copy(
                update={
                    "scene_reference_id": binding.scene_id,
                    "scene_reference_image_path": binding.scene_master_path,
                    "character_reference_ids": list(binding.character_ids),
                    "character_reference_image_paths": char_paths,
                    "other_reference_ids": [ref.ref_id for ref in binding.reference_bindings],
                    "other_reference_image_paths": ref_paths,
                }
            )
        )
    document = ShotsDocument(shots=updated_shots)
    write_json(job.shots_path, document)
    return document


def _append_path(paths: list[Path], candidate: Path) -> None:
    if candidate.is_file() and candidate not in paths:
        paths.append(candidate)


def conditioning_paths(
    job: JobPaths,
    shot: Shot,
    binding: ShotAssetBinding,
) -> list[Path]:
    paths: list[Path] = []
    for cb in binding.character_bindings:
        for rel in cb.reference_image_paths:
            _append_path(paths, job.root / rel)
    for ref in binding.reference_bindings:
        _append_path(paths, job.root / ref.asset_path)
    if shot.needs_scene_master and binding.scene_master_path:
        _append_path(paths, job.root / binding.scene_master_path)
    return paths


def primary_conditioning_path(job: JobPaths, shot: Shot, binding: ShotAssetBinding) -> Path | None:
    """Pick one image for img2img — character, then prop/style ref, then scene master."""
    if shot.has_characters:
        for cb in binding.character_bindings:
            for rel in cb.reference_image_paths:
                candidate = job.root / rel
                if candidate.is_file():
                    return candidate
    for ref in binding.reference_bindings:
        candidate = job.root / ref.asset_path
        if candidate.is_file():
            return candidate
    if shot.needs_scene_master and binding.scene_master_path:
        master = job.root / binding.scene_master_path
        if master.is_file():
            return master
    return None


def video_reference_paths(job: JobPaths, binding: ShotAssetBinding) -> list[Path]:
    """Character + reference assets to pass alongside Kling start/end frames."""
    paths: list[Path] = []
    for cb in binding.character_bindings:
        for rel in cb.reference_image_paths:
            _append_path(paths, job.root / rel)
    for ref in binding.reference_bindings:
        _append_path(paths, job.root / ref.asset_path)
    return paths


def run_asset_binding(
    job: JobPaths,
    script: ScriptPlan,
    shots: ShotsDocument,
) -> tuple[ShotAssetBindingReport, ShotsDocument]:
    timer = StageTimer(
        job_id=job.job_id,
        stage="asset_binding",
        input_artifacts=[
            str(job.shots_path.relative_to(job.root)),
            str(job.reports_dir / "character_asset_report.json"),
            str(job.reports_dir / "scene_map_report.json"),
            str(job.reports_dir / "reference_asset_report.json"),
            str(job.script_path.relative_to(job.root)),
        ],
    )
    report = build_shot_asset_bindings(job, shots)
    bound_shots = apply_bindings_to_shots(job, shots, report)
    write_json(shot_asset_binding_report_path(job), report)
    envelope = timer.envelope(
        status="ok",
        output_artifacts=[str(shot_asset_binding_report_path(job).relative_to(job.root))],
        errors=[],
    )
    write_stage_report(
        job,
        job.reports_dir / "asset_binding_report.json",
        envelope,
        {
            "shot_count": len(report.entries),
            "scene_count": len(report.by_scene),
            "script_scene_ids": script.scene_ids,
        },
    )
    return report, bound_shots
