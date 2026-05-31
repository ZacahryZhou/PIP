"""Tests for Telegram delivery helpers."""

import json
from pathlib import Path

import aiohttp
import pytest
from aioresponses import aioresponses

from video_pipeline.pipeline.delivery import (
    build_delivery_summary,
    deliver_telegram_video,
    send_telegram_message,
    send_telegram_video,
)
from video_pipeline.schemas import GatewayPayload


@pytest.mark.asyncio
async def test_send_telegram_message(tmp_path: Path) -> None:
    with aioresponses() as mocked:
        mocked.post(
            "https://api.telegram.org/bottest-token/sendMessage",
            payload={"ok": True, "result": {"message_id": 42}},
        )
        async with aiohttp.ClientSession() as session:
            message_id = await send_telegram_message(
                session,
                token="test-token",
                chat_id="123456",
                text="hello",
            )
    assert message_id == 42


@pytest.mark.asyncio
async def test_send_telegram_video(tmp_path: Path) -> None:
    video_path = tmp_path / "final.mp4"
    video_path.write_bytes(b"fake-video")

    with aioresponses() as mocked:
        mocked.post(
            "https://api.telegram.org/bottest-token/sendVideo",
            payload={"ok": True, "result": {"message_id": 99}},
        )
        async with aiohttp.ClientSession() as session:
            message_id = await send_telegram_video(
                session,
                token="test-token",
                chat_id="123456",
                video_path=video_path,
                caption="done",
            )
    assert message_id == 99


@pytest.mark.asyncio
async def test_deliver_telegram_video_writes_report(tmp_path: Path) -> None:
    job_root = tmp_path / "job_test"
    reports_dir = job_root / "reports"
    final_dir = job_root / "final"
    routing_dir = job_root / "routing"
    reports_dir.mkdir(parents=True)
    final_dir.mkdir(parents=True)
    routing_dir.mkdir(parents=True)

    final_path = final_dir / "final.mp4"
    final_path.write_bytes(b"fake-video")
    routing_dir.joinpath("routing.json").write_text(
        (Path(__file__).parent / "fixtures" / "routing.json").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    job_root.joinpath("job_state.json").write_text(
        json.dumps(
            {
                "job_id": "job_test",
                "status": "delivered",
                "updated_at": "2026-05-30T00:00:00+00:00",
                "current_stage": "delivered",
                "artifact_paths": {},
            }
        ),
        encoding="utf-8",
    )

    from video_pipeline.storage import JobPaths

    job = JobPaths(job_id="job_test", root=job_root)
    payload = GatewayPayload.model_validate(
        {
            "raw_prompt": "test",
            "channel": "telegram",
            "user_id": "123456",
            "timestamp": "2026-05-30T00:00:00+00:00",
        }
    )

    with aioresponses() as mocked:
        mocked.post(
            "https://api.telegram.org/bottest-token/sendVideo",
            payload={"ok": True, "result": {"message_id": 7}},
        )
        async with aiohttp.ClientSession() as session:
            result = await deliver_telegram_video(
                session,
                token="test-token",
                job=job,
                payload=payload,
                final_path=final_path,
            )

    assert result.status == "sent"
    assert result.telegram_message_id == 7
    report = json.loads((reports_dir / "delivery_report.json").read_text(encoding="utf-8"))
    assert report["status"] == "sent"


def test_build_delivery_summary(tmp_path: Path) -> None:
    fixtures = Path(__file__).parent / "fixtures"
    job_root = tmp_path / "job_test"
    routing_dir = job_root / "routing"
    routing_dir.mkdir(parents=True)
    routing_dir.joinpath("routing.json").write_text(
        fixtures.joinpath("routing.json").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    job_root.joinpath("job_state.json").write_text(
        json.dumps(
            {
                "job_id": "job_test",
                "status": "delivered",
                "updated_at": "2026-05-30T00:00:00+00:00",
                "current_stage": "delivered",
                "artifact_paths": {},
            }
        ),
        encoding="utf-8",
    )

    from video_pipeline.storage import JobPaths

    job = JobPaths(job_id="job_test", root=job_root)
    summary = build_delivery_summary(job)
    assert "job_test" in summary
    assert "$" in summary
