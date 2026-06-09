"""Deliver final video back to the user channel (Telegram MVP)."""

from __future__ import annotations

import json
import ssl
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import aiohttp
import certifi

from video_pipeline.schemas import GatewayPayload, JobState, RoutingPlan, ScriptPlan, ShotsDocument, StoryboardPreviewDocument
from video_pipeline.storage import JobPaths, save_job_state
from video_pipeline.storage.artifacts import write_json


def create_telegram_http_session() -> aiohttp.ClientSession:
    """Use certifi CA bundle — fixes macOS Python SSL verify failures."""
    ssl_context = ssl.create_default_context(cafile=certifi.where())
    connector = aiohttp.TCPConnector(ssl=ssl_context)
    return aiohttp.ClientSession(connector=connector)


async def prepare_telegram_bot(session: aiohttp.ClientSession, *, token: str) -> str:
    """Clear webhook and verify token before long-polling."""
    base_url = f"https://api.telegram.org/bot{token}"
    async with session.post(f"{base_url}/deleteWebhook", json={"drop_pending_updates": False}) as response:
        payload = await response.json()
        if not payload.get("ok"):
            raise RuntimeError(f"Telegram deleteWebhook failed: {payload!r}")

    async with session.get(f"{base_url}/getMe") as response:
        payload = await response.json()
        if not payload.get("ok"):
            raise RuntimeError(f"Telegram getMe failed: {payload!r}")
        username = payload["result"].get("username") or "unknown"
        return str(username)


async def telegram_get_updates(
    session: aiohttp.ClientSession,
    *,
    token: str,
    offset: int | None,
    timeout_sec: int = 30,
) -> dict[str, Any]:
    base_url = f"https://api.telegram.org/bot{token}"
    params: dict[str, str | int] = {"timeout": timeout_sec}
    if offset is not None:
        params["offset"] = offset
    async with session.get(f"{base_url}/getUpdates", params=params) as response:
        return await response.json()


async def telegram_get_file(
    session: aiohttp.ClientSession,
    *,
    token: str,
    file_id: str,
) -> dict[str, Any]:
    base_url = f"https://api.telegram.org/bot{token}"
    async with session.get(f"{base_url}/getFile", params={"file_id": file_id}) as response:
        payload = await response.json()
        if not payload.get("ok"):
            raise RuntimeError(f"Telegram getFile failed: {payload!r}")
        return payload["result"]


async def download_telegram_file(
    session: aiohttp.ClientSession,
    *,
    token: str,
    file_path: str,
    dest: Path,
) -> Path:
    url = f"https://api.telegram.org/file/bot{token}/{file_path}"
    dest.parent.mkdir(parents=True, exist_ok=True)
    async with session.get(url) as response:
        if response.status != 200:
            raise RuntimeError(f"Telegram file download failed: HTTP {response.status}")
        data = await response.read()
    dest.write_bytes(data)
    return dest


@dataclass(frozen=True)
class DeliveryResult:
    channel: str
    user_id: str
    status: str
    final_video: str
    telegram_message_id: int | None = None
    error: str | None = None


def build_delivery_summary(job: JobPaths) -> str:
    lines = [f"PIP job: {job.job_id}"]

    if job.routing_path.is_file():
        routing = RoutingPlan.model_validate_json(job.routing_path.read_text(encoding="utf-8"))
        lines.append(f"Estimated cost: ${routing.total_estimated_cost:.2f}")

    if job.job_state_path.is_file():
        state = JobState.model_validate_json(job.job_state_path.read_text(encoding="utf-8"))
        lines.append(f"Status: {state.status}")

    return "\n".join(lines)


async def send_telegram_message(
    session: aiohttp.ClientSession,
    *,
    token: str,
    chat_id: str,
    text: str,
) -> int:
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    async with session.post(url, json={"chat_id": chat_id, "text": text}) as response:
        payload = await response.json()
        if not payload.get("ok"):
            raise RuntimeError(f"Telegram sendMessage failed: {payload!r}")
        return int(payload["result"]["message_id"])


def build_preview_callback(action: str, job_id: str, preview_version: int) -> str:
    return f"pip:{action}:{job_id}:{preview_version}"


def parse_preview_callback(data: str) -> tuple[str, str, int] | None:
    parts = data.split(":")
    if len(parts) != 4 or parts[0] != "pip":
        return None
    action, job_id, version_text = parts[1], parts[2], parts[3]
    if action not in {"approve", "cancel", "revise"}:
        return None
    try:
        preview_version = int(version_text)
    except ValueError:
        return None
    return action, job_id, preview_version


async def send_telegram_photo(
    session: aiohttp.ClientSession,
    *,
    token: str,
    chat_id: str,
    image_path: Path,
    caption: str | None = None,
) -> int:
    if not image_path.is_file():
        raise FileNotFoundError(f"Preview image not found: {image_path}")

    url = f"https://api.telegram.org/bot{token}/sendPhoto"
    form = aiohttp.FormData()
    form.add_field("chat_id", chat_id)
    if caption:
        form.add_field("caption", caption)
    form.add_field(
        "photo",
        image_path.read_bytes(),
        filename=image_path.name,
        content_type="image/png",
    )

    async with session.post(url, data=form) as response:
        payload = await response.json()
        if not payload.get("ok"):
            raise RuntimeError(f"Telegram sendPhoto failed: {payload!r}")
        return int(payload["result"]["message_id"])


async def send_telegram_message_with_keyboard(
    session: aiohttp.ClientSession,
    *,
    token: str,
    chat_id: str,
    text: str,
    reply_markup: dict[str, Any],
) -> int:
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    async with session.post(
        url,
        json={"chat_id": chat_id, "text": text, "reply_markup": reply_markup},
    ) as response:
        payload = await response.json()
        if not payload.get("ok"):
            raise RuntimeError(f"Telegram sendMessage failed: {payload!r}")
        return int(payload["result"]["message_id"])


def build_preview_caption(
    *,
    shot_id: str,
    scene_id: str,
    subject: str,
    duration_sec: float,
    dialogue_text: str | None = None,
    frame: str | None = None,
) -> str:
    header = f"{shot_id} · {scene_id}"
    if frame:
        header = f"{header} · {frame}"
    lines = [
        header,
        subject,
        f"Duration: {duration_sec:g}s",
    ]
    if dialogue_text:
        lines.append(f'Dialogue: "{dialogue_text}"')
    return "\n".join(lines)


def build_script_review_summary(script: ScriptPlan) -> str:
    """Human-readable script overview for storyboard approval."""
    lines = [
        "Script summary",
        f"Arc: {script.narrative_arc}",
        f"Style: {script.visual_style} · {script.color_tone}",
        f"Duration: {script.total_duration_sec:g}s · {len(script.scene_list)} scenes",
    ]
    if script.characters_in_use:
        lines.append(f"Characters: {', '.join(script.characters_in_use)}")
    lines.append("")
    lines.append("Scenes:")
    for scene in script.scene_list:
        title = scene.scene_title or scene.location
        lines.append(
            f"- {scene.scene_id} {title} ({scene.duration_sec:g}s): {scene.action_summary}"
        )
        if scene.dialogue:
            snippet = scene.dialogue[0].text
            if len(snippet) > 80:
                snippet = snippet[:77] + "..."
            lines.append(f'  Dialogue: "{snippet}"')
    return "\n".join(lines)


def build_shots_review_summary(shots: ShotsDocument) -> str:
    """Compact shot list for storyboard approval."""
    lines = [
        f"Shot list ({len(shots.shots)} shots)",
    ]
    for shot in shots.shots:
        dialogue = shot.dialogue[0].text if shot.dialogue else None
        line = (
            f"- {shot.shot_id} · {shot.scene_id} · {shot.duration_sec:g}s · "
            f"{shot.shot_size} · {shot.subject}"
        )
        lines.append(line)
        if dialogue:
            snippet = dialogue if len(dialogue) <= 60 else dialogue[:57] + "..."
            lines.append(f'  "{snippet}"')
    return "\n".join(lines)


def _chunk_telegram_text(text: str, *, limit: int = 3900) -> list[str]:
    if len(text) <= limit:
        return [text]
    chunks: list[str] = []
    current: list[str] = []
    current_len = 0
    for line in text.splitlines():
        addition = len(line) + (1 if current else 0)
        if current and current_len + addition > limit:
            chunks.append("\n".join(current))
            current = [line]
            current_len = len(line)
        else:
            current.append(line)
            current_len += addition
    if current:
        chunks.append("\n".join(current))
    return chunks


async def deliver_storyboard_previews(
    session: aiohttp.ClientSession,
    *,
    token: str,
    job: JobPaths,
    payload: GatewayPayload,
    preview: StoryboardPreviewDocument,
    shots: ShotsDocument,
    script: ScriptPlan,
) -> None:
    chat_id = payload.user_id
    shot_by_id = {shot.shot_id: shot for shot in shots.shots}
    ok_items = [item for item in preview.items if item.status == "ok"]

    await send_telegram_message(
        session,
        token=token,
        chat_id=chat_id,
        text=(
            f"Storyboard preview for {job.job_id} (v{preview.preview_version}).\n"
            f"{len(ok_items)} shot(s) with start + end frames.\n"
            "Review the script summary, shot list, and frames below, then choose an action."
        ),
    )

    for chunk in _chunk_telegram_text(build_script_review_summary(script)):
        await send_telegram_message(
            session,
            token=token,
            chat_id=chat_id,
            text=chunk,
        )

    for chunk in _chunk_telegram_text(build_shots_review_summary(shots)):
        await send_telegram_message(
            session,
            token=token,
            chat_id=chat_id,
            text=chunk,
        )

    for item in preview.items:
        if item.status != "ok":
            continue
        shot = shot_by_id[item.shot_id]
        dialogue_text = shot.dialogue[0].text if shot.dialogue else None
        start_caption = build_preview_caption(
            shot_id=shot.shot_id,
            scene_id=shot.scene_id,
            subject=shot.subject,
            duration_sec=shot.duration_sec,
            dialogue_text=dialogue_text,
            frame="Start",
        )
        end_caption = build_preview_caption(
            shot_id=shot.shot_id,
            scene_id=shot.scene_id,
            subject=shot.subject,
            duration_sec=shot.duration_sec,
            dialogue_text=dialogue_text,
            frame="End",
        )
        start_path = job.root / item.start_image_path
        end_path = job.root / item.end_image_path
        await send_telegram_photo(
            session,
            token=token,
            chat_id=chat_id,
            image_path=start_path,
            caption=start_caption,
        )
        await send_telegram_photo(
            session,
            token=token,
            chat_id=chat_id,
            image_path=end_path,
            caption=end_caption,
        )

    keyboard = {
        "inline_keyboard": [
            [
                {
                    "text": "Approve / 通过",
                    "callback_data": build_preview_callback(
                        "approve", job.job_id, preview.preview_version
                    ),
                },
                {
                    "text": "Revise / 修改",
                    "callback_data": build_preview_callback(
                        "revise", job.job_id, preview.preview_version
                    ),
                },
                {
                    "text": "Cancel / 取消",
                    "callback_data": build_preview_callback(
                        "cancel", job.job_id, preview.preview_version
                    ),
                },
            ]
        ]
    }
    await send_telegram_message_with_keyboard(
        session,
        token=token,
        chat_id=chat_id,
        text="Approve this storyboard to start video generation?",
        reply_markup=keyboard,
    )


async def answer_telegram_callback(
    session: aiohttp.ClientSession,
    *,
    token: str,
    callback_query_id: str,
    text: str | None = None,
) -> None:
    url = f"https://api.telegram.org/bot{token}/answerCallbackQuery"
    body: dict[str, str] = {"callback_query_id": callback_query_id}
    if text:
        body["text"] = text
    async with session.post(url, json=body) as response:
        payload = await response.json()
        if not payload.get("ok"):
            raise RuntimeError(f"Telegram answerCallbackQuery failed: {payload!r}")


async def send_telegram_video(
    session: aiohttp.ClientSession,
    *,
    token: str,
    chat_id: str,
    video_path: Path,
    caption: str | None = None,
) -> int:
    if not video_path.is_file():
        raise FileNotFoundError(f"Final video not found: {video_path}")

    url = f"https://api.telegram.org/bot{token}/sendVideo"
    form = aiohttp.FormData()
    form.add_field("chat_id", chat_id)
    if caption:
        form.add_field("caption", caption)
    form.add_field(
        "video",
        video_path.read_bytes(),
        filename=video_path.name,
        content_type="video/mp4",
    )

    async with session.post(url, data=form) as response:
        payload = await response.json()
        if not payload.get("ok"):
            raise RuntimeError(f"Telegram sendVideo failed: {payload!r}")
        return int(payload["result"]["message_id"])


def save_delivery_report(job: JobPaths, result: DeliveryResult) -> Path:
    report_path = job.reports_dir / "delivery_report.json"
    write_json(
        report_path,
        {
            "channel": result.channel,
            "user_id": result.user_id,
            "status": result.status,
            "final_video": result.final_video,
            "telegram_message_id": result.telegram_message_id,
            "error": result.error,
            "delivered_at": datetime.now(timezone.utc).isoformat(),
        },
    )
    return report_path


def mark_delivery_failed(job: JobPaths, error_message: str) -> None:
    if not job.job_state_path.is_file():
        return
    state = JobState.model_validate_json(job.job_state_path.read_text(encoding="utf-8"))
    updated = state.model_copy(
        update={
            "status": "failed_delivery",
            "error_message": error_message,
            "updated_at": datetime.now(timezone.utc),
            "current_stage": "delivery",
        }
    )
    save_job_state(job.job_state_path, updated)


async def deliver_telegram_video(
    session: aiohttp.ClientSession,
    *,
    token: str,
    job: JobPaths,
    payload: GatewayPayload,
    final_path: Path,
) -> DeliveryResult:
    chat_id = payload.user_id
    summary = build_delivery_summary(job)

    try:
        message_id = await send_telegram_video(
            session,
            token=token,
            chat_id=chat_id,
            video_path=final_path,
            caption=summary,
        )
        result = DeliveryResult(
            channel="telegram",
            user_id=chat_id,
            status="sent",
            final_video=str(final_path),
            telegram_message_id=message_id,
        )
    except Exception as exc:  # noqa: BLE001 — report delivery failure on job
        result = DeliveryResult(
            channel="telegram",
            user_id=chat_id,
            status="failed",
            final_video=str(final_path),
            error=str(exc),
        )
        mark_delivery_failed(job, str(exc))

    save_delivery_report(job, result)
    return result
