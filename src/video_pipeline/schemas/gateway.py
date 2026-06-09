"""Gateway payload schema — normalized user input from Telegram/WhatsApp."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator


ChannelName = Literal["telegram", "whatsapp"]


class SceneReferenceImage(BaseModel):
    scene_id: str = Field(pattern=r"^scene_\d{3}$")
    path: str = Field(min_length=1, description="Job-local path or stable asset id")


class CharacterReferenceImage(BaseModel):
    character_id: str = Field(min_length=1)
    path: str = Field(min_length=1, description="Job-local path or stable asset id")


class OtherReferenceImage(BaseModel):
    ref_id: str = Field(min_length=1)
    path: str = Field(min_length=1)
    kind_hint: Literal["prop", "style", "mood", "other"] | None = None
    linked_scene_id: str | None = Field(default=None, pattern=r"^scene_\d{3}$")
    linked_character_id: str | None = None


class GatewayPayload(BaseModel):
    """Input from OpenClaw gateway → Python orchestrator."""

    raw_prompt: str = Field(default="", description="User natural language request")
    channel: ChannelName
    user_id: str = Field(min_length=1)
    timestamp: datetime
    has_script: bool = False
    user_script_text: str | None = None
    character_ids: list[str] = Field(default_factory=list)
    style_preset: str | None = None
    style_notes: str | None = None
    scene_reference_images: list[SceneReferenceImage] = Field(default_factory=list)
    character_reference_images: list[CharacterReferenceImage] = Field(default_factory=list)
    other_reference_images: list[OtherReferenceImage] = Field(default_factory=list)
    target_duration_sec: float | None = Field(default=None, gt=0, le=60)
    language: str = Field(default="en", min_length=2)

    @model_validator(mode="after")
    def prompt_or_script_present(self) -> "GatewayPayload":
        has_prompt = bool(self.raw_prompt.strip())
        has_user_script = bool(self.user_script_text and self.user_script_text.strip())
        if not has_prompt and not has_user_script:
            raise ValueError("raw_prompt or user_script_text must be provided")
        return self
