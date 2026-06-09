"""Storyboard human approval artifacts and state updates."""

from __future__ import annotations

from datetime import datetime, timezone

from video_pipeline.schemas import JobState, StoryboardApprovalDocument, StoryboardPreviewDocument
from video_pipeline.storage import JobPaths, save_job_state, write_json


def load_preview_document(job: JobPaths) -> StoryboardPreviewDocument:
    if not job.storyboard_preview_path.is_file():
        raise FileNotFoundError(f"Missing preview manifest: {job.storyboard_preview_path}")
    return StoryboardPreviewDocument.model_validate_json(
        job.storyboard_preview_path.read_text(encoding="utf-8")
    )


def load_approval_document(job: JobPaths) -> StoryboardApprovalDocument | None:
    if not job.approval_report_path.is_file():
        return None
    return StoryboardApprovalDocument.model_validate_json(
        job.approval_report_path.read_text(encoding="utf-8")
    )


def write_approval_document(job: JobPaths, document: StoryboardApprovalDocument) -> None:
    write_json(job.approval_report_path, document)


def record_storyboard_approval(
    job: JobPaths,
    *,
    status: str,
    preview_version: int,
    user_message: str | None = None,
    revision_count: int = 0,
) -> StoryboardApprovalDocument:
    approved_at = datetime.now(timezone.utc) if status == "approved" else None
    document = StoryboardApprovalDocument(
        job_id=job.job_id,
        preview_version=preview_version,
        status=status,  # type: ignore[arg-type]
        user_message=user_message,
        approved_at=approved_at,
        revision_count=revision_count,
    )
    write_approval_document(job, document)
    return document


def merge_job_state(
    job: JobPaths,
    *,
    status: str,
    current_stage: str,
    artifact_paths: dict[str, str] | None = None,
    error_message: str | None = None,
) -> JobState:
    existing: dict[str, str] = {}
    if job.job_state_path.is_file():
        existing = JobState.model_validate_json(
            job.job_state_path.read_text(encoding="utf-8")
        ).artifact_paths

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
