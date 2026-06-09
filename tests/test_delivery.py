"""Tests for Telegram delivery helpers."""

import json
from pathlib import Path
from typing import Any

import pytest

from video_pipeline.pipeline.delivery import (
    build_delivery_summary,
    build_script_review_summary,
    build_shots_review_summary,
    deliver_storyboard_previews,
    deliver_telegram_video,
    send_telegram_message,
    send_telegram_video,
)
from video_pipeline.schemas import GatewayPayload, ScriptPlan, ShotsDocument, StoryboardPreviewDocument


class _MockResponse:
    def __init__(self, payload: dict[str, Any]) -> None:
        self._payload = payload

    async def json(self) -> dict[str, Any]:
        return self._payload

    async def __aenter__(self) -> "_MockResponse":
        return self

    async def __aexit__(self, *args: object) -> None:
        return None


class _MockSession:
    """Minimal aiohttp session stub — avoids aioresponses/aiohttp version drift."""

    def __init__(self, post_payload: dict[str, Any]) -> None:
        self._post_payload = post_payload
        self.post_calls: list[tuple[str, dict[str, Any]]] = []

    def post(self, url: str, **kwargs: Any) -> _MockResponse:
        self.post_calls.append((url, kwargs))
        return _MockResponse(self._post_payload)


@pytest.mark.asyncio
async def test_send_telegram_message(tmp_path: Path) -> None:
    session = _MockSession({"ok": True, "result": {"message_id": 42}})
    message_id = await send_telegram_message(
        session,  # type: ignore[arg-type]
        token="test-token",
        chat_id="123456",
        text="hello",
    )
    assert message_id == 42


@pytest.mark.asyncio
async def test_send_telegram_video(tmp_path: Path) -> None:
    video_path = tmp_path / "final.mp4"
    video_path.write_bytes(b"fake-video")

    session = _MockSession({"ok": True, "result": {"message_id": 99}})
    message_id = await send_telegram_video(
        session,  # type: ignore[arg-type]
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

    session = _MockSession({"ok": True, "result": {"message_id": 7}})
    result = await deliver_telegram_video(
        session,  # type: ignore[arg-type]
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


def test_build_script_review_summary() -> None:
    fixtures = Path(__file__).parent / "fixtures"
    script = ScriptPlan.model_validate_json(
        fixtures.joinpath("script.json").read_text(encoding="utf-8")
    )
    summary = build_script_review_summary(script)
    assert "Script summary" in summary
    assert script.narrative_arc in summary
    assert "Scenes:" in summary


def test_build_shots_review_summary() -> None:
    fixtures = Path(__file__).parent / "fixtures"
    shots = ShotsDocument.model_validate_json(
        fixtures.joinpath("shots.json").read_text(encoding="utf-8")
    )
    summary = build_shots_review_summary(shots)
    assert "Shot list" in summary
    assert shots.shots[0].shot_id in summary


@pytest.mark.asyncio
async def test_deliver_storyboard_previews_sends_summaries_and_both_frames(tmp_path: Path) -> None:
    fixtures = Path(__file__).parent / "fixtures"
    job_root = tmp_path / "job_preview"
    preview_dir = job_root / "preview"
    preview_dir.mkdir(parents=True)

    shots = ShotsDocument.model_validate_json(
        fixtures.joinpath("shots.json").read_text(encoding="utf-8")
    )
    shot = shots.shots[0]
    start_path = preview_dir / f"{shot.shot_id}_start.png"
    end_path = preview_dir / f"{shot.shot_id}_end.png"
    start_path.write_bytes(b"start")
    end_path.write_bytes(b"end")

    preview = StoryboardPreviewDocument.model_validate(
        {
            "job_id": "job_preview",
            "preview_version": 1,
            "created_at": "2026-05-30T00:00:00+00:00",
            "items": [
                {
                    "shot_id": shot.shot_id,
                    "scene_id": shot.scene_id,
                    "preview_image_path": str(start_path.relative_to(job_root)),
                    "start_image_path": str(start_path.relative_to(job_root)),
                    "end_image_path": str(end_path.relative_to(job_root)),
                    "start_prompt": "start prompt",
                    "end_prompt": "end prompt",
                    "prompt": "summary prompt",
                    "status": "ok",
                }
            ],
        }
    )

    script = ScriptPlan.model_validate_json(
        fixtures.joinpath("script.json").read_text(encoding="utf-8")
    )

    from video_pipeline.storage import JobPaths

    job = JobPaths(job_id="job_preview", root=job_root)
    payload = GatewayPayload.model_validate(
        {
            "raw_prompt": "test",
            "channel": "telegram",
            "user_id": "123456",
            "timestamp": "2026-05-30T00:00:00+00:00",
        }
    )

    session = _MockSession({"ok": True, "result": {"message_id": 1}})
    await deliver_storyboard_previews(
        session,  # type: ignore[arg-type]
        token="test-token",
        job=job,
        payload=payload,
        preview=preview,
        shots=shots,
        script=script,
    )

    message_calls = [
        call for call in session.post_calls if "sendMessage" in call[0]
    ]
    photo_calls = [call for call in session.post_calls if "sendPhoto" in call[0]]
    assert len(message_calls) >= 3
    assert len(photo_calls) == 2
    assert any("Script summary" in str(call[1].get("json", {}).get("text", "")) for call in message_calls)
    assert any("Shot list" in str(call[1].get("json", {}).get("text", "")) for call in message_calls)
