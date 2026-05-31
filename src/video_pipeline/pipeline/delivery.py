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

from video_pipeline.schemas import GatewayPayload, JobState, RoutingPlan
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
