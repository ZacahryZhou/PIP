"""Intake clarification persistence and resolution."""

from __future__ import annotations

import re
from datetime import datetime, timezone

from video_pipeline.schemas import GatewayPayload
from video_pipeline.schemas.intake import (
    IntakeClarificationDocument,
    IntakeGap,
    IntakeGapChoice,
    IntakeGapResolution,
    IntakePlan,
)
from video_pipeline.storage import JobPaths, write_json

_GENERATE_RE = re.compile(r"^generate\s+(gap_\d+|\d+)\s*$", re.IGNORECASE)
_SUPPLEMENT_RE = re.compile(
    r"^supplement\s+(gap_\d+|\d+)\s+(.+)$",
    re.IGNORECASE | re.DOTALL,
)


def load_intake_plan(job: JobPaths) -> IntakePlan | None:
    if not job.intake_plan_path.is_file():
        return None
    return IntakePlan.model_validate_json(job.intake_plan_path.read_text(encoding="utf-8"))


def load_intake_clarification(job: JobPaths) -> IntakeClarificationDocument | None:
    if not job.intake_clarification_path.is_file():
        return None
    return IntakeClarificationDocument.model_validate_json(
        job.intake_clarification_path.read_text(encoding="utf-8")
    )


def save_intake_plan(job: JobPaths, plan: IntakePlan) -> None:
    write_json(job.intake_plan_path, plan)


def unresolved_gaps(document: IntakeClarificationDocument) -> list[IntakeGap]:
    resolved_ids = {item.gap_id for item in document.resolutions if item.choice != "pending"}
    return [gap for gap in document.gaps if gap.gap_id not in resolved_ids]


def parse_intake_clarification_reply(text: str) -> tuple[str, list[IntakeGapResolution]]:
    """Return (command, resolutions). command is done|cancel|partial|unknown."""
    stripped = text.strip()
    lowered = stripped.lower()
    if lowered in {"intake done", "done", "完成"}:
        return "done", []
    if lowered in {"intake cancel", "cancel", "取消"}:
        return "cancel", []

    resolutions: list[IntakeGapResolution] = []
    saw_done = False
    for line in stripped.splitlines():
        line = line.strip()
        if not line:
            continue
        line_lower = line.lower()
        if line_lower in {"intake done", "done", "完成"}:
            saw_done = True
            continue
        if line_lower in {"intake cancel", "cancel", "取消"}:
            return "cancel", []

        match = _GENERATE_RE.match(line)
        if match:
            gap_id = _normalize_gap_id(match.group(1))
            resolutions.append(
                IntakeGapResolution(
                    gap_id=gap_id,
                    choice="system_generate",
                    resolved_at=datetime.now(timezone.utc),
                )
            )
            continue
        match = _SUPPLEMENT_RE.match(line)
        if match:
            gap_id = _normalize_gap_id(match.group(1))
            supplement = match.group(2).strip()
            resolutions.append(
                IntakeGapResolution(
                    gap_id=gap_id,
                    choice="user_supplement",
                    user_supplement=supplement,
                    resolved_at=datetime.now(timezone.utc),
                )
            )

    if saw_done:
        return "done", resolutions
    if resolutions:
        return "partial", resolutions
    return "unknown", []


def _normalize_gap_id(raw: str) -> str:
    token = raw.strip().lower()
    if token.startswith("gap_"):
        return token
    return f"gap_{int(token)}"


def merge_clarification_resolutions(
    document: IntakeClarificationDocument,
    new_resolutions: list[IntakeGapResolution],
) -> IntakeClarificationDocument:
    by_id = {item.gap_id: item for item in document.resolutions}
    for resolution in new_resolutions:
        by_id[resolution.gap_id] = resolution
    merged = list(by_id.values())
    still_open = [
        gap.gap_id
        for gap in document.gaps
        if gap.gap_id not in by_id or by_id[gap.gap_id].choice == "pending"
    ]
    status = document.status
    resolved_at = document.resolved_at
    if not still_open and status == "pending":
        status = "resolved"
        resolved_at = datetime.now(timezone.utc)
    return document.model_copy(
        update={
            "resolutions": merged,
            "status": status,
            "resolved_at": resolved_at,
        }
    )


def _infer_character_ids(payload: GatewayPayload) -> list[str]:
    blob = " ".join(
        part
        for part in (
            payload.raw_prompt,
            payload.user_script_text or "",
        )
        if part
    ).lower()
    if "coffeefee" in blob:
        return ["coffeefee"]
    return []


def apply_intake_resolutions(
    payload: GatewayPayload,
    gaps: list[IntakeGap],
    resolutions: list[IntakeGapResolution],
) -> GatewayPayload:
    by_id = {gap.gap_id: gap for gap in gaps}
    updates: dict[str, object] = {}

    character_ids = list(payload.character_ids)
    style_preset = payload.style_preset
    style_notes = payload.style_notes
    target_duration = payload.target_duration_sec
    user_script_text = payload.user_script_text
    raw_prompt = payload.raw_prompt

    for resolution in resolutions:
        gap = by_id.get(resolution.gap_id)
        if gap is None:
            continue
        if resolution.choice == "pending":
            continue

        if resolution.choice == "user_supplement":
            text = (resolution.user_supplement or "").strip()
            if gap.kind == "style" and text:
                style_notes = text if not style_notes else f"{style_notes}; {text}"
            elif gap.kind == "duration" and text:
                try:
                    target_duration = float(text.rstrip("sS秒 "))
                except ValueError:
                    target_duration = payload.target_duration_sec or 30.0
            elif gap.kind == "character_ids" and text:
                character_ids = [
                    part.strip() for part in text.split(",") if part.strip()
                ]
            elif gap.kind == "script" and text:
                if payload.has_script:
                    user_script_text = text
                else:
                    raw_prompt = text
            continue

        # system_generate
        if gap.kind == "character_reference":
            # Downstream Character Agent will generate turnaround without user ref.
            pass
        elif gap.kind == "character_ids":
            inferred = _infer_character_ids(payload)
            if inferred:
                character_ids = inferred
        elif gap.kind == "style":
            if not style_notes and raw_prompt.strip():
                style_notes = f"Inferred from request: {raw_prompt.strip()[:200]}"
            elif not style_notes:
                style_notes = "Cinematic short-form vertical video"
        elif gap.kind == "duration":
            target_duration = 30.0
        elif gap.kind == "script" and not raw_prompt.strip() and not user_script_text:
            raw_prompt = "Auto-generated placeholder brief; refine in script stage."

    updates["character_ids"] = character_ids
    updates["style_preset"] = style_preset
    updates["style_notes"] = style_notes
    updates["target_duration_sec"] = target_duration
    updates["user_script_text"] = user_script_text
    updates["raw_prompt"] = raw_prompt
    return payload.model_copy(update=updates)


def auto_resolve_all_gaps(
    payload: GatewayPayload,
    gaps: list[IntakeGap],
) -> GatewayPayload:
    resolutions = [
        IntakeGapResolution(
            gap_id=gap.gap_id,
            choice="system_generate",
            resolved_at=datetime.now(timezone.utc),
        )
        for gap in gaps
    ]
    return apply_intake_resolutions(payload, gaps, resolutions)


def clarification_is_complete(document: IntakeClarificationDocument) -> bool:
    resolved = {
        item.gap_id: item.choice
        for item in document.resolutions
        if item.choice != "pending"
    }
    for gap in document.gaps:
        if gap.required and gap.gap_id not in resolved:
            return False
    return True
