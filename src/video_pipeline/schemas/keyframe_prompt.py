"""Keyframe prompt artifact — debuggable image prompts per shot."""

from pydantic import BaseModel, Field


class KeyframePromptEntry(BaseModel):
    shot_id: str = Field(pattern=r"^shot_\d{3}$")
    scene_id: str = Field(pattern=r"^scene_\d{3}$")
    start_prompt: str = Field(min_length=1)
    end_prompt: str = Field(min_length=1)
    scene_master_path: str | None = None


class KeyframePromptsDocument(BaseModel):
    job_id: str = Field(min_length=1)
    items: list[KeyframePromptEntry] = Field(default_factory=list)
