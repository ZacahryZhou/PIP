"""SRT generation and subtitle burn-in."""

from __future__ import annotations

import logging
import shutil
from pathlib import Path

from video_pipeline.media.ffmpeg import burn_subtitles
from video_pipeline.pipeline.dialogue import TimedDialogueLine

logger = logging.getLogger(__name__)


def _format_timestamp(seconds: float) -> str:
    total_ms = max(0, int(round(seconds * 1000)))
    hours, remainder = divmod(total_ms, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    secs, millis = divmod(remainder, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def _wrap_text(text: str, *, max_chars: int) -> str:
    words = text.split()
    if not words:
        return text

    lines: list[str] = []
    current = words[0]
    for word in words[1:]:
        candidate = f"{current} {word}"
        if len(candidate) <= max_chars:
            current = candidate
        else:
            lines.append(current)
            current = word
            if len(lines) >= 2:
                break
    lines.append(current)
    return "\n".join(lines[:2])


def write_srt(path: Path, lines: list[TimedDialogueLine], *, language: str = "en") -> Path:
    max_chars = 18 if language.lower().startswith("zh") else 42
    blocks: list[str] = []

    for index, line in enumerate(lines, start=1):
        text = _wrap_text(line.text.strip(), max_chars=max_chars)
        blocks.append(
            "\n".join(
                [
                    str(index),
                    f"{_format_timestamp(line.start_sec)} --> {_format_timestamp(line.end_sec)}",
                    text,
                ]
            )
        )

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n\n".join(blocks) + ("\n" if blocks else ""), encoding="utf-8")
    return path


def burn_subtitles_into_video(
    video_path: Path,
    srt_path: Path,
    output_path: Path,
    *,
    language: str = "en",
) -> Path:
    font_name = "PingFang SC" if language.lower().startswith("zh") else "Arial"
    try:
        return burn_subtitles(
            video_path,
            srt_path,
            output_path,
            font_name=font_name,
        )
    except RuntimeError as exc:
        message = str(exc)
        if "libass" in message or "subtitles filter" in message:
            logger.warning(
                "Skipping subtitle burn-in (%s). SRT saved at %s",
                message,
                srt_path,
            )
            output_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(video_path, output_path)
            return output_path
        raise
