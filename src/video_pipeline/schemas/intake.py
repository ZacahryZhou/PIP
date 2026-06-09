"""Intake plan and clarification schemas — Ring 1 gateway routing."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

IntakeGapKind = Literal[
    "character_reference",
    "character_ids",
    "scene_reference",
    "style",
    "duration",
    "script",
    "plot",
]

IntakeGapChoice = Literal["system_generate", "user_supplement", "pending"]
IntakeClarificationStatus = Literal["pending", "resolved", "cancelled"]

ImageAssetKind = Literal["character", "scene", "prop", "style", "mood", "other"]
PlotRoute = Literal["generate_plot", "review_plot", "direct_to_script"]


class CharacterIntakeJob(BaseModel):
    character_id: str = Field(min_length=1)
    reference_path: str | None = None
    source: Literal["user_upload", "system_generate", "catalog"] = "catalog"
    linked_scene_ids: list[str] = Field(default_factory=list)


class SceneIntakeJob(BaseModel):
    scene_id: str = Field(pattern=r"^scene_\d{3}$")
    reference_path: str | None = None
    source: Literal["user_upload", "system_generate"] = "system_generate"
    linked_character_ids: list[str] = Field(default_factory=list)


class ReferenceIntakeJob(BaseModel):
    """Non-character/non-scene user images (props, style boards, mood refs)."""

    ref_id: str = Field(min_length=1)
    kind: ImageAssetKind = "other"
    reference_path: str | None = None
    linked_scene_id: str | None = None
    linked_character_id: str | None = None
    notes: str | None = None


class SceneShotHint(BaseModel):
    """Planned coverage inside one scene — connects script beats to storyboard shots."""

    scene_id: str = Field(pattern=r"^scene_\d{3}$")
    expected_shots: int = Field(default=1, ge=1, le=6)
    camera_progression: str = Field(min_length=1)
    linked_character_ids: list[str] = Field(default_factory=list)
    linked_reference_ids: list[str] = Field(default_factory=list)
    needs_generated_scene_image: bool = False
    needs_generated_character_refs: list[str] = Field(default_factory=list)


class AssetLink(BaseModel):
    """Cross-artifact index so downstream stages stay connected."""

    link_id: str = Field(min_length=1)
    scene_id: str | None = None
    character_id: str | None = None
    ref_id: str | None = None
    scene_order: int | None = Field(default=None, ge=1)


class IntakePlan(BaseModel):
    """Routing table produced after intake (and any clarifications)."""

    job_id: str = Field(min_length=1)
    script_brief: str = Field(min_length=1)
    plot_route: PlotRoute = "generate_plot"
    characters_for_script: list[str] = Field(default_factory=list)
    character_jobs: list[CharacterIntakeJob] = Field(default_factory=list)
    scene_jobs: list[SceneIntakeJob] = Field(default_factory=list)
    reference_jobs: list[ReferenceIntakeJob] = Field(default_factory=list)
    scene_shot_hints: list[SceneShotHint] = Field(default_factory=list)
    asset_links: list[AssetLink] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class IntakeGap(BaseModel):
    gap_id: str = Field(min_length=1)
    kind: IntakeGapKind
    label: str = Field(min_length=1, description="Short label for user message")
    detail: str = Field(min_length=1)
    character_id: str | None = None
    scene_id: str | None = None
    required: bool = True


class IntakeGapResolution(BaseModel):
    gap_id: str = Field(min_length=1)
    choice: IntakeGapChoice
    user_supplement: str | None = None
    resolved_at: datetime | None = None


class IntakeClarificationDocument(BaseModel):
    job_id: str = Field(min_length=1)
    status: IntakeClarificationStatus = "pending"
    gaps: list[IntakeGap] = Field(default_factory=list)
    user_message: str = Field(min_length=1)
    resolutions: list[IntakeGapResolution] = Field(default_factory=list)
    created_at: datetime
    resolved_at: datetime | None = None
