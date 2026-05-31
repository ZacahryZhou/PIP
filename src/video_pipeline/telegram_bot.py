"""Telegram bot — receive prompt, run pipeline, send final.mp4."""

from __future__ import annotations

import argparse
import asyncio
import fcntl
import json
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from video_pipeline.config import Settings, settings
from video_pipeline.orchestrator import PipelineOrchestrator
from video_pipeline.pipeline.delivery import (
    create_telegram_http_session,
    deliver_telegram_video,
    prepare_telegram_bot,
    send_telegram_message,
    telegram_get_updates,
)
from video_pipeline.schemas import GatewayPayload

_LOCK_PATH = Path(tempfile.gettempdir()) / "pip-telegram-bot.lock"


def build_gateway_payload(raw_prompt: str, *, chat_id: str) -> GatewayPayload:
    return GatewayPayload(
        raw_prompt=raw_prompt.strip(),
        channel="telegram",
        user_id=str(chat_id),
        timestamp=datetime.now(timezone.utc),
    )


def _write_payload_file(payload: GatewayPayload) -> Path:
    handle = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8")
    path = Path(handle.name)
    handle.write(json.dumps(payload.model_dump(mode="json"), ensure_ascii=False))
    handle.close()
    return path


def run_pipeline_for_payload(
    payload_path: Path,
    *,
    app_settings: Settings,
    mock: bool,
):
    return PipelineOrchestrator(app_settings).run(payload_path, mock=mock)


async def handle_text_message(
    session,
    *,
    token: str,
    chat_id: str,
    text: str,
    app_settings: Settings,
    mock: bool,
) -> None:
    stripped = text.strip()
    if not stripped:
        await send_telegram_message(
            session,
            token=token,
            chat_id=chat_id,
            text="Please send a non-empty video prompt.",
        )
        return

    if stripped.startswith("/start"):
        await send_telegram_message(
            session,
            token=token,
            chat_id=chat_id,
            text=(
                "PIP video bot\n"
                "Send a short prompt and I will generate a video and reply with final.mp4.\n"
                "Example: Create a 30 second cinematic cyberpunk chase in a rainy neon alley."
            ),
        )
        return

    if stripped.startswith("/"):
        await send_telegram_message(
            session,
            token=token,
            chat_id=chat_id,
            text="Unknown command. Send a plain-text prompt to generate a video.",
        )
        return

    await send_telegram_message(
        session,
        token=token,
        chat_id=chat_id,
        text="Generating your video. This may take several minutes…",
    )

    payload = build_gateway_payload(stripped, chat_id=chat_id)
    payload_path = _write_payload_file(payload)
    try:
        job = await asyncio.to_thread(
            run_pipeline_for_payload,
            payload_path,
            app_settings=app_settings,
            mock=mock,
        )
    finally:
        payload_path.unlink(missing_ok=True)

    state = json.loads(job.job_state_path.read_text(encoding="utf-8"))
    if state.get("status") != "delivered":
        error = state.get("error_message") or state.get("status", "unknown error")
        await send_telegram_message(
            session,
            token=token,
            chat_id=chat_id,
            text=f"Video generation failed: {error}",
        )
        return

    final_path = job.final_dir / "final.mp4"
    await deliver_telegram_video(
        session,
        token=token,
        job=job,
        payload=payload,
        final_path=final_path,
    )


async def poll_updates(
    *,
    token: str,
    app_settings: Settings,
    mock: bool,
) -> None:
    offset: int | None = None

    async with create_telegram_http_session() as session:
        username = await prepare_telegram_bot(session, token=token)
        print(f"PIP Telegram bot ready: @{username} (mock={mock})", flush=True)

        while True:
            payload = await telegram_get_updates(session, token=token, offset=offset)
            if not payload.get("ok"):
                error_code = payload.get("error_code")
                if error_code == 409:
                    print(
                        "Telegram 409: another poller is active. Waiting 5s… "
                        "Stop other bot terminals (Ctrl+C) if this repeats.",
                        file=sys.stderr,
                        flush=True,
                    )
                    await asyncio.sleep(5)
                    continue
                raise RuntimeError(f"Telegram getUpdates failed: {payload!r}")

            for update in payload.get("result", []):
                offset = int(update["update_id"]) + 1
                message = update.get("message") or update.get("edited_message")
                if not message:
                    continue
                chat = message.get("chat") or {}
                chat_id = str(chat.get("id", ""))
                text = message.get("text")
                if not chat_id or not text:
                    continue

                try:
                    await handle_text_message(
                        session,
                        token=token,
                        chat_id=chat_id,
                        text=text,
                        app_settings=app_settings,
                        mock=mock,
                    )
                except Exception as exc:  # noqa: BLE001 — keep bot alive after one failure
                    await send_telegram_message(
                        session,
                        token=token,
                        chat_id=chat_id,
                        text=f"Unexpected error: {exc}",
                    )


def _acquire_single_instance_lock():
    lock_file = _LOCK_PATH.open("w", encoding="utf-8")
    try:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError as exc:
        lock_file.close()
        raise RuntimeError(
            "Another PIP Telegram bot is already running on this Mac. "
            "Stop it with Ctrl+C in the other terminal, or run: "
            "pkill -f video_pipeline.telegram_bot"
        ) from exc
    lock_file.write(str(Path.cwd()))
    lock_file.flush()
    return lock_file


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="PIP Telegram bot")
    parser.add_argument(
        "--mock",
        action="store_true",
        help="Use fixture script/shots and mock media (no DeepSeek/fal calls)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    app_settings = settings
    token = app_settings.telegram_bot_token.strip()
    if not token:
        print("TELEGRAM_BOT_TOKEN is required in .env", file=sys.stderr)
        return 1

    lock_file = None
    try:
        lock_file = _acquire_single_instance_lock()
        asyncio.run(poll_updates(token=token, app_settings=app_settings, mock=args.mock))
    except KeyboardInterrupt:
        return 0
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    finally:
        if lock_file is not None:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
            lock_file.close()
            _LOCK_PATH.unlink(missing_ok=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
