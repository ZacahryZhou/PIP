"""CLI entrypoint for the PIP video pipeline."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from video_pipeline.orchestrator import PipelineOrchestrator, STOP_AFTER_CHOICES


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="PIP — multi-agent text-to-video pipeline",
    )
    parser.add_argument(
        "--payload",
        required=True,
        help="Path to gateway_payload.json",
    )
    parser.add_argument(
        "--mock",
        action="store_true",
        help="Run in mock mode (no paid external APIs)",
    )
    parser.add_argument(
        "--stop-after",
        choices=sorted(STOP_AFTER_CHOICES),
        default=None,
        help="Stop after this stage (for incremental development)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    payload_path = Path(args.payload)
    if not payload_path.is_file():
        print(f"Payload file not found: {payload_path}", file=sys.stderr)
        return 1

    job = PipelineOrchestrator().run(
        payload_path,
        mock=args.mock,
        stop_after=args.stop_after,
    )
    print(f"Job created: {job.root}")
    print(f"Job ID: {job.job_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
