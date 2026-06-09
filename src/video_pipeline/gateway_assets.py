"""Validate and persist user-uploaded gateway assets into job folders."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from video_pipeline.schemas import (
    CharacterReferenceImage,
    GatewayPayload,
    SceneReferenceImage,
)
from video_pipeline.storage import JobPaths

ALLOWED_IMAGE_SUFFIXES = frozenset({".jpg", ".jpeg", ".png", ".webp"})
MAX_IMAGE_BYTES = 10 * 1024 * 1024


class ImageValidationError(ValueError):
    """Raised when uploaded image bytes fail validation."""


class GatewayAssetValidationError(ValueError):
    """Raised when staged gateway assets are missing or invalid on the job."""


def detect_image_suffix(data: bytes) -> str | None:
    if len(data) < 12:
        return None
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return ".png"
    if data[:3] == b"\xff\xd8\xff":
        return ".jpg"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return ".webp"
    return None


def validate_image_bytes(data: bytes) -> str:
    if len(data) > MAX_IMAGE_BYTES:
        raise ImageValidationError(
            f"Image too large ({len(data)} bytes). Max is {MAX_IMAGE_BYTES // (1024 * 1024)}MB."
        )
    suffix = detect_image_suffix(data)
    if suffix is None or suffix not in ALLOWED_IMAGE_SUFFIXES:
        raise ImageValidationError(
            "Unsupported image format. Use JPG, PNG, or WEBP."
        )
    return suffix


def save_staged_image(data: bytes, dest_dir: Path, *, prefix: str) -> Path:
    dest_dir.mkdir(parents=True, exist_ok=True)
    suffix = validate_image_bytes(data)
    dest = dest_dir / f"{prefix}{suffix}"
    dest.write_bytes(data)
    return dest


@dataclass(frozen=True)
class StagedAsset:
    kind: Literal["scene", "character"]
    ref_id: str
    source_path: Path


@dataclass(frozen=True)
class GatewayAssetBundle:
    staged: tuple[StagedAsset, ...] = ()


def apply_gateway_assets(
    job: JobPaths,
    payload: GatewayPayload,
    bundle: GatewayAssetBundle,
) -> GatewayPayload:
    if not bundle.staged:
        return payload

    job.scene_refs_dir.mkdir(parents=True, exist_ok=True)
    job.character_refs_dir.mkdir(parents=True, exist_ok=True)

    scene_images: list[SceneReferenceImage] = list(payload.scene_reference_images)
    character_images: list[CharacterReferenceImage] = list(payload.character_reference_images)

    scene_index = len(scene_images)
    for asset in bundle.staged:
        data = asset.source_path.read_bytes()
        suffix = validate_image_bytes(data)
        if asset.kind == "scene":
            scene_index += 1
            scene_id = asset.ref_id or f"scene_{scene_index:03d}"
            dest = job.scene_refs_dir / f"{scene_id}_ref{suffix}"
            dest.write_bytes(data)
            scene_images.append(
                SceneReferenceImage(
                    scene_id=scene_id,
                    path=str(dest.relative_to(job.root)),
                )
            )
        else:
            dest = job.character_refs_dir / f"{asset.ref_id}_ref{suffix}"
            dest.write_bytes(data)
            character_images.append(
                CharacterReferenceImage(
                    character_id=asset.ref_id,
                    path=str(dest.relative_to(job.root)),
                )
            )

    return payload.model_copy(
        update={
            "scene_reference_images": scene_images,
            "character_reference_images": character_images,
        }
    )


def validate_payload_assets_on_job(job: JobPaths, payload: GatewayPayload) -> list[str]:
    """Return human-readable errors for missing or invalid job-local reference files."""
    errors: list[str] = []
    for ref in payload.character_reference_images:
        candidate = job.root / ref.path
        if not candidate.is_file():
            errors.append(
                f"Missing character reference for {ref.character_id!r}: {ref.path}"
            )
            continue
        try:
            validate_image_bytes(candidate.read_bytes())
        except ImageValidationError as exc:
            errors.append(
                f"Invalid character reference for {ref.character_id!r}: {exc}"
            )
    for ref in payload.scene_reference_images:
        candidate = job.root / ref.path
        if not candidate.is_file():
            errors.append(f"Missing scene reference for {ref.scene_id!r}: {ref.path}")
            continue
        try:
            validate_image_bytes(candidate.read_bytes())
        except ImageValidationError as exc:
            errors.append(f"Invalid scene reference for {ref.scene_id!r}: {exc}")
    return errors


def require_payload_assets_on_job(job: JobPaths, payload: GatewayPayload) -> None:
    errors = validate_payload_assets_on_job(job, payload)
    if errors:
        raise GatewayAssetValidationError("; ".join(errors))


def copy_staged_assets_to_job(
    job: JobPaths,
    staged_paths: list[Path],
    *,
    kind: Literal["scene", "character"],
    ref_ids: list[str] | None = None,
) -> GatewayAssetBundle:
    assets: list[StagedAsset] = []
    for index, source in enumerate(staged_paths):
        if kind == "scene":
            ref_id = (ref_ids[index] if ref_ids and index < len(ref_ids) else None) or f"scene_{index + 1:03d}"
        else:
            ref_id = ref_ids[index] if ref_ids and index < len(ref_ids) else f"char_{index + 1}"
        assets.append(StagedAsset(kind=kind, ref_id=ref_id, source_path=source))
    return GatewayAssetBundle(staged=tuple(assets))
