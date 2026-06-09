"""Tests for early TTS prep and provider abstraction."""

from __future__ import annotations

import json
from pathlib import Path

from video_pipeline.config import Settings
from video_pipeline.pipeline.bgm_prep import run_bgm_prep
from video_pipeline.pipeline.dialogue import collect_dialogue_text_specs
from video_pipeline.pipeline.tts import load_tts_manifest, run_tts_prep, tts_manifest_path
from video_pipeline.schemas import ScriptPlan, ShotsDocument
from video_pipeline.storage import create_job_paths, ensure_job_layout, resolve_storage_root


def _load_fixtures() -> tuple[ScriptPlan, ShotsDocument]:
    fixtures = Path(__file__).parent / "fixtures"
    script = ScriptPlan.model_validate_json(fixtures.joinpath("script.json").read_text())
    shots = ShotsDocument.model_validate_json(fixtures.joinpath("shots.json").read_text())
    return script, shots


def test_collect_dialogue_text_specs_matches_shot_dialogue() -> None:
    script, shots = _load_fixtures()
    specs = collect_dialogue_text_specs(script, shots)
    assert len(specs) == 2
    assert specs[0].line_id == "shot_002_00"
    assert specs[0].text == "Keep moving."
    assert specs[1].line_id == "shot_006_00"


def test_run_tts_prep_writes_manifest_and_wavs(tmp_path: Path) -> None:
    script, shots = _load_fixtures()
    storage = resolve_storage_root(str(tmp_path))
    job = ensure_job_layout(create_job_paths(storage))
    settings = Settings(job_storage_dir=str(tmp_path), video_pipeline_mock=True)

    report = run_tts_prep(job, script, shots, settings=settings, mock=True)

    assert report.status == "ok"
    assert report.segment_count == 2
    manifest = load_tts_manifest(job)
    assert manifest is not None
    assert manifest.provider == "mock"
    assert tts_manifest_path(job).is_file()
    assert (job.root / "reports" / "tts_report.json").is_file()
    for entry in manifest.segments:
        assert entry.status == "ok"
        assert (job.root / entry.wav_path).is_file()


def test_run_tts_prep_resumes_existing_manifest(tmp_path: Path) -> None:
    script, shots = _load_fixtures()
    storage = resolve_storage_root(str(tmp_path))
    job = ensure_job_layout(create_job_paths(storage))
    settings = Settings(job_storage_dir=str(tmp_path), video_pipeline_mock=True)

    first = run_tts_prep(job, script, shots, settings=settings, mock=True)
    second = run_tts_prep(job, script, shots, settings=settings, mock=True)

    assert first.resumed is False
    assert second.resumed is True
    assert second.status == "ok"


def test_run_bgm_prep_skipped_when_mode_off(tmp_path: Path) -> None:
    script, shots = _load_fixtures()
    storage = resolve_storage_root(str(tmp_path))
    job = ensure_job_layout(create_job_paths(storage))
    settings = Settings(job_storage_dir=str(tmp_path), video_pipeline_mock=True, pip_bgm_mode="off")

    report = run_bgm_prep(job, script, shots, settings=settings, mock=True)

    assert report.status == "skipped"
    assert report.mode == "off"
    assert not (job.root / "audio" / "bgm_prepared.wav").is_file()
