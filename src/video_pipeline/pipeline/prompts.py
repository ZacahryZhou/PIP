"""Build provider prompts from structured shot + script fields."""

from __future__ import annotations

from video_pipeline.schemas import ScriptPlan, Shot


def build_keyframe_prompt(shot: Shot, script: ScriptPlan) -> str:
    parts = [
        shot.subject,
        shot.action,
        f"{shot.shot_size} {shot.camera_angle}",
        f"expression: {shot.facial_expression}",
        f"gaze: {shot.character_gaze}",
        f"blocking: {shot.blocking}",
        script.color_tone,
        script.visual_style,
    ]
    if shot.character_prompts:
        parts.extend(shot.character_prompts)
    if shot.style_tags:
        parts.append(", ".join(shot.style_tags))
    return ". ".join(part.strip() for part in parts if part.strip())


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
