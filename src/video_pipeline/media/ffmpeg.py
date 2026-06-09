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


_FFMPEG_FULL_PATHS = (
    "/opt/homebrew/opt/ffmpeg-full/bin/ffmpeg",
    "/usr/local/opt/ffmpeg-full/bin/ffmpeg",
)


def _ffmpeg_candidates() -> list[str]:
    seen: set[str] = set()
    candidates: list[str] = []
    for path in (*_FFMPEG_FULL_PATHS, shutil.which("ffmpeg")):
        if not path or path in seen:
            continue
        if Path(path).is_file():
            seen.add(path)
            candidates.append(path)
    return candidates


def _ffmpeg_path() -> str | None:
    candidates = _ffmpeg_candidates()
    return candidates[0] if candidates else None


def _ffmpeg_supports_subtitle_burn(ffmpeg: str | None = None) -> bool:
    """Return True when ffmpeg was built with libass (subtitles/ass filters)."""
    paths = [ffmpeg] if ffmpeg else _ffmpeg_candidates()
    for path in paths:
        if not path:
            continue
        try:
            result = subprocess.run(
                [path, "-filters"],
                check=True,
                capture_output=True,
                text=True,
            )
        except subprocess.CalledProcessError:
            continue
        output = result.stdout + result.stderr
        if " subtitles " in output or " ass " in output:
            return True
    return False


def _ffmpeg_for_subtitle_burn() -> str | None:
    for path in _ffmpeg_candidates():
        if _ffmpeg_supports_subtitle_burn(path):
            return path
    return None


def probe_audio_duration(path: Path) -> float:
    """Return audio duration in seconds via ffprobe, or 0.0 when unavailable."""
    ffprobe = shutil.which("ffprobe")
    if ffprobe is None:
        return 0.0
    try:
        result = subprocess.run(
            [
                ffprobe,
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                str(path),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError:
        return 0.0
    try:
        return float(result.stdout.strip())
    except ValueError:
        return 0.0


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


def probe_has_audio(path: Path) -> bool:
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        return False
    try:
        result = subprocess.run(
            [
                ffprobe,
                "-v",
                "error",
                "-select_streams",
                "a",
                "-show_entries",
                "stream=codec_type",
                "-of",
                "csv=p=0",
                str(path),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError:
        return False
    return "audio" in result.stdout


def generate_silent_wav(output_path: Path, *, duration_sec: float, sample_rate: int = 44100) -> Path:
    ffmpeg = _ffmpeg_path()
    if not ffmpeg:
        raise RuntimeError("FFmpeg is required for audio generation")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        subprocess.run(
            [
                ffmpeg,
                "-y",
                "-f",
                "lavfi",
                "-i",
                f"anullsrc=r={sample_rate}:cl=stereo",
                "-t",
                f"{duration_sec:.3f}",
                str(output_path),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(f"FFmpeg silent audio failed: {exc.stderr or ''}") from exc
    return output_path


def generate_tone_wav(
    output_path: Path,
    *,
    duration_sec: float,
    frequency_hz: int = 220,
    sample_rate: int = 44100,
) -> Path:
    ffmpeg = _ffmpeg_path()
    if not ffmpeg:
        raise RuntimeError("FFmpeg is required for audio generation")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        subprocess.run(
            [
                ffmpeg,
                "-y",
                "-f",
                "lavfi",
                "-i",
                f"sine=frequency={frequency_hz}:sample_rate={sample_rate}",
                "-t",
                f"{duration_sec:.3f}",
                "-af",
                "volume=0.08",
                str(output_path),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(f"FFmpeg tone audio failed: {exc.stderr or ''}") from exc
    return output_path


def trim_or_loop_audio(input_path: Path, output_path: Path, *, duration_sec: float) -> Path:
    ffmpeg = _ffmpeg_path()
    if not ffmpeg:
        raise RuntimeError("FFmpeg is required for audio trimming")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        subprocess.run(
            [
                ffmpeg,
                "-y",
                "-stream_loop",
                "-1",
                "-i",
                str(input_path),
                "-t",
                f"{duration_sec:.3f}",
                "-c:a",
                "pcm_s16le",
                str(output_path),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(f"FFmpeg trim/loop audio failed: {exc.stderr or ''}") from exc
    return output_path


def convert_audio_to_wav(input_path: Path, output_path: Path) -> Path:
    ffmpeg = _ffmpeg_path()
    if not ffmpeg:
        raise RuntimeError("FFmpeg is required for audio conversion")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        subprocess.run(
            [
                ffmpeg,
                "-y",
                "-i",
                str(input_path),
                "-ac",
                "2",
                "-ar",
                "44100",
                str(output_path),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(f"FFmpeg audio convert failed: {exc.stderr or ''}") from exc
    return output_path


def build_vo_track(
    segments: list[tuple[Path, float]],
    output_path: Path,
    *,
    total_duration_sec: float,
) -> Path | None:
    if not segments:
        return None

    ffmpeg = _ffmpeg_path()
    if not ffmpeg:
        raise RuntimeError("FFmpeg is required for VO mixing")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    inputs: list[str] = []
    filter_parts: list[str] = []
    for index, (segment_path, start_sec) in enumerate(segments):
        inputs.extend(["-i", str(segment_path)])
        delay_ms = max(0, int(round(start_sec * 1000)))
        filter_parts.append(f"[{index}:a]adelay={delay_ms}|{delay_ms}[vo{index}]")

    mix_inputs = "".join(f"[vo{index}]" for index in range(len(segments)))
    filter_parts.append(
        f"{mix_inputs}amix=inputs={len(segments)}:duration=longest:dropout_transition=0[vo_mix]"
    )
    filter_parts.append(f"[vo_mix]apad=whole_dur={total_duration_sec:.3f}[vo_out]")
    filter_complex = ";".join(filter_parts)

    try:
        subprocess.run(
            [
                ffmpeg,
                "-y",
                *inputs,
                "-filter_complex",
                filter_complex,
                "-map",
                "[vo_out]",
                str(output_path),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(f"FFmpeg VO track failed: {exc.stderr or ''}") from exc
    return output_path


def mix_bgm_and_vo(
    bgm_path: Path,
    vo_path: Path | None,
    output_path: Path,
    *,
    bgm_volume: float,
    fade_out_sec: float,
    total_duration_sec: float,
) -> Path:
    ffmpeg = _ffmpeg_path()
    if not ffmpeg:
        raise RuntimeError("FFmpeg is required for audio mixing")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    fade_start = max(0.0, total_duration_sec - fade_out_sec)

    if vo_path is None:
        filter_complex = (
            f"[0:a]volume={bgm_volume},afade=t=out:st={fade_start:.3f}:d={fade_out_sec:.3f}[out]"
        )
        maps = ["-map", "[out]"]
        inputs = ["-i", str(bgm_path)]
    else:
        filter_complex = (
            f"[0:a]volume={bgm_volume},afade=t=out:st={fade_start:.3f}:d={fade_out_sec:.3f}[bgm];"
            f"[1:a]volume=1.0[vo];"
            f"[bgm][vo]amix=inputs=2:duration=longest:dropout_transition=0[out]"
        )
        maps = ["-map", "[out]"]
        inputs = ["-i", str(bgm_path), "-i", str(vo_path)]

    try:
        subprocess.run(
            [
                ffmpeg,
                "-y",
                *inputs,
                "-filter_complex",
                filter_complex,
                *maps,
                str(output_path),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(f"FFmpeg audio mix failed: {exc.stderr or ''}") from exc
    return output_path


def mux_video_with_audio(video_path: Path, audio_path: Path, output_path: Path) -> Path:
    ffmpeg = _ffmpeg_path()
    if not ffmpeg:
        raise RuntimeError("FFmpeg is required for muxing")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        subprocess.run(
            [
                ffmpeg,
                "-y",
                "-i",
                str(video_path),
                "-i",
                str(audio_path),
                "-c:v",
                "copy",
                "-c:a",
                "aac",
                "-b:a",
                "192k",
                "-shortest",
                str(output_path),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(f"FFmpeg mux failed: {exc.stderr or ''}") from exc
    return output_path


def burn_subtitles(
    video_path: Path,
    srt_path: Path,
    output_path: Path,
    *,
    font_name: str = "Arial",
) -> Path:
    ffmpeg = _ffmpeg_for_subtitle_burn()
    if not ffmpeg:
        plain = _ffmpeg_path()
        if not plain:
            raise RuntimeError(
                "FFmpeg is required for subtitle burn-in. Install with: brew install ffmpeg"
            )
        raise RuntimeError(
            "FFmpeg is installed but missing libass (subtitles filter). "
            "Install a full build with: brew install ffmpeg-full"
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    work_dir = output_path.parent
    local_srt = work_dir / "_pip_burn.srt"
    shutil.copy2(srt_path, local_srt)

    meta = probe_video(video_path)
    frame_height = int(meta["height"])
    font_size = max(18, int(round(frame_height * 0.04)))
    force_style = (
        f"FontName={font_name},FontSize={font_size},PrimaryColour=&HFFFFFF,"
        "OutlineColour=&H000000,Outline=2,BorderStyle=1,Alignment=2,MarginV=86"
    )
    escaped_style = force_style.replace("\\", "\\\\").replace(",", r"\,")
    vf = f"subtitles=_pip_burn.srt:force_style={escaped_style}"
    try:
        subprocess.run(
            [
                ffmpeg,
                "-y",
                "-i",
                video_path.name,
                "-vf",
                vf,
                "-c:v",
                "libx264",
                "-pix_fmt",
                "yuv420p",
                "-c:a",
                "copy",
                output_path.name,
            ],
            check=True,
            capture_output=True,
            text=True,
            cwd=str(work_dir),
        )
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(f"FFmpeg subtitle burn failed: {exc.stderr or ''}") from exc
    finally:
        local_srt.unlink(missing_ok=True)

    return output_path


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
