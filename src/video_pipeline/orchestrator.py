"""Run pipeline stages in order and persist job state."""

from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from video_pipeline.agents import (
    run_intake_agent,
    run_plot_agent,
    run_routing_agent,
    run_script_agent,
    run_storyboard_agent,
)
from video_pipeline.agents.intake_clarification_agent import run_intake_clarification_agent
from video_pipeline.config import Settings, settings
from video_pipeline.gateway_assets import (
    GatewayAssetBundle,
    GatewayAssetValidationError,
    apply_gateway_assets,
    validate_payload_assets_on_job,
)
from video_pipeline.pipeline.intake import (
    auto_resolve_all_gaps,
    load_intake_clarification,
    merge_clarification_resolutions,
    parse_intake_clarification_reply,
    save_intake_plan,
    clarification_is_complete,
    apply_intake_resolutions,
)
from video_pipeline.pipeline.approval import merge_job_state, record_storyboard_approval
from video_pipeline.pipeline import run_generation, run_keyframe_generation, run_postproduction, run_quality_control
from video_pipeline.pipeline.character_assets import run_character_assets
from video_pipeline.pipeline.reference_assets import run_reference_assets
from video_pipeline.pipeline.resume import load_routing_plan
from video_pipeline.pipeline.scene_maps import run_scene_maps
from video_pipeline.pipeline.storyboard_gate import validate_storyboard_gate
from video_pipeline.pipeline.storyboard_preview import current_preview_version, run_storyboard_preview
from video_pipeline.pipeline.tts import run_tts_prep
from video_pipeline.schemas import GatewayPayload, JobState, ScriptPlan, ShotsDocument
from video_pipeline.schemas.intake import IntakePlan
from video_pipeline.schemas.plot import PlotPlan
from video_pipeline.storage import (
    JobPaths,
    copy_rules_snapshot,
    create_job_paths,
    ensure_job_layout,
    load_job_paths,
    resolve_storage_root,
    save_gateway_payload,
    write_json,
)

STOP_AFTER_CHOICES = frozenset(
    {
        "received",
        "intake_done",
        "plot_done",
        "awaiting_intake_clarification",
        "scripted",
        "reference_assets_ready",
        "storyboarded",
        "character_assets_ready",
        "scene_maps_ready",
        "preview_ready",
        "awaiting_storyboard_approval",
        "storyboard_gate_passed",
        "routed",
        "tts_ready",
        "keyframes",
        "generated",
        "validated",
        "assembled",
        "delivered",
    }
)

RESUMABLE_STATUSES = frozenset(
    {
        "plot_done",
        "scripted",
        "reference_assets_ready",
        "storyboarded",
        "storyboard_approved",
        "storyboard_gate_passed",
        "routed",
        "character_assets_ready",
        "scene_maps_ready",
        "failed_character_assets",
        "failed_scene_maps",
        "failed_storyboard_gate",
        "tts_started",
        "tts_ready",
        "failed_tts",
        "keyframes_started",
        "keyframes",
        "failed_keyframes",
        "generation_started",
        "generated",
        "failed_generation",
        "qc_started",
        "validated",
        "failed_qc",
        "failed_postproduction",
        "assembled",
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
        require_approval: bool = True,
        asset_bundle: GatewayAssetBundle | None = None,
        auto_resolve_intake_gaps: bool | None = None,
    ) -> JobPaths:
        self._validate_stop_after(stop_after)

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
        merge_job_state(job, status="received", current_stage="received", artifact_paths=artifact_paths)

        if asset_bundle and asset_bundle.staged:
            payload = apply_gateway_assets(job, payload, asset_bundle)
            save_gateway_payload(job.gateway_payload_path, payload)
            artifact_paths["gateway_payload"] = str(job.gateway_payload_path)

        try:
            corrupt_errors = [
                err
                for err in validate_payload_assets_on_job(job, payload)
                if not err.startswith("Missing ")
            ]
            if corrupt_errors:
                raise GatewayAssetValidationError("; ".join(corrupt_errors))
        except GatewayAssetValidationError as exc:
            merge_job_state(
                job,
                status="failed_asset_collection",
                current_stage="asset_collection",
                error_message=str(exc),
                artifact_paths=artifact_paths,
            )
            return job

        if payload.character_reference_images or payload.scene_reference_images:
            merge_job_state(
                job,
                status="assets_collected",
                current_stage="assets_collected",
                artifact_paths=artifact_paths,
            )

        if stop_after == "received":
            return job

        resolve_intake = mock if auto_resolve_intake_gaps is None else auto_resolve_intake_gaps
        intake_outcome = self._run_intake_stage(
            job,
            payload,
            artifact_paths=artifact_paths,
            auto_resolve_gaps=resolve_intake,
        )
        if intake_outcome is None:
            if stop_after == "awaiting_intake_clarification":
                return job
            return job

        payload, intake_plan = intake_outcome
        save_gateway_payload(job.gateway_payload_path, payload)
        save_intake_plan(job, intake_plan)
        artifact_paths = {
            **artifact_paths,
            "intake_plan": str(job.intake_plan_path),
            "gateway_payload": str(job.gateway_payload_path),
        }
        merge_job_state(
            job,
            status="intake_done",
            current_stage="intake_done",
            artifact_paths=artifact_paths,
        )
        if stop_after == "intake_done":
            return job

        return self._run_post_intake_branches(
            job,
            payload,
            intake_plan,
            mock=mock,
            stop_after=stop_after,
            require_approval=require_approval,
        )

    def _run_post_intake_branches(
        self,
        job: JobPaths,
        payload: GatewayPayload,
        intake_plan: IntakePlan,
        *,
        mock: bool,
        stop_after: str | None,
        require_approval: bool,
        resume_from: str | None = None,
    ) -> JobPaths:
        """Intake 一分五路：叙事链 + 资产链（Reference / Character / Scene）并行。"""
        if resume_from is None:
            plot_plan = run_plot_agent(job, payload, intake_plan, mock=mock)
            merge_job_state(
                job,
                status="plot_done",
                current_stage="plot_done",
                artifact_paths={"plot_plan": str(job.plot_plan_path)},
            )
            if stop_after == "plot_done":
                return job
        else:
            if not job.plot_plan_path.is_file():
                raise ValueError(f"Job {job.job_id} cannot resume from {resume_from!r} without plot_plan")
            plot_plan = PlotPlan.model_validate_json(
                job.plot_plan_path.read_text(encoding="utf-8")
            )

        if resume_from in {"scripted", "reference_assets_ready", "storyboarded"}:
            if not job.script_path.is_file():
                raise ValueError(f"Job {job.job_id} cannot resume from {resume_from!r} without script")
            script = ScriptPlan.model_validate_json(job.script_path.read_text(encoding="utf-8"))
        else:
            with ThreadPoolExecutor(max_workers=2) as pool:
                reference_future = pool.submit(
                    run_reference_assets,
                    job,
                    intake_plan,
                    payload,
                    settings=self.settings,
                    mock=mock,
                )
                script = run_script_agent(
                    job,
                    payload,
                    mock=mock,
                    app_settings=self.settings,
                    intake_plan=intake_plan,
                    plot_plan=plot_plan,
                )
                reference_report = reference_future.result()

            merge_job_state(
                job,
                status="scripted",
                current_stage="scripted",
                artifact_paths={"script": str(job.script_path)},
            )
            ref_status = (
                "failed"
                if any(entry.status == "failed" for entry in reference_report.entries)
                else "reference_assets_ready"
            )
            if ref_status == "failed":
                merge_job_state(
                    job,
                    status="failed_assets",
                    current_stage="reference_assets",
                    error_message="Reference asset generation failed",
                    artifact_paths={
                        "reference_asset_report": str(job.reports_dir / "reference_asset_report.json"),
                    },
                )
                return job
            merge_job_state(
                job,
                status="reference_assets_ready",
                current_stage="reference_assets_ready",
                artifact_paths={
                    "reference_asset_report": str(job.reports_dir / "reference_asset_report.json"),
                },
            )
            if stop_after == "scripted":
                return job
            if stop_after == "reference_assets_ready":
                return job

        if resume_from == "storyboarded":
            if not job.shots_path.is_file():
                raise ValueError(f"Job {job.job_id} cannot resume from storyboarded without shots")
            shots = ShotsDocument.model_validate_json(job.shots_path.read_text(encoding="utf-8"))
            return self._run_pre_approval_pipeline(
                job,
                script,
                shots,
                payload,
                mock=mock,
                stop_after=stop_after,
                require_user_approval=require_approval,
                skip_asset_stages=True,
            )

        need_storyboard = stop_after not in {"character_assets_ready", "scene_maps_ready"}

        if stop_after == "character_assets_ready":
            character_report = run_character_assets(
                job,
                payload,
                intake_plan=intake_plan,
                script=script,
                plot_plan=plot_plan,
                settings=self.settings,
                mock=mock,
            )
            failed_characters = [
                entry.character_id for entry in character_report.entries if entry.status == "failed"
            ]
            if failed_characters:
                merge_job_state(
                    job,
                    status="failed_character_assets",
                    current_stage="character_assets_started",
                    error_message=f"Failed character packs: {', '.join(failed_characters)}",
                )
                return job
            merge_job_state(
                job,
                status="character_assets_ready",
                current_stage="character_assets_ready",
                artifact_paths={
                    "character_asset_report": str(job.reports_dir / "character_asset_report.json"),
                },
            )
            return job

        with ThreadPoolExecutor(max_workers=3 if need_storyboard else 2) as pool:
            character_future = pool.submit(
                run_character_assets,
                job,
                payload,
                intake_plan=intake_plan,
                script=script,
                plot_plan=plot_plan,
                settings=self.settings,
                mock=mock,
            )
            scene_future = pool.submit(
                run_scene_maps,
                job,
                payload,
                intake_plan=intake_plan,
                plot_plan=plot_plan,
                script=script,
                settings=self.settings,
                mock=mock,
            )
            if need_storyboard:
                shots = run_storyboard_agent(
                    job,
                    script,
                    mock=mock,
                    app_settings=self.settings,
                    intake_plan=intake_plan,
                )
            else:
                shots = None
            character_report = character_future.result()
            scene_report = scene_future.result()

        failed_characters = [
            entry.character_id for entry in character_report.entries if entry.status == "failed"
        ]
        if failed_characters:
            merge_job_state(
                job,
                status="failed_character_assets",
                current_stage="character_assets_started",
                error_message=f"Failed character packs: {', '.join(failed_characters)}",
            )
            return job

        failed_scenes = [entry.scene_id for entry in scene_report.entries if entry.status == "failed"]
        if failed_scenes:
            merge_job_state(
                job,
                status="failed_scene_maps",
                current_stage="scene_maps_started",
                error_message=f"Failed scene maps: {', '.join(failed_scenes)}",
            )
            return job

        merge_job_state(
            job,
            status="character_assets_ready",
            current_stage="character_assets_ready",
            artifact_paths={
                "character_asset_report": str(job.reports_dir / "character_asset_report.json"),
            },
        )
        merge_job_state(
            job,
            status="scene_maps_ready",
            current_stage="scene_maps_ready",
            artifact_paths={"scene_map_report": str(job.reports_dir / "scene_map_report.json")},
        )
        if not need_storyboard:
            return job

        assert shots is not None
        merge_job_state(
            job,
            status="storyboarded",
            current_stage="storyboarded",
            artifact_paths={"shots": str(job.shots_path)},
        )
        if stop_after == "storyboarded":
            return job

        return self._run_pre_approval_pipeline(
            job,
            script,
            shots,
            payload,
            mock=mock,
            stop_after=stop_after,
            require_user_approval=require_approval,
            skip_asset_stages=True,
        )

    def _run_pre_approval_pipeline(
        self,
        job: JobPaths,
        script: ScriptPlan,
        shots: ShotsDocument,
        payload: GatewayPayload,
        *,
        mock: bool,
        stop_after: str | None,
        require_user_approval: bool,
        skip_asset_stages: bool = False,
    ) -> JobPaths:
        if not skip_asset_stages:
            intake_plan = IntakePlan.model_validate_json(
                job.intake_plan_path.read_text(encoding="utf-8")
            )
            plot_plan: PlotPlan | None = None
            if job.plot_plan_path.is_file():
                plot_plan = PlotPlan.model_validate_json(
                    job.plot_plan_path.read_text(encoding="utf-8")
                )
            merge_job_state(job, status="character_assets_started", current_stage="character_assets_started")
            character_report = run_character_assets(
                job,
                payload,
                intake_plan=intake_plan,
                script=script,
                shots=shots,
                plot_plan=plot_plan,
                settings=self.settings,
                mock=mock,
            )
            failed_characters = [
                entry.character_id for entry in character_report.entries if entry.status == "failed"
            ]
            if failed_characters:
                merge_job_state(
                    job,
                    status="failed_character_assets",
                    current_stage="character_assets_started",
                    error_message=f"Failed character packs: {', '.join(failed_characters)}",
                    artifact_paths={
                        "character_asset_report": str(job.reports_dir / "character_asset_report.json"),
                    },
                )
                return job
            merge_job_state(
                job,
                status="character_assets_ready",
                current_stage="character_assets_ready",
                artifact_paths={
                    "character_asset_report": str(job.reports_dir / "character_asset_report.json"),
                },
            )
            if stop_after == "character_assets_ready":
                return job

            merge_job_state(job, status="scene_maps_started", current_stage="scene_maps_started")
            scene_maps = run_scene_maps(
                job,
                payload,
                intake_plan=intake_plan,
                plot_plan=plot_plan,
                script=script,
                shots=shots,
                settings=self.settings,
                mock=mock,
            )
            failed_scenes = [entry.scene_id for entry in scene_maps.entries if entry.status == "failed"]
            if failed_scenes:
                merge_job_state(
                    job,
                    status="failed_scene_maps",
                    current_stage="scene_maps_started",
                    error_message=f"Failed scene maps: {', '.join(failed_scenes)}",
                    artifact_paths={
                        "scene_map_report": str(job.reports_dir / "scene_map_report.json"),
                    },
                )
                return job
            merge_job_state(
                job,
                status="scene_maps_ready",
                current_stage="scene_maps_ready",
                artifact_paths={"scene_map_report": str(job.reports_dir / "scene_map_report.json")},
            )
            if stop_after == "scene_maps_ready":
                return job

        if require_user_approval:
            return self._run_preview_and_wait(
                job, script, shots, mock=mock, stop_after=stop_after
            )

        preview = self._run_storyboard_preview_stage(job, script, shots, mock=mock)
        record_storyboard_approval(
            job,
            status="approved",
            preview_version=preview.preview_version,
            user_message="auto-approved (require_approval=false)",
        )
        merge_job_state(
            job,
            status="storyboard_approved",
            current_stage="storyboard_approved",
            artifact_paths={"approval_report": str(job.approval_report_path)},
        )
        return self._run_post_approval(
            job,
            script,
            shots,
            mock=mock,
            stop_after=stop_after,
            require_user_approval=False,
        )

    def continue_after_approval(
        self,
        job: JobPaths,
        *,
        mock: bool = False,
        stop_after: str | None = None,
    ) -> JobPaths:
        """Resume an existing job after storyboard approval."""
        self._validate_stop_after(stop_after)
        job = ensure_job_layout(job)

        state = self._load_job_state(job)
        if state.status != "storyboard_approved":
            raise ValueError(
                f"Job {job.job_id} cannot continue from status {state.status!r}"
            )

        script = ScriptPlan.model_validate_json(job.script_path.read_text(encoding="utf-8"))
        shots = ShotsDocument.model_validate_json(job.shots_path.read_text(encoding="utf-8"))

        approval = load_approval_if_needed(job)
        if approval is None or approval.status != "approved":
            raise ValueError(f"Job {job.job_id} has no approved storyboard")

        merge_job_state(
            job,
            status="storyboard_approved",
            current_stage="storyboard_approved",
            artifact_paths={"approval_report": str(job.approval_report_path)},
        )

        return self._run_post_approval(
            job,
            script,
            shots,
            mock=mock,
            stop_after=stop_after,
            require_user_approval=True,
        )

    def resume_job(
        self,
        job: JobPaths,
        *,
        mock: bool = False,
        stop_after: str | None = None,
        require_approval: bool | None = None,
    ) -> JobPaths:
        """Continue a job from its last persisted status without redoing paid artifacts."""
        self._validate_stop_after(stop_after)
        job = ensure_job_layout(job)
        state = self._load_job_state(job)

        if state.status == "awaiting_storyboard_approval":
            raise ValueError(
                f"Job {job.job_id} is awaiting approval — approve or revise before resuming"
            )
        if state.status == "awaiting_intake_clarification":
            raise ValueError(
                f"Job {job.job_id} is awaiting intake clarification — "
                "reply with generate/supplement lines, then intake done"
            )
        if state.status not in RESUMABLE_STATUSES:
            raise ValueError(f"Job {job.job_id} cannot resume from status {state.status!r}")

        if state.status in {"plot_done", "scripted", "reference_assets_ready", "storyboarded"}:
            payload = GatewayPayload.model_validate_json(
                job.gateway_payload_path.read_text(encoding="utf-8")
            )
            intake_plan = IntakePlan.model_validate_json(
                job.intake_plan_path.read_text(encoding="utf-8")
            )
            return self._run_post_intake_branches(
                job,
                payload,
                intake_plan,
                mock=mock,
                stop_after=stop_after,
                require_approval=require_approval if require_approval is not None else True,
                resume_from=state.status,
            )

        script = ScriptPlan.model_validate_json(job.script_path.read_text(encoding="utf-8"))
        payload = GatewayPayload.model_validate_json(
            job.gateway_payload_path.read_text(encoding="utf-8")
        )
        shots: ShotsDocument | None = None
        if job.shots_path.is_file():
            shots = ShotsDocument.model_validate_json(job.shots_path.read_text(encoding="utf-8"))

        pre_approval_statuses = {
            "character_assets_ready",
            "failed_character_assets",
            "scene_maps_ready",
            "failed_scene_maps",
            "preview_ready",
            "failed_preview",
            "failed_storyboard_gate",
        }
        if state.status in pre_approval_statuses:
            return self._resume_pre_approval(
                job,
                script,
                shots,
                payload,
                mock=mock,
                stop_after=stop_after,
                require_approval=require_approval if require_approval is not None else False,
            )

        if state.status == "storyboard_approved":
            if shots is None:
                raise ValueError(f"Job {job.job_id} is approved but has no shots artifact")
            approval = load_approval_if_needed(job)
            if approval is None or approval.status != "approved":
                raise ValueError(f"Job {job.job_id} has no approved storyboard")

        require_user_approval = (
            require_approval if require_approval is not None else True
        )
        if shots is None:
            raise ValueError(f"Job {job.job_id} cannot resume post-approval without shots")
        return self._run_post_approval(
            job,
            script,
            shots,
            mock=mock,
            stop_after=stop_after,
            require_user_approval=require_user_approval,
        )

    def approve_job(
        self,
        job: JobPaths,
        *,
        preview_version: int,
        user_message: str | None = None,
    ) -> JobPaths:
        job = ensure_job_layout(job)
        record_storyboard_approval(
            job,
            status="approved",
            preview_version=preview_version,
            user_message=user_message,
        )
        merge_job_state(
            job,
            status="storyboard_approved",
            current_stage="storyboard_approved",
            artifact_paths={"approval_report": str(job.approval_report_path)},
        )
        return job

    def cancel_job(
        self,
        job: JobPaths,
        *,
        preview_version: int,
        user_message: str | None = None,
    ) -> JobPaths:
        job = ensure_job_layout(job)
        record_storyboard_approval(
            job,
            status="cancelled",
            preview_version=preview_version,
            user_message=user_message,
        )
        merge_job_state(
            job,
            status="cancelled_user",
            current_stage="awaiting_storyboard_approval",
            error_message=user_message or "Cancelled by user",
            artifact_paths={"approval_report": str(job.approval_report_path)},
        )
        return job

    def request_revision(
        self,
        job: JobPaths,
        *,
        preview_version: int,
        user_message: str | None = None,
    ) -> JobPaths:
        job = ensure_job_layout(job)
        existing = load_approval_if_needed(job)
        revision_count = (existing.revision_count + 1) if existing else 1
        record_storyboard_approval(
            job,
            status="revision_requested",
            preview_version=preview_version,
            user_message=user_message,
            revision_count=revision_count,
        )
        merge_job_state(
            job,
            status="storyboard_revision_requested",
            current_stage="awaiting_storyboard_approval",
            artifact_paths={"approval_report": str(job.approval_report_path)},
        )
        return job

    def revise_storyboard(
        self,
        job: JobPaths,
        revision_notes: str,
        *,
        mock: bool = False,
    ) -> JobPaths:
        """Re-run storyboard + preview after user revision notes."""
        job = ensure_job_layout(job)
        state = self._load_job_state(job)
        if state.status not in {"awaiting_storyboard_approval", "storyboard_revision_requested"}:
            raise ValueError(
                f"Job {job.job_id} cannot revise from status {state.status!r}"
            )

        notes = revision_notes.strip()
        if not notes:
            raise ValueError("Revision notes must not be empty")

        approval = load_approval_if_needed(job)
        if approval and approval.revision_count >= self.settings.max_storyboard_revisions:
            raise ValueError(
                f"Maximum storyboard revisions ({self.settings.max_storyboard_revisions}) reached"
            )

        script = ScriptPlan.model_validate_json(job.script_path.read_text(encoding="utf-8"))
        llm_mock = mock
        shots = run_storyboard_agent(
            job,
            script,
            mock=llm_mock,
            app_settings=self.settings,
            revision_notes=notes,
        )
        merge_job_state(
            job,
            status="storyboarded",
            current_stage="storyboarded",
            artifact_paths={"shots": str(job.shots_path)},
        )

        next_version = current_preview_version(job) + 1
        merge_job_state(job, status="preview_started", current_stage="preview_started")
        preview = run_storyboard_preview(
            job,
            script,
            shots,
            settings=self.settings,
            mock=mock,
            preview_version=next_version,
        )
        merge_job_state(
            job,
            status="preview_ready",
            current_stage="preview_ready",
            artifact_paths={
                "storyboard_preview": str(job.storyboard_preview_path),
                "preview_report": str(job.reports_dir / "preview_report.json"),
            },
        )

        revision_count = approval.revision_count if approval else 0
        record_storyboard_approval(
            job,
            status="pending",
            preview_version=preview.preview_version,
            revision_count=revision_count,
        )
        merge_job_state(
            job,
            status="awaiting_storyboard_approval",
            current_stage="awaiting_storyboard_approval",
            artifact_paths={"approval_report": str(job.approval_report_path)},
        )
        return job

    def _run_storyboard_preview_stage(
        self,
        job: JobPaths,
        script: ScriptPlan,
        shots: ShotsDocument,
        *,
        mock: bool,
        preview_version: int | None = None,
    ):
        merge_job_state(job, status="preview_started", current_stage="preview_started")
        preview = run_storyboard_preview(
            job,
            script,
            shots,
            settings=self.settings,
            mock=mock,
            preview_version=preview_version,
        )
        merge_job_state(
            job,
            status="preview_ready",
            current_stage="preview_ready",
            artifact_paths={
                "storyboard_preview": str(job.storyboard_preview_path),
                "preview_report": str(job.reports_dir / "preview_report.json"),
            },
        )
        return preview

    def _resume_pre_approval(
        self,
        job: JobPaths,
        script: ScriptPlan,
        shots: ShotsDocument | None,
        payload: GatewayPayload,
        *,
        mock: bool,
        stop_after: str | None,
        require_approval: bool,
    ) -> JobPaths:
        """Continue interrupted jobs before storyboard approval."""
        from video_pipeline.pipeline.approval import load_preview_document
        from video_pipeline.pipeline.resume import scene_maps_complete

        intake_plan = IntakePlan.model_validate_json(
            job.intake_plan_path.read_text(encoding="utf-8")
        )
        plot_plan: PlotPlan | None = None
        if job.plot_plan_path.is_file():
            plot_plan = PlotPlan.model_validate_json(job.plot_plan_path.read_text(encoding="utf-8"))

        character_report_path = job.reports_dir / "character_asset_report.json"
        if not character_report_path.is_file():
            merge_job_state(job, status="character_assets_started", current_stage="character_assets_started")
            character_report = run_character_assets(
                job,
                payload,
                intake_plan=intake_plan,
                script=script,
                shots=shots,
                plot_plan=plot_plan,
                settings=self.settings,
                mock=mock,
            )
            failed_characters = [
                entry.character_id for entry in character_report.entries if entry.status == "failed"
            ]
            if failed_characters:
                merge_job_state(
                    job,
                    status="failed_character_assets",
                    current_stage="character_assets_started",
                    error_message=f"Failed character packs: {', '.join(failed_characters)}",
                )
                return job
            merge_job_state(
                job,
                status="character_assets_ready",
                current_stage="character_assets_ready",
                artifact_paths={"character_asset_report": str(character_report_path)},
            )
        if stop_after == "character_assets_ready":
            return job

        if not scene_maps_complete(job, script):
            merge_job_state(job, status="scene_maps_started", current_stage="scene_maps_started")
            scene_maps = run_scene_maps(
                job,
                payload,
                intake_plan=intake_plan,
                plot_plan=plot_plan,
                script=script,
                shots=shots,
                settings=self.settings,
                mock=mock,
            )
            failed_scenes = [entry.scene_id for entry in scene_maps.entries if entry.status == "failed"]
            if failed_scenes:
                merge_job_state(
                    job,
                    status="failed_scene_maps",
                    current_stage="scene_maps_started",
                    error_message=f"Failed scene maps: {', '.join(failed_scenes)}",
                )
                return job
            merge_job_state(
                job,
                status="scene_maps_ready",
                current_stage="scene_maps_ready",
                artifact_paths={"scene_map_report": str(job.reports_dir / "scene_map_report.json")},
            )
        if stop_after == "scene_maps_ready":
            return job

        if shots is None:
            shots = run_storyboard_agent(
                job,
                script,
                mock=mock,
                app_settings=self.settings,
                intake_plan=intake_plan,
            )
            merge_job_state(
                job,
                status="storyboarded",
                current_stage="storyboarded",
                artifact_paths={"shots": str(job.shots_path)},
            )

        if not job.storyboard_preview_path.is_file():
            preview = self._run_storyboard_preview_stage(job, script, shots, mock=mock)
        else:
            preview = load_preview_document(job)
            merge_job_state(
                job,
                status="preview_ready",
                current_stage="preview_ready",
                artifact_paths={
                    "storyboard_preview": str(job.storyboard_preview_path),
                    "preview_report": str(job.reports_dir / "preview_report.json"),
                },
            )
        if stop_after == "preview_ready":
            return job

        approval = None
        try:
            approval = load_approval_if_needed(job)
        except FileNotFoundError:
            approval = None

        if require_approval and (approval is None or approval.status != "approved"):
            if approval is None or approval.status != "pending":
                record_storyboard_approval(
                    job,
                    status="pending",
                    preview_version=preview.preview_version,
                )
            merge_job_state(
                job,
                status="awaiting_storyboard_approval",
                current_stage="awaiting_storyboard_approval",
                artifact_paths={"approval_report": str(job.approval_report_path)},
            )
            return job

        if approval is None or approval.status != "approved":
            record_storyboard_approval(
                job,
                status="approved",
                preview_version=preview.preview_version,
                user_message="auto-approved on resume",
            )
            merge_job_state(
                job,
                status="storyboard_approved",
                current_stage="storyboard_approved",
                artifact_paths={"approval_report": str(job.approval_report_path)},
            )

        return self._run_post_approval(
            job,
            script,
            shots,
            mock=mock,
            stop_after=stop_after,
            require_user_approval=require_approval,
        )

    def _run_preview_and_wait(
        self,
        job: JobPaths,
        script: ScriptPlan,
        shots: ShotsDocument,
        *,
        mock: bool,
        stop_after: str | None,
    ) -> JobPaths:
        preview = self._run_storyboard_preview_stage(job, script, shots, mock=mock)
        if stop_after == "preview_ready":
            return job

        record_storyboard_approval(
            job,
            status="pending",
            preview_version=preview.preview_version,
        )
        merge_job_state(
            job,
            status="awaiting_storyboard_approval",
            current_stage="awaiting_storyboard_approval",
            artifact_paths={"approval_report": str(job.approval_report_path)},
        )
        return job

    def _run_post_approval(
        self,
        job: JobPaths,
        script: ScriptPlan,
        shots: ShotsDocument,
        *,
        mock: bool,
        stop_after: str | None,
        require_user_approval: bool = True,
    ) -> JobPaths:
        gate = validate_storyboard_gate(
            job,
            shots,
            require_user_approval=require_user_approval,
        )
        if not gate.passed:
            merge_job_state(
                job,
                status="failed_storyboard_gate",
                current_stage="storyboard_gate",
                error_message="; ".join(gate.blocking_reasons),
            )
            return job

        merge_job_state(
            job,
            status="storyboard_gate_passed",
            current_stage="storyboard_gate_passed",
        )
        if stop_after == "storyboard_gate_passed":
            return job

        existing_routing = load_routing_plan(job)
        if existing_routing is not None:
            routing = existing_routing
        else:
            routing = run_routing_agent(
                job,
                shots,
                max_job_cost_usd=self.settings.max_job_cost_usd,
            )
        merge_job_state(
            job,
            status="routed",
            current_stage="routed",
            artifact_paths={"routing": str(job.routing_path)},
        )
        if not routing.should_continue:
            merge_job_state(
                job,
                status="cancelled_budget",
                current_stage="routed",
                error_message=routing.budget_message
                or f"Estimated cost exceeds budget ${self.settings.max_job_cost_usd:.2f}",
                artifact_paths={"routing": str(job.routing_path)},
            )
            return job
        if stop_after == "routed":
            return job

        merge_job_state(job, status="tts_started", current_stage="tts_started")
        with ThreadPoolExecutor(max_workers=2) as pool:
            tts_future = pool.submit(
                run_tts_prep,
                job,
                script,
                shots,
                settings=self.settings,
                mock=mock,
            )

            merge_job_state(job, status="keyframes_started", current_stage="keyframes_started")
            keyframes = run_keyframe_generation(
                job, script, shots, routing, settings=self.settings, mock=mock
            )
            failed_keyframes = [item.shot_id for item in keyframes.results if item.status == "failed"]
            if failed_keyframes:
                merge_job_state(
                    job,
                    status="failed_keyframes",
                    current_stage="keyframes",
                    error_message=f"Failed keyframes: {', '.join(failed_keyframes)}",
                    artifact_paths={
                        "keyframe_report": str(job.reports_dir / "keyframe_report.json"),
                    },
                )
                return job

            merge_job_state(
                job,
                status="keyframes",
                current_stage="keyframes",
                artifact_paths={
                    "keyframe_report": str(job.reports_dir / "keyframe_report.json"),
                },
            )
            if stop_after == "keyframes":
                tts_report = tts_future.result()
                if tts_report.status == "failed":
                    merge_job_state(
                        job,
                        status="failed_tts",
                        current_stage="tts_started",
                        error_message=f"Failed TTS lines: {', '.join(tts_report.failed_line_ids)}",
                        artifact_paths={"tts_report": str(job.reports_dir / "tts_report.json")},
                    )
                else:
                    merge_job_state(
                        job,
                        status="tts_ready",
                        current_stage="tts_ready",
                        artifact_paths={"tts_report": str(job.reports_dir / "tts_report.json")},
                    )
                return job

            merge_job_state(
                job,
                status="generation_started",
                current_stage="generation_started",
            )
            generation = run_generation(job, script, shots, routing, settings=self.settings, mock=mock)
            if generation.failed_shot_ids:
                merge_job_state(
                    job,
                    status="failed_generation",
                    current_stage="generation",
                    error_message=f"Failed shots: {', '.join(generation.failed_shot_ids)}",
                    artifact_paths={
                        "generation_report": str(job.reports_dir / "generation_report.json"),
                    },
                )
                return job

            merge_job_state(
                job,
                status="generated",
                current_stage="generated",
                artifact_paths={
                    "generation_report": str(job.reports_dir / "generation_report.json"),
                },
            )
            if stop_after == "generated":
                tts_report = tts_future.result()
                if tts_report.status == "failed":
                    merge_job_state(
                        job,
                        status="failed_tts",
                        current_stage="tts_started",
                        error_message=f"Failed TTS lines: {', '.join(tts_report.failed_line_ids)}",
                        artifact_paths={"tts_report": str(job.reports_dir / "tts_report.json")},
                    )
                else:
                    merge_job_state(
                        job,
                        status="tts_ready",
                        current_stage="tts_ready",
                        artifact_paths={"tts_report": str(job.reports_dir / "tts_report.json")},
                    )
                return job

            merge_job_state(job, status="qc_started", current_stage="qc_started")
            qc = run_quality_control(job, shots, generation, settings=self.settings)
            if not qc.all_passed:
                merge_job_state(
                    job,
                    status="failed_qc",
                    current_stage="qc",
                    error_message=f"Failed shots: {', '.join(qc.failed_shot_ids)}",
                    artifact_paths={"qc_report": str(job.reports_dir / "qc_report.json")},
                )
                return job

            merge_job_state(
                job,
                status="validated",
                current_stage="validated",
                artifact_paths={"qc_report": str(job.reports_dir / "qc_report.json")},
            )

            tts_report = tts_future.result()
            if tts_report.status == "failed":
                merge_job_state(
                    job,
                    status="failed_tts",
                    current_stage="tts_started",
                    error_message=f"Failed TTS lines: {', '.join(tts_report.failed_line_ids)}",
                    artifact_paths={"tts_report": str(job.reports_dir / "tts_report.json")},
                )
                return job

            merge_job_state(
                job,
                status="tts_ready",
                current_stage="tts_ready",
                artifact_paths={"tts_report": str(job.reports_dir / "tts_report.json")},
            )
            if stop_after in {"tts_ready", "validated"}:
                return job

        final_path = run_postproduction(
            job, script, shots, settings=self.settings, mock=mock
        )
        merge_job_state(
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

        merge_job_state(
            job,
            status="delivered",
            current_stage="delivered",
        )
        return job

    def _load_payload(self, payload_path: Path) -> GatewayPayload:
        data = json.loads(payload_path.read_text(encoding="utf-8"))
        return GatewayPayload.model_validate(data)

    def _load_job_state(self, job: JobPaths) -> JobState:
        return JobState.model_validate_json(job.job_state_path.read_text(encoding="utf-8"))

    def _validate_stop_after(self, stop_after: str | None) -> None:
        if stop_after is not None and stop_after not in STOP_AFTER_CHOICES:
            allowed = ", ".join(sorted(STOP_AFTER_CHOICES))
            raise ValueError(f"stop_after must be one of: {allowed}")

    def resolve_intake_clarification(
        self,
        job: JobPaths,
        user_message: str,
        *,
        mock: bool = False,
        stop_after: str | None = None,
        require_approval: bool = True,
        asset_bundle: GatewayAssetBundle | None = None,
        auto_resolve_intake_gaps: bool | None = None,
    ) -> JobPaths:
        """Apply user choices for intake gaps and continue the pipeline."""
        self._validate_stop_after(stop_after)
        job = ensure_job_layout(job)
        state = self._load_job_state(job)
        if state.status != "awaiting_intake_clarification":
            raise ValueError(
                f"Job {job.job_id} is not awaiting intake clarification "
                f"(status={state.status!r})"
            )

        document = load_intake_clarification(job)
        if document is None:
            raise ValueError(f"Job {job.job_id} has no intake clarification document")

        command, resolutions = parse_intake_clarification_reply(user_message)
        if command == "cancel":
            document = document.model_copy(update={"status": "cancelled"})
            write_json(job.intake_clarification_path, document)
            merge_job_state(
                job,
                status="cancelled_user",
                current_stage="intake_clarification",
                error_message="Cancelled during intake clarification",
                artifact_paths={"intake_clarification": str(job.intake_clarification_path)},
            )
            return job

        if command == "unknown":
            raise ValueError(
                "Unrecognized intake reply. Use: generate <编号>, "
                "supplement <编号> <内容>, intake done, or intake cancel."
            )

        if resolutions:
            document = merge_clarification_resolutions(document, resolutions)
            write_json(job.intake_clarification_path, document)

        if command != "done" and not clarification_is_complete(document):
            merge_job_state(
                job,
                status="awaiting_intake_clarification",
                current_stage="awaiting_intake_clarification",
                artifact_paths={
                    "intake_clarification": str(job.intake_clarification_path)
                },
            )
            return job

        if not clarification_is_complete(document):
            raise ValueError(
                "Required intake gaps are still unresolved. "
                "Reply generate/supplement for each required item, then intake done."
            )

        payload = GatewayPayload.model_validate_json(
            job.gateway_payload_path.read_text(encoding="utf-8")
        )
        if asset_bundle and asset_bundle.staged:
            payload = apply_gateway_assets(job, payload, asset_bundle)
            save_gateway_payload(job.gateway_payload_path, payload)

        from datetime import datetime, timezone

        from video_pipeline.agents.intake_agent import build_intake_plan
        from video_pipeline.schemas.intake import IntakeGapResolution

        merged_resolutions = list(document.resolutions)
        resolved_ids = {item.gap_id for item in merged_resolutions}
        for gap in document.gaps:
            if gap.gap_id in resolved_ids:
                continue
            merged_resolutions.append(
                IntakeGapResolution(
                    gap_id=gap.gap_id,
                    choice="system_generate",
                    resolved_at=datetime.now(timezone.utc),
                )
            )

        payload = apply_intake_resolutions(payload, document.gaps, merged_resolutions)
        save_gateway_payload(job.gateway_payload_path, payload)

        intake_plan = build_intake_plan(job, payload)
        save_intake_plan(job, intake_plan)
        document = document.model_copy(
            update={
                "status": "resolved",
                "resolutions": merged_resolutions,
                "resolved_at": datetime.now(timezone.utc),
            }
        )
        write_json(job.intake_clarification_path, document)

        merge_job_state(
            job,
            status="intake_done",
            current_stage="intake_done",
            artifact_paths={
                "intake_plan": str(job.intake_plan_path),
                "intake_clarification": str(job.intake_clarification_path),
                "gateway_payload": str(job.gateway_payload_path),
            },
        )
        if stop_after == "intake_done":
            return job

        return self._run_post_intake_branches(
            job,
            payload,
            intake_plan,
            mock=mock,
            stop_after=stop_after,
            require_approval=require_approval,
        )

    def _run_intake_stage(
        self,
        job: JobPaths,
        payload: GatewayPayload,
        *,
        artifact_paths: dict[str, str],
        auto_resolve_gaps: bool,
    ) -> tuple[GatewayPayload, object] | None:
        from video_pipeline.agents.intake_agent import build_intake_plan

        analysis = run_intake_agent(job, payload)
        gaps = list(analysis.gaps)

        if gaps and auto_resolve_gaps:
            payload = auto_resolve_all_gaps(payload, gaps)
            plan = build_intake_plan(job, payload)
            return payload, plan

        if gaps:
            clarification = run_intake_clarification_agent(job, gaps)
            merge_job_state(
                job,
                status="awaiting_intake_clarification",
                current_stage="awaiting_intake_clarification",
                artifact_paths={
                    **artifact_paths,
                    "intake_clarification": str(job.intake_clarification_path),
                },
            )
            return None

        return payload, analysis.plan

    def resolve_job(self, job_id: str) -> JobPaths:
        storage_root = resolve_storage_root(self.settings.job_storage_dir)
        return load_job_paths(storage_root, job_id)


def load_approval_if_needed(job: JobPaths):
    from video_pipeline.pipeline.approval import load_approval_document

    return load_approval_document(job)
