"""Mock video provider — writes placeholder MP4 clips locally."""

from __future__ import annotations

from pathlib import Path


def generate_mock_clip(
    output_path: Path,
    *,
    width: int,
    height: int,
    fps: int,
    duration_sec: float,
    label: str = "",
) -> Path:
    import cv2
    import numpy as np

    output_path.parent.mkdir(parents=True, exist_ok=True)
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(str(output_path), fourcc, fps, (width, height))
    if not writer.isOpened():
        raise RuntimeError(f"Failed to open VideoWriter for {output_path}")

    frame_total = max(1, int(round(duration_sec * fps)))
    for index in range(frame_total):
        frame = np.zeros((height, width, 3), dtype=np.uint8)
        frame[:, :, 0] = min(255, 40 + index * 3)
        frame[:, :, 1] = min(255, 20 + index * 2)
        frame[:, :, 2] = 80
        if label:
            cv2.putText(
                frame,
                label[:32],
                (40, height // 2),
                cv2.FONT_HERSHEY_SIMPLEX,
                1.0,
                (255, 255, 255),
                2,
                cv2.LINE_AA,
            )
        writer.write(frame)

    writer.release()
    return output_path
