"""Tests for Plot Agent (剧情)."""

from datetime import datetime, timezone

from video_pipeline.agents.intake_agent import build_intake_plan
from video_pipeline.agents.plot_agent import run_plot_agent
from video_pipeline.schemas import GatewayPayload
from video_pipeline.storage import create_job_paths, ensure_job_layout, resolve_storage_root


def _payload(**overrides) -> GatewayPayload:
    base = {
        "raw_prompt": "Coffeefee healing short in coffee shop",
        "channel": "telegram",
        "user_id": "test",
        "timestamp": datetime.now(timezone.utc),
        "character_ids": ["coffeefee"],
        "target_duration_sec": 30,
    }
    base.update(overrides)
    return GatewayPayload.model_validate(base)


def test_plot_agent_generates_when_no_script(tmp_path) -> None:
    job = ensure_job_layout(create_job_paths(resolve_storage_root(str(tmp_path))))
    payload = _payload()
    intake = build_intake_plan(job, payload)
    assert intake.plot_route == "generate_plot"

    plot = run_plot_agent(job, payload, intake, mock=True)
    assert plot.mode == "generated"
    assert len(plot.full_plot) > 200
    assert plot.narrative_arc
    assert plot.scene_outlines
    assert all(len(scene.story_text) > 50 for scene in plot.scene_outlines)
    assert job.plot_plan_path.is_file()
    assert (job.plot_dir / "plot_narrative.txt").is_file()
    assert "FULL PLOT" in plot.script_handoff
    assert plot.full_plot in plot.script_handoff


def test_plot_agent_reviews_user_script(tmp_path) -> None:
    job = ensure_job_layout(create_job_paths(resolve_storage_root(str(tmp_path))))
    payload = _payload(
        has_script=True,
        user_script_text="A cat walks into a cafe. The end.",
    )
    intake = build_intake_plan(job, payload)
    assert intake.plot_route == "review_plot"

    plot = run_plot_agent(job, payload, intake, mock=True)
    assert plot.mode in {"reviewed", "from_user_script"}
    assert plot.gaps_found
