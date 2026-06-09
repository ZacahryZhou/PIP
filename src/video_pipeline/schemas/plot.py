"""Plot plan schema — Ring 2 story/plot agent output before Script Agent."""

from typing import Literal

from pydantic import BaseModel, Field

PlotMode = Literal["generated", "reviewed", "from_user_script"]


class PlotDialogueBeat(BaseModel):
    speaker: str = Field(min_length=1)
    line: str = Field(min_length=1)
    delivery: str | None = None


class PlotSceneOutline(BaseModel):
    """One scene in the complete plot — full story text, not a one-line premise."""

    scene_id: str = Field(pattern=r"^scene_\d{3}$")
    scene_order: int = Field(ge=1)
    heading: str = Field(min_length=1, description="Scene slugline / title")
    story_text: str = Field(
        min_length=1,
        description="Complete prose for this scene: action, emotion, staging",
    )
    emotional_beat: str = Field(min_length=1)
    characters: list[str] = Field(default_factory=list)
    location: str = Field(min_length=1)
    time_of_day: str = Field(default="night")
    visual_style_hint: str | None = None
    scene_style_hint: str | None = None
    dialogue_beats: list[PlotDialogueBeat] = Field(default_factory=list)
    dialogue_intent: str | None = None
    camera_progression: str = Field(min_length=1)
    expected_shot_count: int = Field(default=1, ge=1, le=6)
    linked_scene_ref_id: str | None = None
    linked_character_ids: list[str] = Field(default_factory=list)
    linked_reference_ids: list[str] = Field(default_factory=list)
    needs_scene_image: bool = False
    missing_notes: list[str] = Field(default_factory=list)

    # Back-compat alias used in handoff builders
    @property
    def premise(self) -> str:
        return self.story_text


class PlotPlan(BaseModel):
    job_id: str = Field(min_length=1)
    mode: PlotMode
    plot_summary: str = Field(min_length=1)
    narrative_arc: str = Field(
        min_length=1,
        description="Emotional / story arc across the full plot",
    )
    full_plot: str = Field(
        min_length=1,
        description="Complete plot narrative handed to Script Agent — not an outline stub",
    )
    visual_style_hint: str | None = None
    scene_style_hint: str | None = None
    scene_outlines: list[PlotSceneOutline] = Field(min_length=1)
    gaps_found: list[str] = Field(default_factory=list)
    supplements: list[str] = Field(default_factory=list)
    ready_for_script: bool = True
    script_handoff: str = Field(
        min_length=1,
        description="Consolidated handoff: full plot + per-scene detail for Script Agent",
    )
