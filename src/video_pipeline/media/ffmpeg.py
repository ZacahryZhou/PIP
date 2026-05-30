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


def normalize_clip(
    input_path: Path,
    output_path: Path,
    *,
    width: int,
    height: int,
    fps: int,
    duration_sec: float,
) -> Path:
    """Scale, pad, retime, and mute a provider clip to pipeline target specs."""
    ffmpeg = _ffmpeg_path()
    if ffmpeg:
        return _normalize_with_ffmpeg(
            ffmpeg,
            input_path,
            output_path,
            width=width,
            height=height,
            fps=fps,
            duration_sec=duration_sec,
        )
    return _normalize_with_opencv(
        input_path,
        output_path,
        width=width,
        height=height,
        fps=fps,
        duration_sec=duration_sec,
    )


def _normalize_with_ffmpeg(
    ffmpeg: str,
    input_path: Path,
    output_path: Path,
    *,
    width: int,
    height: int,
    fps: int,
    duration_sec: float,
) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    vf = (
        f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
        f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:black,"
        f"fps={fps}"
    )
    try:
        subprocess.run(
            [
                ffmpeg,
                "-y",
                "-i",
                str(input_path),
                "-an",
                "-vf",
                vf,
                "-t",
                f"{duration_sec:.3f}",
                "-c:v",
                "libx264",
                "-pix_fmt",
                "yuv420p",
                str(output_path),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as exc:
        stderr = exc.stderr or ""
        raise RuntimeError(f"FFmpeg normalize failed: {stderr}") from exc

    return output_path


def _normalize_with_opencv(
    input_path: Path,
    output_path: Path,
    *,
    width: int,
    height: int,
    fps: int,
    duration_sec: float,
) -> Path:
    import cv2

    output_path.parent.mkdir(parents=True, exist_ok=True)
    capture = cv2.VideoCapture(str(input_path))
    if not capture.isOpened():
        raise ValueError(f"Cannot open video: {input_path}")

    frame_total = max(1, int(round(duration_sec * fps)))
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(str(output_path), fourcc, float(fps), (width, height))
    if not writer.isOpened():
        capture.release()
        raise RuntimeError(f"Failed to open VideoWriter for {output_path}")

    written = 0
    last_frame = None
    while written < frame_total:
        ok, frame = capture.read()
        if not ok:
            if last_frame is None:
                break
            frame = last_frame
        else:
            last_frame = cv2.resize(frame, (width, height))
        writer.write(last_frame)
        written += 1

    capture.release()
    writer.release()
    if written == 0:
        raise RuntimeError(f"Failed to normalize clip: {input_path}")
    return output_path


def clip_needs_normalize(
    meta: dict[str, float | int],
    *,
    width: int,
    height: int,
    fps: int,
    duration_sec: float,
    duration_tolerance_sec: float,
) -> bool:
    resolution_ok = int(meta["width"]) == width and int(meta["height"]) == height
    fps_ok = abs(float(meta["fps"]) - fps) <= 1.0
    duration_ok = abs(float(meta["duration_sec"]) - duration_sec) <= duration_tolerance_sec
    return not (resolution_ok and fps_ok and duration_ok)


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
