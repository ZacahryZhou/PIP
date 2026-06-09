"""Telegram bot — receive prompt, preview storyboard, approve, deliver final.mp4."""

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
from video_pipeline.gateway_assets import (
    GatewayAssetBundle,
    ImageValidationError,
    StagedAsset,
    validate_image_bytes,
)
from video_pipeline.orchestrator import PipelineOrchestrator
from video_pipeline.pipeline.approval import load_approval_document, load_preview_document
from video_pipeline.pipeline.intake import load_intake_clarification
from video_pipeline.pipeline.delivery import (
    answer_telegram_callback,
    create_telegram_http_session,
    deliver_storyboard_previews,
    deliver_telegram_video,
    download_telegram_file,
    parse_preview_callback,
    prepare_telegram_bot,
    send_telegram_message,
    telegram_get_file,
    telegram_get_updates,
)
from video_pipeline.schemas import GatewayPayload, ScriptPlan, ShotsDocument
from video_pipeline.telegram_collection import (
    CollectionStep,
    advance_collection,
    build_gateway_payload as build_collected_payload,
    clear_collection,
    clear_intake_job,
    clear_revision,
    collection_asset_paths,
    get_collection,
    get_intake_job,
    get_revision,
    prompt_for_step,
    set_intake_job,
    set_revision,
    stage_collection_image,
    start_collection,
)

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


def _asset_bundle_from_collection(session) -> GatewayAssetBundle | None:
    scene_paths, char_paths = collection_asset_paths(session)
    staged: list[StagedAsset] = []
    for index, source in enumerate(scene_paths):
        staged.append(
            StagedAsset(kind="scene", ref_id=f"scene_{index + 1:03d}", source_path=source)
        )
    for index, source in enumerate(char_paths):
        staged.append(
            StagedAsset(kind="character", ref_id=f"char_{index + 1}", source_path=source)
        )
    if not staged:
        return None
    return GatewayAssetBundle(staged=tuple(staged))


def run_pipeline_for_payload(
    payload_path: Path,
    *,
    app_settings: Settings,
    mock: bool,
    asset_bundle: GatewayAssetBundle | None = None,
):
    return PipelineOrchestrator(app_settings).run(
        payload_path,
        mock=mock,
        require_approval=True,
        asset_bundle=asset_bundle,
    )


def continue_pipeline_job(
    job,
    *,
    app_settings: Settings,
    mock: bool,
):
    return PipelineOrchestrator(app_settings).continue_after_approval(job, mock=mock)


def revise_pipeline_job(
    job,
    revision_notes: str,
    *,
    app_settings: Settings,
    mock: bool,
):
    return PipelineOrchestrator(app_settings).revise_storyboard(
        job,
        revision_notes,
        mock=mock,
    )


async def deliver_intake_clarification_if_waiting(
    session,
    *,
    token: str,
    chat_id: str,
    job,
) -> bool:
    state = json.loads(job.job_state_path.read_text(encoding="utf-8"))
    if state.get("status") != "awaiting_intake_clarification":
        return False
    document = load_intake_clarification(job)
    if document is None:
        return False
    set_intake_job(chat_id, job.job_id)
    await send_telegram_message(
        session,
        token=token,
        chat_id=chat_id,
        text=document.user_message,
    )
    return True


async def handle_intake_clarification_message(
    session,
    *,
    token: str,
    chat_id: str,
    text: str,
    app_settings: Settings,
    mock: bool,
) -> bool:
    job_id = get_intake_job(chat_id)
    if job_id is None:
        return False

    orchestrator = PipelineOrchestrator(app_settings)
    try:
        job = orchestrator.resolve_job(job_id)
    except FileNotFoundError:
        clear_intake_job(chat_id)
        await send_telegram_message(
            session,
            token=token,
            chat_id=chat_id,
            text="Intake session expired — job not found. Send a new prompt to start over.",
        )
        return True

    state = json.loads(job.job_state_path.read_text(encoding="utf-8"))
    if state.get("status") != "awaiting_intake_clarification":
        clear_intake_job(chat_id)
        return False

    try:
        job = await asyncio.to_thread(
            orchestrator.resolve_intake_clarification,
            job,
            text,
            mock=mock,
            require_approval=True,
        )
    except ValueError as exc:
        await send_telegram_message(
            session, token=token, chat_id=chat_id, text=str(exc)
        )
        return True

    state = json.loads(job.job_state_path.read_text(encoding="utf-8"))
    if state.get("status") == "awaiting_intake_clarification":
        document = load_intake_clarification(job)
        if document is not None:
            await send_telegram_message(
                session,
                token=token,
                chat_id=chat_id,
                text=(
                    "已记录你的选择。仍需处理的项目：\n\n"
                    + document.user_message
                ),
            )
        return True

    clear_intake_job(chat_id)
    payload = GatewayPayload.model_validate_json(
        job.gateway_payload_path.read_text(encoding="utf-8")
    )

    if await deliver_preview_if_waiting(
        session, token=token, chat_id=chat_id, job=job, payload=payload
    ):
        return True

    if state.get("status") == "cancelled_user":
        await send_telegram_message(
            session, token=token, chat_id=chat_id, text="任务已取消。"
        )
        return True

    if state.get("status") != "delivered":
        error = state.get("error_message") or state.get("status")
        await send_telegram_message(
            session,
            token=token,
            chat_id=chat_id,
            text=f"Video generation failed: {error}",
        )
        return True

    final_path = job.final_dir / "final.mp4"
    await deliver_telegram_video(
        session,
        token=token,
        job=job,
        payload=payload,
        final_path=final_path,
    )
    return True


async def deliver_preview_if_waiting(
    session,
    *,
    token: str,
    chat_id: str,
    job,
    payload: GatewayPayload,
) -> bool:
    state = json.loads(job.job_state_path.read_text(encoding="utf-8"))
    if state.get("status") != "awaiting_storyboard_approval":
        return False
    preview = load_preview_document(job)
    shots = ShotsDocument.model_validate_json(job.shots_path.read_text(encoding="utf-8"))
    script = ScriptPlan.model_validate_json(job.script_path.read_text(encoding="utf-8"))
    await deliver_storyboard_previews(
        session,
        token=token,
        job=job,
        payload=payload,
        preview=preview,
        shots=shots,
        script=script,
    )
    return True


async def start_pipeline_from_payload(
    session,
    *,
    token: str,
    chat_id: str,
    payload: GatewayPayload,
    app_settings: Settings,
    mock: bool,
    asset_bundle: GatewayAssetBundle | None = None,
    busy_message: str = "Generating storyboard preview. This may take a few minutes…",
) -> None:
    await send_telegram_message(session, token=token, chat_id=chat_id, text=busy_message)
    payload_path = _write_payload_file(payload)
    try:
        job = await asyncio.to_thread(
            run_pipeline_for_payload,
            payload_path,
            app_settings=app_settings,
            mock=mock,
            asset_bundle=asset_bundle,
        )
    finally:
        payload_path.unlink(missing_ok=True)

    if await deliver_intake_clarification_if_waiting(
        session, token=token, chat_id=chat_id, job=job
    ):
        return

    if await deliver_preview_if_waiting(
        session, token=token, chat_id=chat_id, job=job, payload=payload
    ):
        return

    state = json.loads(job.job_state_path.read_text(encoding="utf-8"))
    if state.get("status") != "delivered":
        error = state.get("error_message") or state.get("status")
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


def extract_telegram_file_id(message: dict) -> str | None:
    photos = message.get("photo")
    if photos:
        return str(photos[-1]["file_id"])
    document = message.get("document")
    if document and str(document.get("mime_type", "")).startswith("image/"):
        return str(document["file_id"])
    return None


async def download_message_image(
    session,
    *,
    token: str,
    message: dict,
    dest: Path,
) -> Path:
    file_id = extract_telegram_file_id(message)
    if not file_id:
        raise ImageValidationError("No image found in this message.")
    file_info = await telegram_get_file(session, token=token, file_id=file_id)
    remote_path = str(file_info["file_path"])
    raw_dest = dest.with_suffix(".upload")
    await download_telegram_file(session, token=token, file_path=remote_path, dest=raw_dest)
    data = raw_dest.read_bytes()
    suffix = validate_image_bytes(data)
    final_dest = dest.with_suffix(suffix)
    final_dest.write_bytes(data)
    raw_dest.unlink(missing_ok=True)
    return final_dest


async def handle_revision_notes(
    session,
    *,
    token: str,
    chat_id: str,
    text: str,
    revision,
    app_settings: Settings,
    mock: bool,
) -> None:
    orchestrator = PipelineOrchestrator(app_settings)
    try:
        job = orchestrator.resolve_job(revision.job_id)
    except FileNotFoundError:
        clear_revision(chat_id)
        await send_telegram_message(
            session, token=token, chat_id=chat_id, text="Revision job not found."
        )
        return

    try:
        job = await asyncio.to_thread(
            revise_pipeline_job,
            job,
            text.strip(),
            app_settings=app_settings,
            mock=mock,
        )
    except ValueError as exc:
        await send_telegram_message(session, token=token, chat_id=chat_id, text=str(exc))
        return
    finally:
        clear_revision(chat_id)

    payload = GatewayPayload.model_validate_json(
        job.gateway_payload_path.read_text(encoding="utf-8")
    )
    await deliver_preview_if_waiting(
        session, token=token, chat_id=chat_id, job=job, payload=payload
    )


async def handle_collection_message(
    session,
    *,
    token: str,
    chat_id: str,
    text: str,
    app_settings: Settings,
    mock: bool,
) -> bool:
    """Return True if message was consumed by an active collection session."""
    collection = get_collection(chat_id)
    if collection is None:
        return False

    updated, error = advance_collection(collection, text)
    if error:
        await send_telegram_message(session, token=token, chat_id=chat_id, text=error)
        return True

    if updated is not None:
        await send_telegram_message(
            session, token=token, chat_id=chat_id, text=prompt_for_step(updated)
        )
        return True

    payload = build_collected_payload(collection)
    asset_bundle = _asset_bundle_from_collection(collection)
    clear_collection(chat_id)
    await start_pipeline_from_payload(
        session,
        token=token,
        chat_id=chat_id,
        payload=payload,
        app_settings=app_settings,
        mock=mock,
        asset_bundle=asset_bundle,
    )
    return True


async def handle_collection_photo(
    session,
    *,
    token: str,
    chat_id: str,
    message: dict,
    app_settings: Settings,
    mock: bool,
) -> bool:
    collection = get_collection(chat_id)
    if collection is None or collection.step != CollectionStep.SCENE_REF:
        return False

    try:
        dest = collection.staging_dir / "scene_ref_pending"
        saved = await download_message_image(
            session, token=token, message=message, dest=dest
        )
        stage_collection_image(collection, saved)
    except (ImageValidationError, RuntimeError) as exc:
        await send_telegram_message(
            session,
            token=token,
            chat_id=chat_id,
            text=f"Image rejected: {exc}\nSend another photo or type skip.",
        )
        return True

    payload = build_collected_payload(collection)
    asset_bundle = _asset_bundle_from_collection(collection)
    clear_collection(chat_id)
    await start_pipeline_from_payload(
        session,
        token=token,
        chat_id=chat_id,
        payload=payload,
        app_settings=app_settings,
        mock=mock,
        asset_bundle=asset_bundle,
    )
    return True


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
                "Quick path: send a short prompt.\n"
                "Rich path: /new — optional script, style, characters, scene photo.\n"
                "Flow: storyboard preview → approve → final.mp4 with voice, music, subtitles."
            ),
        )
        return

    if stripped.startswith("/new"):
        clear_collection(chat_id)
        start_collection(chat_id)
        await send_telegram_message(
            session,
            token=token,
            chat_id=chat_id,
            text=(
                "Rich collection started.\n"
                f"{prompt_for_step(get_collection(chat_id))}"
            ),
        )
        return

    if stripped.startswith("/"):
        await send_telegram_message(
            session,
            token=token,
            chat_id=chat_id,
            text="Unknown command. Send a prompt, or /new for rich collection.",
        )
        return

    revision = get_revision(chat_id)
    if revision is not None:
        await handle_revision_notes(
            session,
            token=token,
            chat_id=chat_id,
            text=stripped,
            revision=revision,
            app_settings=app_settings,
            mock=mock,
        )
        return

    if await handle_intake_clarification_message(
        session,
        token=token,
        chat_id=chat_id,
        text=stripped,
        app_settings=app_settings,
        mock=mock,
    ):
        return

    if await handle_collection_message(
        session,
        token=token,
        chat_id=chat_id,
        text=stripped,
        app_settings=app_settings,
        mock=mock,
    ):
        return

    payload = build_gateway_payload(stripped, chat_id=chat_id)
    await start_pipeline_from_payload(
        session,
        token=token,
        chat_id=chat_id,
        payload=payload,
        app_settings=app_settings,
        mock=mock,
    )


async def handle_callback_query(
    session,
    *,
    token: str,
    callback_query: dict,
    app_settings: Settings,
    mock: bool,
) -> None:
    callback_id = str(callback_query.get("id", ""))
    data = callback_query.get("data")
    message = callback_query.get("message") or {}
    chat = message.get("chat") or {}
    chat_id = str(chat.get("id", ""))

    if not callback_id or not data or not chat_id:
        return

    parsed = parse_preview_callback(str(data))
    if parsed is None:
        await answer_telegram_callback(session, token=token, callback_query_id=callback_id)
        return

    action, job_id, preview_version = parsed
    orchestrator = PipelineOrchestrator(app_settings)

    try:
        job = orchestrator.resolve_job(job_id)
    except FileNotFoundError:
        await answer_telegram_callback(
            session,
            token=token,
            callback_query_id=callback_id,
            text="Job not found.",
        )
        return

    state = json.loads(job.job_state_path.read_text(encoding="utf-8"))
    if state.get("status") != "awaiting_storyboard_approval":
        await answer_telegram_callback(
            session,
            token=token,
            callback_query_id=callback_id,
            text=f"Job is no longer waiting for approval ({state.get('status')}).",
        )
        return

    try:
        current_preview = load_preview_document(job)
    except FileNotFoundError:
        await answer_telegram_callback(
            session,
            token=token,
            callback_query_id=callback_id,
            text="Preview not found.",
        )
        return
    if preview_version != current_preview.preview_version:
        await answer_telegram_callback(
            session,
            token=token,
            callback_query_id=callback_id,
            text=f"Outdated preview (v{preview_version}). Use the latest preview message.",
        )
        return

    if action == "cancel":
        orchestrator.cancel_job(job, preview_version=preview_version)
        clear_revision(chat_id)
        await answer_telegram_callback(
            session, token=token, callback_query_id=callback_id, text="Cancelled."
        )
        await send_telegram_message(
            session,
            token=token,
            chat_id=chat_id,
            text=f"Job {job_id} cancelled. Send a new prompt to start again.",
        )
        return

    if action == "revise":
        existing = load_approval_document(job)
        if existing and existing.revision_count >= app_settings.max_storyboard_revisions:
            await answer_telegram_callback(
                session,
                token=token,
                callback_query_id=callback_id,
                text="Revision limit reached.",
            )
            await send_telegram_message(
                session,
                token=token,
                chat_id=chat_id,
                text=(
                    f"Maximum revisions ({app_settings.max_storyboard_revisions}) reached. "
                    "Approve, cancel, or send a new prompt to start fresh."
                ),
            )
            return

        orchestrator.request_revision(job, preview_version=preview_version)
        set_revision(chat_id, job_id, preview_version)
        await answer_telegram_callback(
            session, token=token, callback_query_id=callback_id, text="Revision noted."
        )
        await send_telegram_message(
            session,
            token=token,
            chat_id=chat_id,
            text="What should change? Send revision notes in your next message.",
        )
        return

    orchestrator.approve_job(job, preview_version=preview_version)
    clear_revision(chat_id)
    await answer_telegram_callback(
        session, token=token, callback_query_id=callback_id, text="Approved."
    )
    await send_telegram_message(
        session,
        token=token,
        chat_id=chat_id,
        text="Storyboard approved. Generating your video — this may take several minutes…",
    )

    payload = GatewayPayload.model_validate_json(
        job.gateway_payload_path.read_text(encoding="utf-8")
    )
    job = await asyncio.to_thread(
        continue_pipeline_job,
        job,
        app_settings=app_settings,
        mock=mock,
    )

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

                callback_query = update.get("callback_query")
                if callback_query:
                    try:
                        await handle_callback_query(
                            session,
                            token=token,
                            callback_query=callback_query,
                            app_settings=app_settings,
                            mock=mock,
                        )
                    except Exception as exc:  # noqa: BLE001
                        callback_id = str(callback_query.get("id", ""))
                        if callback_id:
                            await answer_telegram_callback(
                                session,
                                token=token,
                                callback_query_id=callback_id,
                                text="Something went wrong.",
                            )
                        chat = (callback_query.get("message") or {}).get("chat") or {}
                        chat_id = str(chat.get("id", ""))
                        if chat_id:
                            await send_telegram_message(
                                session,
                                token=token,
                                chat_id=chat_id,
                                text=f"Unexpected error: {exc}",
                            )
                    continue

                message = update.get("message") or update.get("edited_message")
                if not message:
                    continue
                chat = message.get("chat") or {}
                chat_id = str(chat.get("id", ""))
                if not chat_id:
                    continue

                if message.get("photo") or (
                    message.get("document")
                    and str((message.get("document") or {}).get("mime_type", "")).startswith(
                        "image/"
                    )
                ):
                    try:
                        handled = await handle_collection_photo(
                            session,
                            token=token,
                            chat_id=chat_id,
                            message=message,
                            app_settings=app_settings,
                            mock=mock,
                        )
                        if not handled:
                            await send_telegram_message(
                                session,
                                token=token,
                                chat_id=chat_id,
                                text="Send /new first if you want to upload a scene reference.",
                            )
                    except Exception as exc:  # noqa: BLE001
                        await send_telegram_message(
                            session,
                            token=token,
                            chat_id=chat_id,
                            text=f"Unexpected error: {exc}",
                        )
                    continue

                text = message.get("text")
                if not text:
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
