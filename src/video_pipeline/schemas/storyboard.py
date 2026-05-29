"""Storyboard schema — per-shot breakdown after Storyboard Agent."""

from typing import Literal

from pydantic import BaseModel, Field, model_validator

from video_pipeline.schemas.script import DialogueLine, MoodType

SceneType = Literal["realistic", "simple", "creative", "abstract"]
MotionIntensity = Literal["low", "medium", "high"]
VideoModelName = Literal["seedance", "kling", "wan_t2v", "premium_api", "mock"]


class Shot(BaseModel):
    shot_id: str = Field(pattern=r"^shot_\d{3}$")
    scene_id: str = Field(pattern=r"^scene_\d{3}$")
    duration_sec: float = Field(gt=0, le=8)
    subject: str = Field(min_length=1)
    camera_move: str = Field(min_length=1)
    action: str = Field(min_length=1)
    mood: MoodType
    scene_type: SceneType
    motion_intensity: MotionIntensity
    has_characters: bool
    character_ids: list[str] = Field(default_factory=list)
    character_prompts: list[str] = Field(default_factory=list)
    style_tags: list[str] = Field(default_factory=list)
    dialogue: list[DialogueLine] = Field(default_factory=list)
    preferred_model: VideoModelName | None = None
    fallback_model: VideoModelName | None = None

    @model_validator(mode="after")
    def character_fields_consistent(self) -> "Shot":
        if self.has_characters:
            if not self.character_ids:
                raise ValueError("character_ids must not be empty when has_characters is true")
            if not self.character_prompts:
                raise ValueError(
                    "character_prompts must not be empty when has_characters is true"
                )
        else:
            if self.character_ids or self.character_prompts:
                raise ValueError(
                    "character_ids and character_prompts must be empty when has_characters is false"
                )
        return self


class ShotsDocument(BaseModel):
    shots: list[Shot] = Field(min_length=1)

    @model_validator(mode="after")
    def unique_shot_ids(self) -> "ShotsDocument":
        ids = [shot.shot_id for shot in self.shots]
        if len(ids) != len(set(ids)):
            raise ValueError("shot_id values must be unique")
        return self

    @property
    def total_duration_sec(self) -> float:
        return sum(shot.duration_sec for shot in self.shots)
