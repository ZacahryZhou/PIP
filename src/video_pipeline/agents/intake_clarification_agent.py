"""Intake Clarification Agent — ask user to system-generate or supplement gaps."""

from __future__ import annotations

from datetime import datetime, timezone

from video_pipeline.schemas.intake import IntakeClarificationDocument, IntakeGap
from video_pipeline.storage import JobPaths, write_json


def format_intake_clarification_message(gaps: list[IntakeGap]) -> str:
    lines = [
        "PIP 入口分拣发现信息不完整，请先补齐或选择处理方式：",
        "",
    ]
    for gap in gaps:
        req = "必填" if gap.required else "可选"
        lines.append(f"{gap.gap_id}. [{gap.kind}] {gap.label}（{req}）")
        lines.append(f"   {gap.detail}")
        lines.append("   · 回复 generate <编号> — 让系统推断/生成")
        lines.append("   · 回复 supplement <编号> <内容> — 你补充文字说明")
        lines.append("   · 角色/场景图可补发图片后再回复 supplement <编号> done")
        lines.append("")

    lines.extend(
        [
            "全部选完后回复：intake done",
            "取消任务回复：intake cancel",
        ]
    )
    return "\n".join(lines)


def run_intake_clarification_agent(
    job: JobPaths,
    gaps: list[IntakeGap],
) -> IntakeClarificationDocument:
    document = IntakeClarificationDocument(
        job_id=job.job_id,
        status="pending",
        gaps=gaps,
        user_message=format_intake_clarification_message(gaps),
        created_at=datetime.now(timezone.utc),
    )
    write_json(job.intake_clarification_path, document)
    return document
