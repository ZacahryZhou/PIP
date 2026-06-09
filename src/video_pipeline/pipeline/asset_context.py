"""Resolve Intake-routed asset targets and style hints for parallel asset agents."""

from __future__ import annotations

from video_pipeline.schemas import GatewayPayload, Scene, ScriptPlan, ShotsDocument
from video_pipeline.schemas.intake import IntakePlan, SceneIntakeJob
from video_pipeline.schemas.plot import PlotPlan


def resolve_character_ids(
    payload: GatewayPayload,
    intake_plan: IntakePlan,
    script: ScriptPlan | None = None,
    shots: ShotsDocument | None = None,
) -> list[str]:
    ids: set[str] = set(payload.character_ids)
    ids.update(intake_plan.characters_for_script)
    ids.update(job.character_id for job in intake_plan.character_jobs)
    if script is not None:
        ids.update(script.characters_in_use)
    if shots is not None:
        for shot in shots.shots:
            if shot.has_characters:
                ids.update(shot.character_ids)
    return sorted(ids)


def visual_style_bundle(
    *,
    intake_plan: IntakePlan,
    plot_plan: PlotPlan | None = None,
    script: ScriptPlan | None = None,
) -> tuple[str, str]:
    if script is not None:
        return script.visual_style, script.color_tone
    visual = (plot_plan.visual_style_hint if plot_plan else None) or "cinematic photoreal"
    color = (plot_plan.scene_style_hint if plot_plan else None) or intake_plan.script_brief[:120]
    return visual, color


def resolve_scenes_for_maps(
    intake_plan: IntakePlan,
    plot_plan: PlotPlan | None,
    script: ScriptPlan | None,
) -> list[Scene]:
    if script is not None and script.scene_list:
        return sorted(
            script.scene_list,
            key=lambda scene: scene.scene_order or int(scene.scene_id.split("_")[1]),
        )

    outline_by_id = {
        outline.scene_id: outline for outline in (plot_plan.scene_outlines if plot_plan else [])
    }
    scene_jobs: list[SceneIntakeJob] = list(intake_plan.scene_jobs)
    if not scene_jobs and intake_plan.scene_shot_hints:
        scene_jobs = [
            SceneIntakeJob(scene_id=hint.scene_id) for hint in intake_plan.scene_shot_hints
        ]

    scenes: list[Scene] = []
    for index, scene_job in enumerate(scene_jobs, start=1):
        outline = outline_by_id.get(scene_job.scene_id)
        scenes.append(
            Scene(
                scene_id=scene_job.scene_id,
                scene_order=index,
                duration_sec=5.0,
                location=outline.location if outline else scene_job.scene_id.replace("_", " "),
                time_of_day=outline.time_of_day if outline else "night",
                characters=outline.characters if outline else intake_plan.characters_for_script,
                action_summary=(
                    outline.story_text[:240]
                    if outline
                    else f"Scene {scene_job.scene_id} from intake routing"
                ),
                mood="normal",
                emotional_beat=outline.emotional_beat if outline else "development",
                camera_notes=outline.camera_progression if outline else "establishing wide",
                director_notes="Routed from Intake scene job",
                visual_style=outline.visual_style_hint if outline else None,
                color_palette=outline.scene_style_hint if outline else None,
                camera_intent=outline.camera_progression if outline else None,
            )
        )
    return scenes
