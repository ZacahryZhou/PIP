"""Collect dialogue lines with global timestamps for VO and subtitles."""

from __future__ import annotations

from dataclasses import dataclass

from video_pipeline.pipeline.timeline import TimelineDocument
from video_pipeline.schemas import DialogueLine, ScriptPlan, ShotsDocument

MIN_SUBTITLE_DURATION_SEC = 0.8


@dataclass(frozen=True)
class TimedDialogueLine:
    speaker: str
    text: str
    start_sec: float
    end_sec: float
    source: str
    line_id: str


def _scene_starts(shots: ShotsDocument, timeline: TimelineDocument) -> dict[str, float]:
    shot_starts = {entry.shot_id: entry.start_sec for entry in timeline.shots}
    starts: dict[str, float] = {}
    for shot in sorted(shots.shots, key=lambda item: item.shot_id):
        if shot.scene_id not in starts:
            starts[shot.scene_id] = shot_starts[shot.shot_id]
    return starts


def _clamp_to_shot(
    start_sec: float,
    end_sec: float,
    *,
    shot_start: float,
    shot_end: float,
) -> tuple[float, float] | None:
    global_start = shot_start + start_sec
    global_end = shot_start + end_sec
    global_start = max(global_start, shot_start)
    global_end = min(global_end, shot_end)
    if global_end - global_start < MIN_SUBTITLE_DURATION_SEC:
        global_end = min(shot_end, global_start + MIN_SUBTITLE_DURATION_SEC)
    if global_end <= global_start:
        return None
    return global_start, global_end


def _from_shot_dialogue(
    shots: ShotsDocument,
    timeline: TimelineDocument,
) -> list[TimedDialogueLine]:
    shot_bounds = {entry.shot_id: (entry.start_sec, entry.end_sec) for entry in timeline.shots}
    lines: list[TimedDialogueLine] = []

    for shot in sorted(shots.shots, key=lambda item: item.shot_id):
        if not shot.dialogue:
            continue
        shot_start, shot_end = shot_bounds[shot.shot_id]
        for index, line in enumerate(shot.dialogue):
            clamped = _clamp_to_shot(
                line.start_sec,
                line.end_sec,
                shot_start=shot_start,
                shot_end=shot_end,
            )
            if clamped is None:
                continue
            global_start, global_end = clamped
            lines.append(
                TimedDialogueLine(
                    speaker=line.speaker,
                    text=line.text,
                    start_sec=global_start,
                    end_sec=global_end,
                    source=f"shot:{shot.shot_id}",
                    line_id=f"{shot.shot_id}_{index:02d}",
                )
            )
    return lines


def _from_scene_dialogue(
    script: ScriptPlan,
    shots: ShotsDocument,
    timeline: TimelineDocument,
) -> list[TimedDialogueLine]:
    scene_starts = _scene_starts(shots, timeline)
    lines: list[TimedDialogueLine] = []

    for scene in script.scene_list:
        if not scene.dialogue:
            continue
        scene_start = scene_starts.get(scene.scene_id, 0.0)
        for index, line in enumerate(scene.dialogue):
            global_start = scene_start + line.start_sec
            global_end = scene_start + line.end_sec
            if global_end - global_start < MIN_SUBTITLE_DURATION_SEC:
                global_end = global_start + MIN_SUBTITLE_DURATION_SEC
            lines.append(
                TimedDialogueLine(
                    speaker=line.speaker,
                    text=line.text,
                    start_sec=global_start,
                    end_sec=global_end,
                    source=f"scene:{scene.scene_id}",
                    line_id=f"{scene.scene_id}_{index:02d}",
                )
            )
    return lines


def collect_dialogue_lines(
    script: ScriptPlan,
    shots: ShotsDocument,
    timeline: TimelineDocument,
) -> list[TimedDialogueLine]:
    shot_lines = _from_shot_dialogue(shots, timeline)
    if shot_lines:
        return sorted(shot_lines, key=lambda line: (line.start_sec, line.line_id))

    scene_lines = _from_scene_dialogue(script, shots, timeline)
    return sorted(scene_lines, key=lambda line: (line.start_sec, line.line_id))


def dialogue_lines_from_script_only(script: ScriptPlan) -> list[DialogueLine]:
    lines: list[DialogueLine] = []
    for scene in script.scene_list:
        lines.extend(scene.dialogue)
    return lines
