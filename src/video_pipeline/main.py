"""CLI entrypoint for the PIP video pipeline."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from video_pipeline.gateway_assets import copy_staged_assets_to_job
from video_pipeline.orchestrator import PipelineOrchestrator, STOP_AFTER_CHOICES


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="PIP — multi-agent text-to-video pipeline",
    )
    parser.add_argument(
        "--payload",
        help="Path to gateway_payload.json (required for new jobs)",
    )
    parser.add_argument(
        "--mock",
        action="store_true",
        help="Use fixture script/shots and mock video (no DeepSeek/fal calls)",
    )
    parser.add_argument(
        "--skip-approval",
        action="store_true",
        help="Skip storyboard preview approval gate (dev / legacy e2e)",
    )
    parser.add_argument(
        "--resume-job",
        help="Continue an approved job by job_id (e.g. job_20260530_010101)",
    )
    parser.add_argument(
        "--stop-after",
        choices=sorted(STOP_AFTER_CHOICES),
        default=None,
        help="Stop after this stage (for incremental development)",
    )
    parser.add_argument(
        "--character-ref",
        action="append",
        dest="character_refs",
        metavar="PATH",
        help="Character reference image to copy into job input/character_refs/ (repeatable)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    orchestrator = PipelineOrchestrator()

    if args.resume_job:
        job = orchestrator.resolve_job(args.resume_job)
        job = orchestrator.resume_job(
            job,
            mock=args.mock,
            stop_after=args.stop_after,
        )
        print(f"Job resumed: {job.root}")
        print(f"Job ID: {job.job_id}")
        return 0

    if not args.payload:
        print("--payload is required unless --resume-job is set", file=sys.stderr)
        return 1

    payload_path = Path(args.payload)
    if not payload_path.is_file():
        print(f"Payload file not found: {payload_path}", file=sys.stderr)
        return 1

    asset_bundle = None
    if args.character_refs:
        ref_paths: list[Path] = []
        for raw in args.character_refs:
            ref_path = Path(raw)
            if not ref_path.is_file():
                print(f"Character reference not found: {ref_path}", file=sys.stderr)
                return 1
            ref_paths.append(ref_path)
        asset_bundle = copy_staged_assets_to_job(
            None,  # type: ignore[arg-type]
            ref_paths,
            kind="character",
        )

    job = orchestrator.run(
        payload_path,
        mock=args.mock,
        stop_after=args.stop_after,
        require_approval=not args.skip_approval,
        asset_bundle=asset_bundle,
    )
    print(f"Job created: {job.root}")
    print(f"Job ID: {job.job_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
