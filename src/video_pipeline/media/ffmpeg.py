"""Video probe and concat — prefers FFmpeg, falls back to OpenCV."""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path


def parse_resolution(resolution: str) -> tuple[int, int]:
    if "x" not in resolution.lower():
        raise ValueError(f"Invalid resolution: {resolution}")
    width_str, height_str = resolution.lower().split("x", 1)
    return int(width_str), int(height_str)


def _ffmpeg_path() -> str | None:
    return shutil.which("ffmpeg")


def probe_video(path: Path) -> dict[str, float | int]:
    import cv2

    capture = cv2.VideoCapture(str(path))
    if not capture.isOpened():
        raise ValueError(f"Cannot open video: {path}")

    width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = float(capture.get(cv2.CAP_PROP_FPS))
    frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
    capture.release()

    duration_sec = frame_count / fps if fps > 0 else 0.0
    return {
        "width": width,
        "height": height,
        "fps": fps,
        "duration_sec": duration_sec,
    }


def concat_videos(inputs: list[Path], output: Path) -> Path:
    if not inputs:
        raise ValueError("concat_videos requires at least one input")

    output.parent.mkdir(parents=True, exist_ok=True)
    ffmpeg = _ffmpeg_path()
    if ffmpeg:
        return _concat_with_ffmpeg(ffmpeg, inputs, output)
    return _concat_with_opencv(inputs, output)


def _concat_with_ffmpeg(ffmpeg: str, inputs: list[Path], output: Path) -> Path:
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as handle:
        list_path = Path(handle.name)
        for clip in inputs:
            escaped = str(clip.resolve()).replace("'", "'\\''")
            handle.write(f"file '{escaped}'\n")

    try:
        subprocess.run(
            [
                ffmpeg,
                "-y",
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                str(list_path),
                "-c",
                "copy",
                str(output),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as exc:
        stderr = exc.stderr or ""
        raise RuntimeError(f"FFmpeg concat failed: {stderr}") from exc
    finally:
        list_path.unlink(missing_ok=True)

    return output


def _concat_with_opencv(inputs: list[Path], output: Path) -> Path:
    import cv2

    writer: cv2.VideoWriter | None = None
    fps = 24.0
    size: tuple[int, int] | None = None

    for clip_path in inputs:
        capture = cv2.VideoCapture(str(clip_path))
        if not capture.isOpened():
            raise ValueError(f"Cannot open video: {clip_path}")

        clip_fps = float(capture.get(cv2.CAP_PROP_FPS)) or fps
        width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))

        if writer is None:
            fps = clip_fps
            size = (width, height)
            fourcc = cv2.VideoWriter_fourcc(*"mp4v")
            writer = cv2.VideoWriter(str(output), fourcc, fps, size)

        while True:
            ok, frame = capture.read()
            if not ok:
                break
            if frame.shape[1] != size[0] or frame.shape[0] != size[1]:
                frame = cv2.resize(frame, size)
            writer.write(frame)
        capture.release()

    if writer is not None:
        writer.release()
    return output
