"""Storyboard logic validation against script scenes."""

from __future__ import annotations

from collections import defaultdict

from video_pipeline.schemas import ScriptPlan, ShotsDocument


def validate_storyboard_logic(
    script: ScriptPlan,
    shots: ShotsDocument,
    *,
    strict: bool = True,
) -> list[str]:
    """Return human-readable validation errors. Empty list means pass."""
    errors: list[str] = []
    script_scene_ids = set(script.scene_ids)
    grouped: dict[str, list] = defaultdict(list)
    for shot in shots.shots:
        grouped[shot.scene_id].append(shot)

    for scene_id, scene_shots in grouped.items():
        if scene_id not in script_scene_ids:
            errors.append(f"shot references unknown scene_id {scene_id}")
            continue

        orders = [shot.shot_order_in_scene for shot in scene_shots if shot.shot_order_in_scene]
        expected = list(range(1, len(scene_shots) + 1))
        if sorted(orders) != expected:
            errors.append(
                f"{scene_id} has invalid shot_order_in_scene sequence: {sorted(orders)}"
            )

        scene = next(item for item in script.scene_list if item.scene_id == scene_id)
        scene_total = sum(shot.duration_sec for shot in scene_shots)
        if abs(scene_total - scene.duration_sec) > 0.5:
            errors.append(
                f"{scene_id} shot durations sum to {scene_total}, "
                f"but script scene duration is {scene.duration_sec}"
            )

        styles = {shot.visual_style for shot in scene_shots if shot.visual_style}
        if len(styles) > 1:
            errors.append(f"{scene_id} has inconsistent visual_style across shots")

        for index, shot in enumerate(scene_shots):
            if index == 0:
                continue
            if strict and not (shot.shot_continuity_from_previous or "").strip():
                errors.append(
                    f"{shot.shot_id} missing shot_continuity_from_previous inside {scene_id}"
                )

        if strict and len(scene_shots) > 1:
            sizes = [shot.shot_size for shot in scene_shots]
            if len(set(sizes)) < 2 and scene.duration_sec > 5:
                errors.append(
                    f"{scene_id} should use at least two shot_size values for a scene longer than 5s"
                )

    if abs(shots.total_duration_sec - script.total_duration_sec) > 1.0:
        errors.append(
            f"total shot duration {shots.total_duration_sec} "
            f"does not match script total {script.total_duration_sec}"
        )

    return errors
