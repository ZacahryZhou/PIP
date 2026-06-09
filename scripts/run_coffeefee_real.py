#!/usr/bin/env python3
"""Run COFFEEFEE real pipeline test (DeepSeek + fal + TTS)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from video_pipeline.gateway_assets import copy_staged_assets_to_job
from video_pipeline.orchestrator import PipelineOrchestrator

ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT / "tests" / "fixtures" / "coffeefee_script.txt"
CHAR_REF = ROOT / "assets" / "characters" / "coffeefee" / "reference.png"
PAYLOAD_PATH = ROOT / "tests" / "fixtures" / "coffeefee_gateway_payload.json"


def build_payload() -> dict:
    script_text = SCRIPT_PATH.read_text(encoding="utf-8")
    base = json.loads(PAYLOAD_PATH.read_text(encoding="utf-8"))
    base["user_script_text"] = script_text
    return base


def main() -> int:
    if not CHAR_REF.is_file():
        print(f"Missing character reference: {CHAR_REF}", file=sys.stderr)
        return 1

    payload = build_payload()
    payload_file = ROOT / "storage" / "coffeefee_live_payload.json"
    payload_file.parent.mkdir(parents=True, exist_ok=True)
    payload_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    bundle = copy_staged_assets_to_job(
        None,  # type: ignore[arg-type]
        [CHAR_REF],
        kind="character",
        ref_ids=["coffeefee"],
    )

    print("Starting real pipeline (mock=False, approval gate ON)...")
    print(f"Payload: {payload_file}")
    print(f"Character ref: {CHAR_REF}")
    print("Pipeline stops at awaiting_storyboard_approval unless you approve and resume.")

    orchestrator = PipelineOrchestrator()
    job = orchestrator.run(
        payload_file,
        mock=False,
        require_approval=True,
        asset_bundle=bundle,
    )

    state_path = job.job_state_path
    state = json.loads(state_path.read_text(encoding="utf-8"))
    print(f"\nJob ID: {job.job_id}")
    print(f"Status: {state.get('status')}")
    print(f"Job dir: {job.root}")

    final = job.root / "output" / "final.mp4"
    if final.is_file():
        print(f"Final video: {final}")
    else:
        print("No final.mp4 yet — check job_state for stage / error.")
        if state.get("error_message"):
            print(f"Error: {state['error_message']}")

    if state.get("status") == "awaiting_storyboard_approval":
        print("Preview ready — approve via Telegram or orchestrator.approve_job before Kling.")
        return 0
    if state.get("status") == "failed_asset_collection":
        return 1
    return 0 if state.get("status") == "delivered" else 1


if __name__ == "__main__":
    raise SystemExit(main())
