"""Unit tests for SRT generation."""

from pathlib import Path

from video_pipeline.pipeline.dialogue import TimedDialogueLine
from video_pipeline.pipeline.subtitles import write_srt


def test_write_srt_formats_blocks(tmp_path: Path) -> None:
    srt_path = tmp_path / "final.srt"
    lines = [
        TimedDialogueLine(
            speaker="hero",
            text="Keep moving.",
            start_sec=7.0,
            end_sec=8.5,
            source="shot:shot_002",
            line_id="shot_002_00",
        )
    ]
    write_srt(srt_path, lines, language="en")

    content = srt_path.read_text(encoding="utf-8")
    assert "1\n" in content
    assert "00:00:07,000 --> 00:00:08,500" in content
    assert "Keep moving." in content
