"""Routing schema — deterministic model assignment per shot."""

from pydantic import BaseModel, Field, model_validator

from video_pipeline.schemas.storyboard import VideoModelName


class RouteDecision(BaseModel):
    shot_id: str = Field(pattern=r"^shot_\d{3}$")
    preferred_model: VideoModelName
    fallback_model: VideoModelName
    routing_reason: str = Field(min_length=1)
    estimated_cost_per_shot: float = Field(ge=0)
    estimated_duration_sec: float = Field(gt=0)


class RoutingPlan(BaseModel):
    routes: list[RouteDecision] = Field(min_length=1)
    total_estimated_cost: float = Field(ge=0)
    currency: str = Field(default="USD", min_length=3, max_length=3)
    should_continue: bool
    budget_message: str | None = None

    @model_validator(mode="after")
    def unique_routes_and_cost(self) -> "RoutingPlan":
        shot_ids = [route.shot_id for route in self.routes]
        if len(shot_ids) != len(set(shot_ids)):
            raise ValueError("Each shot_id may appear only once in routes")

        computed_total = round(sum(route.estimated_cost_per_shot for route in self.routes), 4)
        if abs(computed_total - self.total_estimated_cost) > 0.01:
            raise ValueError(
                f"total_estimated_cost {self.total_estimated_cost} "
                f"does not match sum of routes {computed_total}"
            )

        if not self.should_continue and not self.budget_message:
            raise ValueError("budget_message is required when should_continue is false")

        return self
