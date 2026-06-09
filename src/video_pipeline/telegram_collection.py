"""Telegram gateway collection and revision session state."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from tempfile import gettempdir

from video_pipeline.schemas import GatewayPayload

_SKIP_WORDS = frozenset({"skip", "no", "n", "-", "none"})


class CollectionStep(str, Enum):
    PROMPT = "prompt"
    HAS_SCRIPT = "has_script"
    SCRIPT_TEXT = "script_text"
    STYLE = "style"
    CHARACTERS = "characters"
    SCENE_REF = "scene_ref"
    DONE = "done"


@dataclass
class CollectionSession:
    chat_id: str
    step: CollectionStep = CollectionStep.PROMPT
    raw_prompt: str = ""
    has_script: bool = False
    user_script_text: str | None = None
    style_preset: str | None = None
    style_notes: str | None = None
    character_ids: list[str] = field(default_factory=list)
    staged_scene_refs: list[Path] = field(default_factory=list)
    staged_character_refs: list[Path] = field(default_factory=list)

    @property
    def staging_dir(self) -> Path:
        path = Path(gettempdir()) / "pip-telegram-staging" / self.chat_id
        path.mkdir(parents=True, exist_ok=True)
        return path


@dataclass(frozen=True)
class RevisionSession:
    job_id: str
    preview_version: int


def is_skip(text: str) -> bool:
    return text.strip().lower() in _SKIP_WORDS


def parse_yes_no(text: str) -> bool | None:
    normalized = text.strip().lower()
    if normalized in {"yes", "y", "yeah", "有", "是"}:
        return True
    if normalized in _SKIP_WORDS or normalized in {"no", "n", "没有", "否"}:
        return False
    return None


def parse_character_ids(text: str) -> list[str]:
    if is_skip(text):
        return []
    return [part.strip() for part in text.split(",") if part.strip()]


def start_collection(chat_id: str) -> CollectionSession:
    session = CollectionSession(chat_id=chat_id)
    _sessions[chat_id] = session
    return session


def get_collection(chat_id: str) -> CollectionSession | None:
    return _sessions.get(chat_id)


def clear_collection(chat_id: str) -> None:
    _sessions.pop(chat_id, None)


def set_revision(chat_id: str, job_id: str, preview_version: int) -> None:
    _revision_sessions[chat_id] = RevisionSession(job_id=job_id, preview_version=preview_version)


def get_revision(chat_id: str) -> RevisionSession | None:
    return _revision_sessions.get(chat_id)


def clear_revision(chat_id: str) -> None:
    _revision_sessions.pop(chat_id, None)


def prompt_for_step(session: CollectionSession) -> str:
    if session.step == CollectionStep.PROMPT:
        return "Send your video idea (one short prompt)."
    if session.step == CollectionStep.HAS_SCRIPT:
        return "Do you already have a script? Reply yes / no / skip."
    if session.step == CollectionStep.SCRIPT_TEXT:
        return "Paste your script text (or send skip to continue without one)."
    if session.step == CollectionStep.STYLE:
        return "Any style preset or notes? (e.g. cinematic cyberpunk) — or send skip."
    if session.step == CollectionStep.CHARACTERS:
        return "Character IDs from CHARACTERS.md, comma-separated — or send skip."
    if session.step == CollectionStep.SCENE_REF:
        return "Send a scene reference photo, or send skip."
    return ""


def advance_collection(session: CollectionSession, text: str) -> tuple[CollectionSession | None, str | None]:
    """Apply user text to the current step. Returns (session, error). None session means done."""
    stripped = text.strip()
    if not stripped and session.step != CollectionStep.SCENE_REF:
        return session, "Please send a non-empty reply or skip."

    if session.step == CollectionStep.PROMPT:
        session.raw_prompt = stripped
        session.step = CollectionStep.HAS_SCRIPT
        return session, None

    if session.step == CollectionStep.HAS_SCRIPT:
        choice = parse_yes_no(stripped)
        if choice is None:
            return session, "Reply yes, no, or skip."
        session.has_script = choice
        session.step = CollectionStep.SCRIPT_TEXT if choice else CollectionStep.STYLE
        return session, None

    if session.step == CollectionStep.SCRIPT_TEXT:
        if is_skip(stripped):
            session.has_script = False
            session.user_script_text = None
        else:
            session.user_script_text = stripped
        session.step = CollectionStep.STYLE
        return session, None

    if session.step == CollectionStep.STYLE:
        if not is_skip(stripped):
            session.style_notes = stripped
            if " " not in stripped and len(stripped) <= 32:
                session.style_preset = stripped
        session.step = CollectionStep.CHARACTERS
        return session, None

    if session.step == CollectionStep.CHARACTERS:
        session.character_ids = parse_character_ids(stripped)
        session.step = CollectionStep.SCENE_REF
        return session, None

    if session.step == CollectionStep.SCENE_REF:
        if is_skip(stripped):
            session.step = CollectionStep.DONE
            return None, None
        return session, "Send a photo for the scene reference, or type skip."

    return session, "Collection already finished."


def stage_collection_image(session: CollectionSession, dest: Path) -> CollectionSession:
    session.staged_scene_refs.append(dest)
    session.step = CollectionStep.DONE
    return session


def build_gateway_payload(session: CollectionSession) -> GatewayPayload:
    return GatewayPayload(
        raw_prompt=session.raw_prompt,
        channel="telegram",
        user_id=session.chat_id,
        timestamp=datetime.now(timezone.utc),
        has_script=session.has_script,
        user_script_text=session.user_script_text,
        character_ids=list(session.character_ids),
        style_preset=session.style_preset,
        style_notes=session.style_notes,
    )


def collection_asset_paths(session: CollectionSession) -> tuple[list[Path], list[Path]]:
    return list(session.staged_scene_refs), list(session.staged_character_refs)


_sessions: dict[str, CollectionSession] = {}
_revision_sessions: dict[str, RevisionSession] = {}
_intake_sessions: dict[str, str] = {}


def set_intake_job(chat_id: str, job_id: str) -> None:
    _intake_sessions[chat_id] = job_id


def get_intake_job(chat_id: str) -> str | None:
    return _intake_sessions.get(chat_id)


def clear_intake_job(chat_id: str) -> None:
    _intake_sessions.pop(chat_id, None)
