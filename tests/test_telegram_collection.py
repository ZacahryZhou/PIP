"""Telegram collection session tests."""

from video_pipeline.telegram_collection import (
    CollectionStep,
    advance_collection,
    build_gateway_payload,
    parse_character_ids,
    parse_yes_no,
    start_collection,
)


def test_collection_quick_skip_path() -> None:
    session = start_collection("chat-1")
    session, err = advance_collection(session, "cyberpunk chase")
    assert err is None and session.step == CollectionStep.HAS_SCRIPT

    session, err = advance_collection(session, "no")
    assert err is None and session.step == CollectionStep.STYLE

    session, err = advance_collection(session, "skip")
    assert err is None and session.step == CollectionStep.CHARACTERS

    session, err = advance_collection(session, "hero, drone_guard")
    assert err is None and session.step == CollectionStep.SCENE_REF

    done, err = advance_collection(session, "skip")
    assert err is None and done is None

    payload = build_gateway_payload(session)
    assert payload.raw_prompt == "cyberpunk chase"
    assert payload.character_ids == ["hero", "drone_guard"]


def test_parse_helpers() -> None:
    assert parse_yes_no("yes") is True
    assert parse_yes_no("skip") is False
    assert parse_character_ids("a, b") == ["a", "b"]
    assert parse_character_ids("skip") == []
