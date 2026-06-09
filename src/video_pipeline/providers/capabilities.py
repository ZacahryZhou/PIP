"""Video provider capability flags for routing and generation."""

from __future__ import annotations

from dataclasses import dataclass

from video_pipeline.schemas.storyboard import GenerationMode, VideoModelName


@dataclass(frozen=True)
class ProviderCapabilities:
    supports_t2v: bool
    supports_i2v: bool
    supports_first_last_frame: bool
    supports_audio_generation: bool


PROVIDER_CAPABILITIES: dict[VideoModelName, ProviderCapabilities] = {
    "seedance": ProviderCapabilities(
        supports_t2v=True,
        supports_i2v=True,
        supports_first_last_frame=False,
        supports_audio_generation=True,
    ),
    "kling": ProviderCapabilities(
        supports_t2v=True,
        supports_i2v=True,
        supports_first_last_frame=True,
        supports_audio_generation=False,
    ),
    "wan_t2v": ProviderCapabilities(
        supports_t2v=True,
        supports_i2v=False,
        supports_first_last_frame=False,
        supports_audio_generation=False,
    ),
    "premium_api": ProviderCapabilities(
        supports_t2v=True,
        supports_i2v=True,
        supports_first_last_frame=False,
        supports_audio_generation=False,
    ),
    "mock": ProviderCapabilities(
        supports_t2v=True,
        supports_i2v=True,
        supports_first_last_frame=True,
        supports_audio_generation=False,
    ),
}


def get_provider_capabilities(model: VideoModelName) -> ProviderCapabilities:
    return PROVIDER_CAPABILITIES[model]


def resolve_generation_mode(
    requested: GenerationMode,
    model: VideoModelName,
) -> tuple[GenerationMode, str]:
    caps = get_provider_capabilities(model)
    if requested == "first_last_frame":
        if caps.supports_first_last_frame:
            return requested, "first_last_frame supported by provider"
        if caps.supports_i2v:
            return "i2v", "first_last_frame unsupported; fallback to i2v"
        return "t2v", "first_last_frame unsupported; fallback to t2v"
    if requested == "i2v":
        if caps.supports_i2v:
            return requested, "i2v supported by provider"
        return "t2v", "i2v unsupported; fallback to t2v"
    return "t2v", "text-to-video"


def keyframe_cost_for_mode(mode: GenerationMode) -> float:
    if mode == "first_last_frame":
        return 0.30
    if mode == "i2v":
        return 0.15
    return 0.0
