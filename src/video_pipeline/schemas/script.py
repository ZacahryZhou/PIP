"""Script plan schema — single source of truth after Script Agent."""

from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

MoodType = Literal["action", "tense", "calm", "normal", "dream", "memory"]


class DialogueLine(BaseModel):
    speaker: str = Field(min_length=1)
    text: str = Field(min_length=1)
    start_sec: float = Field(ge=0)
    end_sec: float = Field(gt=0)

    @model_validator(mode="after")
    def end_after_start(self) -> "DialogueLine":
        if self.end_sec <= self.start_sec:
            raise ValueError("end_sec must be greater than start_sec")
        return self


class Scene(BaseModel):
    scene_id: str = Field(pattern=r"^scene_\d{3}$")
    scene_order: int | None = Field(default=None, ge=1)
    scene_title: str | None = None
    scene_purpose: str | None = None
    duration_sec: float = Field(gt=0, le=12)
    location: str = Field(min_length=1)
    time_of_day: str = Field(min_length=1)
    characters: list[str] = Field(default_factory=list)
    action_summary: str = Field(min_length=1)
    dialogue: list[DialogueLine] = Field(default_factory=list)
    mood: MoodType
    visual_style: str | None = None
    color_palette: str | None = None
    scene_reference_id: str | None = None
    emotional_beat: str = Field(min_length=1)
    emotion_start: str | None = None
    emotion_end: str | None = None
    dialogue_intent: str | None = None
    camera_notes: str = Field(min_length=1)
    camera_intent: str | None = None
    director_notes: str = Field(min_length=1)
    transition_to_next_scene: str | None = None


class ScriptPlan(BaseModel):
    narrative_arc: str = Field(min_length=1)
    visual_style: str = Field(min_length=1)
    color_tone: str = Field(min_length=1)
    music_mood: str = Field(min_length=1)
    music_bpm: int = Field(ge=40, le=220)
    camera_language: str = Field(min_length=1)
    characters_in_use: list[str] = Field(default_factory=list)
    total_duration_sec: float = Field(gt=0, le=60)
    scene_list: list[Scene] = Field(min_length=1)

    @field_validator("total_duration_sec")
    @classmethod
    def mvp_duration_range(cls, value: float) -> float:
        if value < 15 or value > 60:
            raise ValueError("MVP total_duration_sec must be between 15 and 60 seconds")
        return value

    @model_validator(mode="after")
    def normalize_scenes(self) -> "ScriptPlan":
        ordered = sorted(
            self.scene_list,
            key=lambda scene: scene.scene_order or int(scene.scene_id.split("_")[1]),
        )
        normalized: list[Scene] = []
        for index, scene in enumerate(ordered, start=1):
            normalized.append(
                scene.model_copy(
                    update={
                        "scene_order": scene.scene_order or index,
                        "scene_title": scene.scene_title or scene.location,
                        "scene_purpose": scene.scene_purpose or scene.action_summary,
                        "visual_style": scene.visual_style or self.visual_style,
                        "color_palette": scene.color_palette or self.color_tone,
                        "camera_intent": scene.camera_intent or scene.camera_notes,
                        "dialogue_intent": scene.dialogue_intent
                        or (
                            "spoken dialogue for subtitles and TTS"
                            if scene.dialogue
                            else "no spoken dialogue"
                        ),
                    }
                )
            )
        object.__setattr__(self, "scene_list", normalized)
        return self

    @model_validator(mode="after")
    def scene_durations_match_total(self) -> "ScriptPlan":
        scene_total = sum(scene.duration_sec for scene in self.scene_list)
        if abs(scene_total - self.total_duration_sec) > 1.0:
            raise ValueError(
                f"scene_list durations sum to {scene_total}, "
                f"but total_duration_sec is {self.total_duration_sec} (max delta 1s)"
            )
        scene_orders = [scene.scene_order for scene in self.scene_list if scene.scene_order]
        if len(scene_orders) != len(set(scene_orders)):
            raise ValueError("scene_order values must be unique within scene_list")
        return self

    @property
    def scene_ids(self) -> list[str]:
        return [scene.scene_id for scene in self.scene_list]
