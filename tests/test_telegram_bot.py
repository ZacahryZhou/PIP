"""Tests for Telegram gateway payload building."""

from datetime import datetime, timezone

from video_pipeline.telegram_bot import build_gateway_payload


def test_build_gateway_payload_from_telegram_message() -> None:
    payload = build_gateway_payload(
        "  Create a short cyberpunk chase  ",
        chat_id="987654321",
    )
    assert payload.raw_prompt == "Create a short cyberpunk chase"
    assert payload.channel == "telegram"
    assert payload.user_id == "987654321"
    assert payload.timestamp.tzinfo is not None
    assert payload.timestamp <= datetime.now(timezone.utc)
