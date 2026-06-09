"""Storyboard schema — per-shot breakdown after Storyboard Agent."""

from collections import defaultdict
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from video_pipeline.schemas.script import DialogueLine, MoodType

SceneType = Literal["realistic", "simple", "creative", "abstract"]
MotionIntensity = Literal["low", "medium", "high"]
ShotSize = Literal["EWS", "WS", "MLS", "MS", "MCU", "CU", "ECU"]
GenerationMode = Literal["t2v", "i2v", "first_last_frame"]
VideoModelName = Literal["seedance", "kling", "wan_t2v", "premium_api", "mock"]


class Shot(BaseModel):
    shot_id: str = Field(pattern=r"^shot_\d{3}$")
    scene_id: str = Field(pattern=r"^scene_\d{3}$")
    scene_order: int | None = Field(default=None, ge=1)
    shot_order_in_scene: int | None = Field(default=None, ge=1)
    duration_sec: float = Field(gt=0, le=8)
    shot_purpose: str | None = None
    subject: str = Field(min_length=1)
    shot_size: ShotSize
    camera_angle: str = Field(min_length=1)
    camera_move: str = Field(min_length=1)
    camera_progression: str | None = None
    action: str = Field(min_length=1)
    facial_expression: str = Field(min_length=1)
    character_gaze: str = Field(min_length=1)
    blocking: str = Field(min_length=1)
    mood: MoodType
    scene_type: SceneType
    motion_intensity: MotionIntensity
    has_characters: bool
    character_ids: list[str] = Field(default_factory=list)
    character_prompts: list[str] = Field(default_factory=list)
    character_reference_ids: list[str] = Field(default_factory=list)
    character_reference_image_paths: list[str] = Field(default_factory=list)
    scene_reference_id: str | None = None
    scene_reference_image_path: str | None = None
    visual_style: str | None = None
    color_palette: str | None = None
    style_tags: list[str] = Field(default_factory=list)
    preview_desc: str | None = None
    keyframe_start_desc: str | None = None
    keyframe_end_desc: str | None = None
    dialogue: list[DialogueLine] = Field(default_factory=list)
    emotion: str | None = None
    emotion_transition: str | None = None
    shot_continuity_from_previous: str | None = None
    sfx_tags: list[str] = Field(default_factory=list)
    needs_scene_master: bool = True
    reuse_preview_as_start_frame: bool = True
    generation_mode: GenerationMode
    generation_mode_reason: str = Field(min_length=1)
    preferred_model: VideoModelName | None = None
    fallback_model: VideoModelName | None = None

    @model_validator(mode="after")
    def fill_storyboard_defaults(self) -> "Shot":
        updates: dict[str, object] = {}
        if not self.shot_purpose:
            updates["shot_purpose"] = self.subject
        if not self.preview_desc:
            updates["preview_desc"] = f"{self.subject}. {self.action}"
        if not self.keyframe_start_desc:
            updates["keyframe_start_desc"] = updates.get("preview_desc", self.preview_desc)
        if not self.keyframe_end_desc:
            updates["keyframe_end_desc"] = self.action
        if not self.camera_progression:
            updates["camera_progression"] = f"{self.shot_size} {self.camera_move}"
        if not self.emotion:
            updates["emotion"] = self.mood
        if updates:
            return self.model_copy(update=updates)
        return self

    @model_validator(mode="after")
    def character_fields_consistent(self) -> "Shot":
        if self.has_characters:
            if not self.character_ids:
                raise ValueError("character_ids must not be empty when has_characters is true")
            if not self.character_prompts:
                raise ValueError(
                    "character_prompts must not be empty when has_characters is true"
                )
            for label, value in (
                ("facial_expression", self.facial_expression),
                ("character_gaze", self.character_gaze),
                ("blocking", self.blocking),
            ):
                if value.strip().lower() == "n/a":
                    raise ValueError(f"{label} must be descriptive when has_characters is true")
        else:
            if self.character_ids or self.character_prompts:
                raise ValueError(
                    "character_ids and character_prompts must be empty when has_characters is false"
                )
        return self


class ShotsDocument(BaseModel):
    shots: list[Shot] = Field(min_length=1)

    @model_validator(mode="after")
    def normalize_shot_order(self) -> "ShotsDocument":
        grouped: dict[str, list[Shot]] = defaultdict(list)
        for shot in self.shots:
            grouped[shot.scene_id].append(shot)

        normalized: list[Shot] = []
        scene_order_map: dict[str, int] = {}
        for scene_index, scene_id in enumerate(
            sorted(grouped.keys(), key=lambda value: int(value.split("_")[1])),
            start=1,
        ):
            scene_order_map[scene_id] = scene_index
            scene_shots = sorted(
                grouped[scene_id],
                key=lambda item: int(item.shot_id.split("_")[1]),
            )
            for shot_index, shot in enumerate(scene_shots, start=1):
                normalized.append(
                    shot.model_copy(
                        update={
                            "scene_order": shot.scene_order or scene_index,
                            "shot_order_in_scene": shot.shot_order_in_scene or shot_index,
                        }
                    )
                )
        object.__setattr__(self, "shots", normalized)
        return self

    @model_validator(mode="after")
    def unique_shot_ids(self) -> "ShotsDocument":
        ids = [shot.shot_id for shot in self.shots]
        if len(ids) != len(set(ids)):
            raise ValueError("shot_id values must be unique")
        return self

    @property
    def total_duration_sec(self) -> float:
        return sum(shot.duration_sec for shot in self.shots)

    def shots_for_scene(self, scene_id: str) -> list[Shot]:
        return [shot for shot in self.shots if shot.scene_id == scene_id]
