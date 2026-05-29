"""End-to-end mock pipeline through final.mp4."""

import json
from pathlib import Path

from video_pipeline.config import Settings
from video_pipeline.orchestrator import PipelineOrchestrator


def test_mock_pipeline_produces_final_video(tmp_path: Path) -> None:
    fixtures = Path(__file__).parent / "fixtures"
    orchestrator = PipelineOrchestrator(
        Settings(job_storage_dir=str(tmp_path), video_pipeline_mock=True)
    )
    job = orchestrator.run(fixtures / "gateway_payload.json", mock=True)

    assert job.final_dir.joinpath("final.mp4").is_file()
    assert job.final_dir.joinpath("assembled_video.mp4").is_file()
    assert (job.reports_dir / "generation_report.json").is_file()
    assert (job.reports_dir / "qc_report.json").is_file()

    raw_clips = list(job.clips_raw_dir.glob("*.mp4"))
    validated_clips = list(job.clips_validated_dir.glob("*.mp4"))
    assert len(raw_clips) == 6
    assert len(validated_clips) == 6

    state = json.loads(job.job_state_path.read_text(encoding="utf-8"))
    assert state["status"] == "delivered"
