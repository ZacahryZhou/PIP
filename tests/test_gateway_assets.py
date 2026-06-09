"""Gateway asset validation and job persistence tests."""

from pathlib import Path

import pytest

from video_pipeline.gateway_assets import (
    GatewayAssetBundle,
    GatewayAssetValidationError,
    ImageValidationError,
    StagedAsset,
    apply_gateway_assets,
    require_payload_assets_on_job,
    validate_image_bytes,
    validate_payload_assets_on_job,
)
from video_pipeline.schemas import GatewayPayload
from video_pipeline.storage import create_job_paths, ensure_job_layout, resolve_storage_root
from datetime import datetime, timezone


PNG_1X1 = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
    b"\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00\x01\x01\x01\x00\x18\xdd\x8d\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
)


def test_validate_image_bytes_accepts_png() -> None:
    assert validate_image_bytes(PNG_1X1) == ".png"


def test_validate_image_bytes_rejects_garbage() -> None:
    with pytest.raises(ImageValidationError, match="Unsupported"):
        validate_image_bytes(b"not-an-image")


def test_apply_gateway_assets_copies_into_job(tmp_path: Path) -> None:
    staging = tmp_path / "staging"
    staging.mkdir()
    source = staging / "upload.png"
    source.write_bytes(PNG_1X1)

    storage_root = resolve_storage_root(str(tmp_path / "jobs"))
    job = ensure_job_layout(create_job_paths(storage_root))
    payload = GatewayPayload(
        raw_prompt="test",
        channel="telegram",
        user_id="123",
        timestamp=datetime.now(timezone.utc),
    )
    bundle = GatewayAssetBundle(
        staged=(StagedAsset(kind="scene", ref_id="scene_001", source_path=source),)
    )

    updated = apply_gateway_assets(job, payload, bundle)
    assert len(updated.scene_reference_images) == 1
    assert updated.scene_reference_images[0].scene_id == "scene_001"
    ref_path = job.root / updated.scene_reference_images[0].path
    assert ref_path.is_file()
    assert ref_path.read_bytes() == PNG_1X1


def test_validate_payload_assets_on_job_accepts_staged_character_ref(tmp_path: Path) -> None:
    storage_root = resolve_storage_root(str(tmp_path / "jobs"))
    job = ensure_job_layout(create_job_paths(storage_root))
    refs_dir = job.character_refs_dir
    refs_dir.mkdir(parents=True, exist_ok=True)
    ref_file = refs_dir / "coffeefee_ref.png"
    ref_file.write_bytes(PNG_1X1)
    rel = str(ref_file.relative_to(job.root))
    payload = GatewayPayload(
        raw_prompt="test",
        channel="telegram",
        user_id="123",
        timestamp=datetime.now(timezone.utc),
        character_reference_images=[{"character_id": "coffeefee", "path": rel}],
    )
    assert validate_payload_assets_on_job(job, payload) == []


def test_require_payload_assets_on_job_raises_when_missing(tmp_path: Path) -> None:
    storage_root = resolve_storage_root(str(tmp_path / "jobs"))
    job = ensure_job_layout(create_job_paths(storage_root))
    payload = GatewayPayload(
        raw_prompt="test",
        channel="telegram",
        user_id="123",
        timestamp=datetime.now(timezone.utc),
        character_reference_images=[
            {"character_id": "coffeefee", "path": "input/character_refs/coffeefee_ref.png"}
        ],
    )
    with pytest.raises(GatewayAssetValidationError, match="Missing character reference"):
        require_payload_assets_on_job(job, payload)
