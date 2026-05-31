"""Unit tests for dialogue global timing."""

from video_pipeline.pipeline.dialogue import collect_dialogue_lines
from video_pipeline.pipeline.timeline import TimelineDocument, TimelineShot
from video_pipeline.schemas import ScriptPlan, ShotsDocument


def test_collect_dialogue_prefers_shot_level_timing() -> None:
    fixtures = __import__("pathlib").Path(__file__).parent / "fixtures"
    script = ScriptPlan.model_validate_json(fixtures.joinpath("script.json").read_text())
    shots = ShotsDocument.model_validate_json(fixtures.joinpath("shots.json").read_text())

    timeline = TimelineDocument(
        shots=[
            TimelineShot("shot_001", "clips/validated/shot_001.mp4", 0.0, 5.0),
            TimelineShot("shot_002", "clips/validated/shot_002.mp4", 5.0, 10.0),
            TimelineShot("shot_006", "clips/validated/shot_006.mp4", 25.0, 30.0),
        ],
        final_duration_sec=30.0,
    )

    lines = collect_dialogue_lines(script, shots, timeline)
    assert len(lines) == 2
    assert lines[0].text == "Keep moving."
    assert lines[0].start_sec == 7.0
    assert lines[0].end_sec == 8.5
    assert lines[1].text == "Now or never."
    assert lines[1].start_sec == 26.0
    assert lines[1].end_sec == 27.5
