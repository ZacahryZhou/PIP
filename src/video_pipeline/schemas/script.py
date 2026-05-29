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
    duration_sec: float = Field(gt=0, le=12)
    location: str = Field(min_length=1)
    time_of_day: str = Field(min_length=1)
    characters: list[str] = Field(default_factory=list)
    action_summary: str = Field(min_length=1)
    dialogue: list[DialogueLine] = Field(default_factory=list)
    mood: MoodType
    camera_notes: str = Field(min_length=1)


class ScriptPlan(BaseModel):
    narrative_arc: str = Field(min_length=1)
    visual_style: str = Field(min_length=1)
    color_tone: str = Field(min_length=1)
    music_mood: str = Field(min_length=1)
    music_bpm: int = Field(ge=40, le=220)
    camera_language: str = Field(min_length=1)
    characters_in_use: list[str] = Field(default_factory=list)
    total_duration_sec: float = Field(gt=0, le=45)
    scene_list: list[Scene] = Field(min_length=1)

    @field_validator("total_duration_sec")
    @classmethod
    def mvp_duration_range(cls, value: float) -> float:
        if value < 15 or value > 45:
            raise ValueError("MVP total_duration_sec must be between 15 and 45 seconds")
        return value

    @model_validator(mode="after")
    def scene_durations_match_total(self) -> "ScriptPlan":
        scene_total = sum(scene.duration_sec for scene in self.scene_list)
        if abs(scene_total - self.total_duration_sec) > 1.0:
            raise ValueError(
                f"scene_list durations sum to {scene_total}, "
                f"but total_duration_sec is {self.total_duration_sec} (max delta 1s)"
            )
        return self
