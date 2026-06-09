"""Per-shot links from script/storyboard IDs to on-disk asset packs."""

from pydantic import BaseModel, Field


class CharacterShotBinding(BaseModel):
    character_id: str = Field(min_length=1)
    reference_image_paths: list[str] = Field(default_factory=list)


class ReferenceShotBinding(BaseModel):
    ref_id: str = Field(min_length=1)
    kind: str = Field(min_length=1)
    asset_path: str = Field(min_length=1)


class ShotAssetBinding(BaseModel):
    shot_id: str = Field(pattern=r"^shot_\d{3}$")
    scene_id: str = Field(pattern=r"^scene_\d{3}$")
    character_ids: list[str] = Field(default_factory=list)
    scene_master_path: str | None = None
    character_bindings: list[CharacterShotBinding] = Field(default_factory=list)
    reference_bindings: list[ReferenceShotBinding] = Field(default_factory=list)


class SceneAssetGroup(BaseModel):
    scene_id: str = Field(pattern=r"^scene_\d{3}$")
    shot_ids: list[str] = Field(default_factory=list)
    scene_master_path: str | None = None
    character_ids: list[str] = Field(default_factory=list)
    reference_ids: list[str] = Field(default_factory=list)


class ShotAssetBindingReport(BaseModel):
    job_id: str = Field(min_length=1)
    entries: list[ShotAssetBinding] = Field(default_factory=list)
    by_scene: list[SceneAssetGroup] = Field(default_factory=list)
