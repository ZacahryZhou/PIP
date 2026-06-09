"""Intake Agent — classify gateway input and wire cross-linked asset jobs."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from video_pipeline.schemas import GatewayPayload, OtherReferenceImage
from video_pipeline.schemas.intake import (
    AssetLink,
    CharacterIntakeJob,
    IntakeGap,
    IntakePlan,
    PlotRoute,
    ReferenceIntakeJob,
    SceneIntakeJob,
    SceneShotHint,
)
from video_pipeline.storage import JobPaths


@dataclass(frozen=True)
class IntakeAnalysis:
    plan: IntakePlan
    gaps: tuple[IntakeGap, ...]
    payload: GatewayPayload


def _resolve_reference_path(job: JobPaths, rel_path: str) -> str | None:
    candidate = job.root / rel_path
    return rel_path if candidate.is_file() else None


def _build_script_brief(payload: GatewayPayload) -> str:
    parts: list[str] = []
    if payload.has_script and payload.user_script_text:
        parts.append(f"User script:\n{payload.user_script_text.strip()}")
    elif payload.raw_prompt.strip():
        parts.append(f"User request:\n{payload.raw_prompt.strip()}")
    if payload.style_preset:
        parts.append(f"Style preset: {payload.style_preset}")
    if payload.style_notes:
        parts.append(f"Style notes: {payload.style_notes}")
    if payload.target_duration_sec:
        parts.append(f"Target duration: {payload.target_duration_sec}s")
    parts.append(f"Language: {payload.language}")
    parts.append(f"Channel: {payload.channel}")
    return "\n\n".join(parts)


def _resolve_plot_route(payload: GatewayPayload) -> PlotRoute:
    if payload.has_script and (payload.user_script_text or "").strip():
        return "review_plot"
    if (payload.user_script_text or "").strip():
        return "review_plot"
    return "generate_plot"


def _classify_reference_jobs(
    job: JobPaths,
    payload: GatewayPayload,
) -> list[ReferenceIntakeJob]:
    jobs: list[ReferenceIntakeJob] = []
    for ref in payload.other_reference_images:
        path = _resolve_reference_path(job, ref.path)
        jobs.append(
            ReferenceIntakeJob(
                ref_id=ref.ref_id,
                kind=ref.kind_hint or "other",
                reference_path=path,
                linked_scene_id=ref.linked_scene_id,
                linked_character_id=ref.linked_character_id,
            )
        )
    return jobs


def _build_scene_shot_hints(
    scene_jobs: list[SceneIntakeJob],
    character_jobs: list[CharacterIntakeJob],
    reference_jobs: list[ReferenceIntakeJob],
) -> list[SceneShotHint]:
    hints: list[SceneShotHint] = []
    for scene in scene_jobs:
        linked_refs = [
            ref.ref_id
            for ref in reference_jobs
            if ref.linked_scene_id == scene.scene_id
        ]
        hints.append(
            SceneShotHint(
                scene_id=scene.scene_id,
                expected_shots=2,
                camera_progression="establishing wide → medium action → emotional close",
                linked_character_ids=scene.linked_character_ids,
                linked_reference_ids=linked_refs,
                needs_generated_scene_image=scene.reference_path is None,
                needs_generated_character_refs=[
                    char.character_id
                    for char in character_jobs
                    if char.reference_path is None
                    and char.character_id in scene.linked_character_ids
                ],
            )
        )
    if not hints and character_jobs:
        hints.append(
            SceneShotHint(
                scene_id="scene_001",
                expected_shots=2,
                camera_progression="establishing wide → medium action → emotional close",
                linked_character_ids=[c.character_id for c in character_jobs],
                needs_generated_scene_image=True,
                needs_generated_character_refs=[
                    c.character_id for c in character_jobs if c.reference_path is None
                ],
            )
        )
    return hints


def _build_asset_links(
    scene_jobs: list[SceneIntakeJob],
    character_jobs: list[CharacterIntakeJob],
    reference_jobs: list[ReferenceIntakeJob],
) -> list[AssetLink]:
    links: list[AssetLink] = []
    link_index = 1
    for order, scene in enumerate(scene_jobs, start=1):
        links.append(
            AssetLink(
                link_id=f"link_{link_index}",
                scene_id=scene.scene_id,
                scene_order=order,
            )
        )
        link_index += 1
        for character in character_jobs:
            if character.character_id in scene.linked_character_ids:
                links.append(
                    AssetLink(
                        link_id=f"link_{link_index}",
                        scene_id=scene.scene_id,
                        character_id=character.character_id,
                        scene_order=order,
                    )
                )
                link_index += 1
    for ref in reference_jobs:
        links.append(
            AssetLink(
                link_id=f"link_{link_index}",
                scene_id=ref.linked_scene_id,
                character_id=ref.linked_character_id,
                ref_id=ref.ref_id,
            )
        )
        link_index += 1
    return links


def detect_intake_gaps(job: JobPaths, payload: GatewayPayload) -> list[IntakeGap]:
    gaps: list[IntakeGap] = []
    gap_index = 1

    if payload.has_script and not (payload.user_script_text or "").strip():
        gaps.append(
            IntakeGap(
                gap_id=f"gap_{gap_index}",
                kind="script",
                label="缺少剧本正文",
                detail="has_script 为 true，但 user_script_text 为空。",
                required=True,
            )
        )
        gap_index += 1

    if not payload.has_script and not payload.raw_prompt.strip():
        gaps.append(
            IntakeGap(
                gap_id=f"gap_{gap_index}",
                kind="plot",
                label="缺少剧情描述",
                detail="没有 raw_prompt，将由剧情 Agent 生成；请确认是否让系统生成。",
                required=False,
            )
        )
        gap_index += 1

    refs_by_character = {
        ref.character_id: ref for ref in payload.character_reference_images
    }
    if payload.character_ids:
        for character_id in payload.character_ids:
            ref = refs_by_character.get(character_id)
            path_ok = ref is not None and _resolve_reference_path(job, ref.path) is not None
            if not path_ok:
                also_on_disk = any(
                    job.character_refs_dir.glob(f"{character_id}_ref.*")
                )
                if not also_on_disk:
                    gaps.append(
                        IntakeGap(
                            gap_id=f"gap_{gap_index}",
                            kind="character_reference",
                            label=f"角色 {character_id} 缺少参考图",
                            detail=(
                                f"已声明 character_id={character_id!r}，"
                                "未找到人物参考图；可选系统生成或补发图片。"
                            ),
                            character_id=character_id,
                            required=False,
                        )
                    )
                    gap_index += 1
    elif not payload.character_reference_images:
        gaps.append(
            IntakeGap(
                gap_id=f"gap_{gap_index}",
                kind="character_ids",
                label="未指定角色",
                detail="未提供 character_ids，也没有角色参考图。",
                required=False,
            )
        )
        gap_index += 1

    for ref in payload.scene_reference_images:
        if _resolve_reference_path(job, ref.path) is None:
            gaps.append(
                IntakeGap(
                    gap_id=f"gap_{gap_index}",
                    kind="scene_reference",
                    label=f"场景 {ref.scene_id} 参考图缺失",
                    detail=f"声明了 scene_id={ref.scene_id!r}，但文件不存在；可系统生成。",
                    scene_id=ref.scene_id,
                    required=False,
                )
            )
            gap_index += 1

    if not payload.style_preset and not (payload.style_notes or "").strip():
        gaps.append(
            IntakeGap(
                gap_id=f"gap_{gap_index}",
                kind="style",
                label="未指定视觉风格",
                detail="style_preset 与 style_notes 均为空。",
                required=False,
            )
        )
        gap_index += 1

    if payload.target_duration_sec is None:
        gaps.append(
            IntakeGap(
                gap_id=f"gap_{gap_index}",
                kind="duration",
                label="未指定目标时长",
                detail="target_duration_sec 未设置。",
                required=False,
            )
        )

    return gaps


def build_intake_plan(job: JobPaths, payload: GatewayPayload) -> IntakePlan:
    characters_for_script = list(dict.fromkeys(payload.character_ids))
    character_jobs: list[CharacterIntakeJob] = []
    refs_by_character = {
        ref.character_id: ref for ref in payload.character_reference_images
    }

    for character_id in characters_for_script:
        ref = refs_by_character.get(character_id)
        ref_path = None
        source: Literal["user_upload", "system_generate", "catalog"] = "catalog"
        if ref is not None:
            ref_path = _resolve_reference_path(job, ref.path)
            if ref_path:
                source = "user_upload"
        if ref_path is None:
            for candidate in sorted(job.character_refs_dir.glob(f"{character_id}_ref.*")):
                if candidate.is_file():
                    ref_path = str(candidate.relative_to(job.root))
                    source = "user_upload"
                    break
        character_jobs.append(
            CharacterIntakeJob(
                character_id=character_id,
                reference_path=ref_path,
                source=source,
                linked_scene_ids=[f"scene_{index:03d}" for index in range(1, 4)],
            )
        )

    for ref in payload.character_reference_images:
        if ref.character_id in characters_for_script:
            continue
        ref_path = _resolve_reference_path(job, ref.path)
        character_jobs.append(
            CharacterIntakeJob(
                character_id=ref.character_id,
                reference_path=ref_path,
                source="user_upload" if ref_path else "catalog",
            )
        )
        if ref.character_id not in characters_for_script:
            characters_for_script.append(ref.character_id)

    scene_jobs: list[SceneIntakeJob] = []
    for index, ref in enumerate(payload.scene_reference_images, start=1):
        ref_path = _resolve_reference_path(job, ref.path)
        scene_jobs.append(
            SceneIntakeJob(
                scene_id=ref.scene_id,
                reference_path=ref_path,
                source="user_upload" if ref_path else "system_generate",
                linked_character_ids=characters_for_script,
            )
        )

    if not scene_jobs and characters_for_script:
        scene_jobs.append(
            SceneIntakeJob(
                scene_id="scene_001",
                reference_path=None,
                source="system_generate",
                linked_character_ids=characters_for_script,
            )
        )

    reference_jobs = _classify_reference_jobs(job, payload)
    scene_shot_hints = _build_scene_shot_hints(scene_jobs, character_jobs, reference_jobs)
    asset_links = _build_asset_links(scene_jobs, character_jobs, reference_jobs)

    notes: list[str] = []
    if characters_for_script:
        notes.append(
            "Script Agent must only use characters: " + ", ".join(characters_for_script)
        )
    notes.append(
        "Asset graph: scene_jobs ↔ character_jobs ↔ reference_jobs linked via asset_links "
        "and scene_shot_hints for storyboard generation."
    )

    return IntakePlan(
        job_id=job.job_id,
        script_brief=_build_script_brief(payload),
        plot_route=_resolve_plot_route(payload),
        characters_for_script=characters_for_script,
        character_jobs=character_jobs,
        scene_jobs=scene_jobs,
        reference_jobs=reference_jobs,
        scene_shot_hints=scene_shot_hints,
        asset_links=asset_links,
        notes=notes,
    )


def run_intake_agent(job: JobPaths, payload: GatewayPayload) -> IntakeAnalysis:
    gaps = detect_intake_gaps(job, payload)
    plan = build_intake_plan(job, payload)
    return IntakeAnalysis(plan=plan, gaps=tuple(gaps), payload=payload)
