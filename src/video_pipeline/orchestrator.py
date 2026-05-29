"""Run pipeline stages in order and persist job state."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from video_pipeline.agents import (
    run_routing_agent,
    run_script_agent,
    run_storyboard_agent,
)
from video_pipeline.config import Settings, settings
from video_pipeline.pipeline import run_generation, run_postproduction, run_quality_control
from video_pipeline.schemas import GatewayPayload, JobState
from video_pipeline.storage import (
    JobPaths,
    copy_rules_snapshot,
    create_job_paths,
    ensure_job_layout,
    resolve_storage_root,
    save_gateway_payload,
    save_job_state,
)

STOP_AFTER_CHOICES = frozenset(
    {
        "received",
        "scripted",
        "storyboarded",
        "routed",
        "generated",
        "validated",
        "assembled",
        "delivered",
    }
)


class PipelineOrchestrator:
    def __init__(self, app_settings: Settings | None = None) -> None:
        self.settings = app_settings or settings

    def run(
        self,
        payload_path: Path,
        *,
        mock: bool = False,
        stop_after: str | None = None,
    ) -> JobPaths:
        if stop_after is not None and stop_after not in STOP_AFTER_CHOICES:
            allowed = ", ".join(sorted(STOP_AFTER_CHOICES))
            raise ValueError(f"stop_after must be one of: {allowed}")

        payload = self._load_payload(payload_path)
        storage_root = resolve_storage_root(self.settings.job_storage_dir)
        storage_root.mkdir(parents=True, exist_ok=True)

        job = ensure_job_layout(create_job_paths(storage_root))
        copy_rules_snapshot(job.root)
        save_gateway_payload(job.gateway_payload_path, payload)

        artifact_paths = {
            "gateway_payload": str(job.gateway_payload_path),
            "rules_snapshot": str(job.rules_snapshot_dir),
        }
        self._update_state(job, status="received", current_stage="received", artifact_paths=artifact_paths)

        if stop_after == "received":
            return job

        # --mock: fixture LLM + mock video. Without --mock: DeepSeek LLM + mock video (step 18 TBD).
        llm_mock = mock
        script = run_script_agent(
            job, payload, mock=llm_mock, app_settings=self.settings
        )
        self._update_state(
            job,
            status="scripted",
            current_stage="scripted",
            artifact_paths={"script": str(job.script_path)},
        )
        if stop_after == "scripted":
            return job

        shots = run_storyboard_agent(
            job, script, mock=llm_mock, app_settings=self.settings
        )
        self._update_state(
            job,
            status="storyboarded",
            current_stage="storyboarded",
            artifact_paths={"shots": str(job.shots_path)},
        )
        if stop_after == "storyboarded":
            return job

        routing = run_routing_agent(
            job,
            shots,
            max_job_cost_usd=self.settings.max_job_cost_usd,
        )
        self._update_state(
            job,
            status="routed",
            current_stage="routed",
            artifact_paths={"routing": str(job.routing_path)},
        )
        if stop_after == "routed" or not routing.should_continue:
            return job

        self._update_state(
            job,
            status="generation_started",
            current_stage="generation_started",
        )
        generation = run_generation(job, shots, routing, settings=self.settings)
        if generation.failed_shot_ids:
            self._update_state(
                job,
                status="failed_generation",
                current_stage="generation",
                error_message=f"Failed shots: {', '.join(generation.failed_shot_ids)}",
                artifact_paths={
                    "generation_report": str(job.reports_dir / "generation_report.json"),
                },
            )
            return job

        self._update_state(
            job,
            status="generated",
            current_stage="generated",
            artifact_paths={
                "generation_report": str(job.reports_dir / "generation_report.json"),
            },
        )
        if stop_after == "generated":
            return job

        self._update_state(job, status="qc_started", current_stage="qc_started")
        qc = run_quality_control(job, shots, generation, settings=self.settings)
        if not qc.all_passed:
            self._update_state(
                job,
                status="failed_qc",
                current_stage="qc",
                error_message=f"Failed shots: {', '.join(qc.failed_shot_ids)}",
                artifact_paths={"qc_report": str(job.reports_dir / "qc_report.json")},
            )
            return job

        self._update_state(
            job,
            status="validated",
            current_stage="validated",
            artifact_paths={"qc_report": str(job.reports_dir / "qc_report.json")},
        )
        if stop_after == "validated":
            return job

        final_path = run_postproduction(job, shots)
        self._update_state(
            job,
            status="assembled",
            current_stage="assembled",
            artifact_paths={
                "assembled_video": str(job.final_dir / "assembled_video.mp4"),
                "final_video": str(final_path),
            },
        )
        if stop_after == "assembled":
            return job

        self._update_state(
            job,
            status="delivered",
            current_stage="delivered",
        )
        return job

    def _load_payload(self, payload_path: Path) -> GatewayPayload:
        data = json.loads(payload_path.read_text(encoding="utf-8"))
        return GatewayPayload.model_validate(data)

    def _update_state(
        self,
        job: JobPaths,
        *,
        status: str,
        current_stage: str,
        artifact_paths: dict[str, str] | None = None,
        error_message: str | None = None,
    ) -> JobState:
        existing: dict[str, str] = {}
        if job.job_state_path.exists():
            existing = json.loads(job.job_state_path.read_text(encoding="utf-8")).get(
                "artifact_paths", {}
            )

        merged = {**existing, **(artifact_paths or {})}
        state = JobState(
            job_id=job.job_id,
            status=status,  # type: ignore[arg-type]
            updated_at=datetime.now(timezone.utc),
            current_stage=current_stage,
            error_message=error_message,
            artifact_paths=merged,
        )
        save_job_state(job.job_state_path, state)
        return state
