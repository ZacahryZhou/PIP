"""Select local BGM assets per MUSIC_LIBRARY.md."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class MusicCatalogEntry:
    asset_id: str
    file: str
    mood_tags: tuple[str, ...]
    bpm_min: int
    bpm_max: int


CATALOG: tuple[MusicCatalogEntry, ...] = (
    MusicCatalogEntry(
        "tense_electronic_128",
        "tense_electronic_128.mp3",
        ("tense", "electronic", "action", "chase"),
        118,
        138,
    ),
    MusicCatalogEntry(
        "calm_ambient_90",
        "calm_ambient_90.mp3",
        ("calm", "ambient", "normal", "peaceful"),
        80,
        100,
    ),
    MusicCatalogEntry(
        "dream_ethereal_72",
        "dream_ethereal_72.mp3",
        ("dream", "memory", "ethereal", "soft"),
        60,
        84,
    ),
    MusicCatalogEntry(
        "action_percussion_140",
        "action_percussion_140.mp3",
        ("action", "tense", "percussion", "run"),
        130,
        150,
    ),
    MusicCatalogEntry(
        "fallback_neutral_loop",
        "fallback_neutral_loop.mp3",
        ("any",),
        40,
        220,
    ),
)


def _mood_tokens(music_mood: str) -> set[str]:
    return {token.strip().lower() for token in music_mood.replace(",", " ").split() if token.strip()}


def select_library_track(
    music_dir: Path,
    *,
    music_mood: str,
    music_bpm: int,
) -> Path | None:
    tokens = _mood_tokens(music_mood)
    candidates: list[tuple[int, MusicCatalogEntry]] = []

    for entry in CATALOG:
        if entry.asset_id == "fallback_neutral_loop":
            continue
        tag_set = set(entry.mood_tags)
        if not tokens.intersection(tag_set):
            continue
        if not (entry.bpm_min <= music_bpm <= entry.bpm_max):
            continue
        distance = abs(music_bpm - ((entry.bpm_min + entry.bpm_max) // 2))
        candidates.append((distance, entry))

    if candidates:
        _, best = min(candidates, key=lambda item: item[0])
        path = music_dir / best.file
        if path.is_file():
            return path

    fallback = music_dir / "fallback_neutral_loop.mp3"
    if fallback.is_file():
        return fallback
    return None
