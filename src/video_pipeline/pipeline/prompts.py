"""Build provider prompts from structured shot + script fields."""

from __future__ import annotations

from pathlib import Path

from video_pipeline.schemas import Scene, ScriptPlan, Shot


def build_preview_prompt(shot: Shot, script: ScriptPlan) -> str:
    base = shot.preview_desc or f"{shot.subject}. {shot.action}"
    parts = [
        base,
        f"{shot.shot_size} {shot.camera_angle}",
        f"mood {shot.mood}",
        script.visual_style,
        script.color_tone,
    ]
    if shot.visual_style:
        parts.append(shot.visual_style)
    if shot.character_prompts:
        parts.extend(shot.character_prompts)
    if shot.style_tags:
        parts.append(", ".join(shot.style_tags))
    return ". ".join(part.strip() for part in parts if part.strip())


def _keyframe_common_parts(
    shot: Shot,
    script: ScriptPlan,
    *,
    scene: Scene | None,
    scene_master_path: Path | None,
) -> list[str]:
    parts: list[str] = []
    if scene is not None:
        parts.append(f"location: {scene.location}, {scene.time_of_day}")
        if scene.visual_style:
            parts.append(scene.visual_style)
        if scene.color_palette:
            parts.append(scene.color_palette)
        if scene.camera_intent:
            parts.append(f"scene camera intent: {scene.camera_intent}")
    else:
        parts.extend([script.color_tone, script.visual_style])
    if scene_master_path is not None:
        parts.append(
            f"match environment and lighting from scene master reference ({scene_master_path.name})"
        )
    if shot.character_prompts:
        parts.extend(shot.character_prompts)
    if shot.style_tags:
        parts.append(", ".join(shot.style_tags))
    return parts


def build_keyframe_start_prompt(
    shot: Shot,
    script: ScriptPlan,
    *,
    scene: Scene | None = None,
    scene_master_path: Path | None = None,
) -> str:
    parts: list[str] = []
    if shot.keyframe_start_desc:
        parts.append(shot.keyframe_start_desc)
    parts.extend(
        [
            shot.subject,
            shot.action,
            f"{shot.shot_size} {shot.camera_angle}",
            f"expression: {shot.facial_expression}",
            f"gaze: {shot.character_gaze}",
            f"blocking: {shot.blocking}",
            "first frame of shot",
        ]
    )
    parts.extend(_keyframe_common_parts(shot, script, scene=scene, scene_master_path=scene_master_path))
    return ". ".join(part.strip() for part in parts if part.strip())


def build_keyframe_end_prompt(
    shot: Shot,
    script: ScriptPlan,
    *,
    scene: Scene | None = None,
    scene_master_path: Path | None = None,
) -> str:
    parts: list[str] = []
    if shot.keyframe_end_desc:
        parts.append(shot.keyframe_end_desc)
    parts.extend(
        [
            shot.subject,
            shot.action,
            f"{shot.shot_size} {shot.camera_angle}",
            f"camera move: {shot.camera_move}",
            "last frame of shot",
        ]
    )
    parts.extend(_keyframe_common_parts(shot, script, scene=scene, scene_master_path=scene_master_path))
    return ". ".join(part.strip() for part in parts if part.strip())


def build_keyframe_prompt(
    shot: Shot,
    script: ScriptPlan,
    *,
    scene: Scene | None = None,
    scene_master_path: Path | None = None,
) -> str:
    return build_keyframe_start_prompt(
        shot,
        script,
        scene=scene,
        scene_master_path=scene_master_path,
    )


def build_video_prompt(shot: Shot, script: ScriptPlan) -> str:
    parts = [
        shot.subject,
        shot.action,
        shot.camera_move,
        f"mood {shot.mood}",
        script.color_tone,
    ]
    if shot.character_prompts:
        parts.extend(shot.character_prompts)
    return ". ".join(part.strip() for part in parts if part.strip())
