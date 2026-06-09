"""Keyframe prompt artifact — debuggable image prompts per shot."""

from typing import Literal

from pydantic import BaseModel, Field

PromptSource = Literal["llm", "template"]


class KeyframePromptEntry(BaseModel):
    shot_id: str = Field(pattern=r"^shot_\d{3}$")
    scene_id: str = Field(pattern=r"^scene_\d{3}$")
    start_prompt: str = Field(min_length=1)
    end_prompt: str = Field(min_length=1)
    scene_master_path: str | None = None
    prompt_source: PromptSource = "template"


class KeyframePromptsDocument(BaseModel):
    job_id: str = Field(min_length=1)
    items: list[KeyframePromptEntry] = Field(default_factory=list)
