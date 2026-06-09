"""Plot Agent (剧情) — write or review the *complete* plot before Script Agent."""

from __future__ import annotations

import json
import re
from pathlib import Path

from video_pipeline.config import Settings, settings
from video_pipeline.schemas import GatewayPayload
from video_pipeline.schemas.intake import IntakePlan, PlotRoute
from video_pipeline.schemas.plot import PlotDialogueBeat, PlotPlan, PlotSceneOutline
from video_pipeline.storage import JobPaths, repo_root, write_json
from video_pipeline.utils.llm import deepseek_chat_json


def _infer_scene_count(payload: GatewayPayload, intake: IntakePlan) -> int:
    if intake.scene_jobs:
        return len(intake.scene_jobs)
    duration = payload.target_duration_sec or 30.0
    return max(1, min(6, int(round(duration / 5))))


def _load_rule(job: JobPaths, name: str) -> str:
    path = job.rules_snapshot_dir / name
    if path.is_file():
        return path.read_text(encoding="utf-8")
    fallback = repo_root() / "rules" / name
    return fallback.read_text(encoding="utf-8") if fallback.is_file() else ""


def _coffeefee_fixture_plot() -> str:
    path = repo_root() / "tests" / "fixtures" / "coffeefee_script.txt"
    return path.read_text(encoding="utf-8")


def _is_coffeefee_job(payload: GatewayPayload, intake: IntakePlan) -> bool:
    blob = f"{payload.raw_prompt} {' '.join(intake.characters_for_script)}".lower()
    return "coffeefee" in blob or "coffee" in blob


def _parse_coffeefee_scenes(full_plot: str) -> list[dict]:
    blocks = re.split(r"\nCUT TO:\s*\n", full_plot, flags=re.IGNORECASE)
    scenes: list[dict] = []
    for block in blocks:
        block = block.strip()
        if not block or block.startswith("《"):
            continue
        heading_match = re.search(
            r"(INT\.|EXT\.)\s*([^\n]+?)\s*-\s*([^\n]+?)(?:\s+(\d+:\d+-\d+:\d+))?",
            block,
        )
        heading = heading_match.group(0).strip() if heading_match else block.split("\n")[0]
        location = heading_match.group(2).strip() if heading_match else "未命名场景"
        time_of_day = heading_match.group(3).strip() if heading_match else "night"
        dialogue_beats: list[PlotDialogueBeat] = []
        for speaker, line in re.findall(
            r"^\s{20}([A-Z\u4e00-\u9fff]+)\s*\n\s{10}(.+)$",
            block,
            re.MULTILINE,
        ):
            dialogue_beats.append(
                PlotDialogueBeat(speaker=speaker.strip(), line=line.strip())
            )
        scenes.append(
            {
                "heading": heading,
                "story_text": block,
                "location": location,
                "time_of_day": time_of_day,
                "dialogue_beats": dialogue_beats,
            }
        )
    return scenes


def _generate_full_plot_mock(
    payload: GatewayPayload,
    intake: IntakePlan,
) -> tuple[str, str, list[PlotSceneOutline]]:
    """Return (full_plot, narrative_arc, scene_outlines) with complete story text."""
    if _is_coffeefee_job(payload, intake):
        full_plot = _coffeefee_fixture_plot()
        narrative_arc = "孤独 → 发现温暖 → 被看见 → 被接纳"
        parsed = _parse_coffeefee_scenes(full_plot)
        characters = intake.characters_for_script or ["coffeefee", "dario"]
        outlines: list[PlotSceneOutline] = []
        for index, scene in enumerate(parsed, start=1):
            scene_id = f"scene_{index:03d}"
            scene_job = next((j for j in intake.scene_jobs if j.scene_id == scene_id), None)
            shot_hint = next((h for h in intake.scene_shot_hints if h.scene_id == scene_id), None)
            outlines.append(
                PlotSceneOutline(
                    scene_id=scene_id,
                    scene_order=index,
                    heading=scene["heading"],
                    story_text=scene["story_text"],
                    emotional_beat=(
                        "lonely isolation"
                        if index == 1
                        else "warmth and belonging"
                        if index >= len(parsed) - 1
                        else "curiosity and courage"
                    ),
                    characters=characters if index < len(parsed) else characters,
                    location=scene["location"],
                    time_of_day=scene["time_of_day"],
                    visual_style_hint=payload.style_notes or "3D anime character in photoreal environment",
                    scene_style_hint="cold blue exteriors shifting to warm amber interiors",
                    dialogue_beats=scene["dialogue_beats"],
                    dialogue_intent="spoken dialogue for subtitles and TTS",
                    camera_progression=(
                        shot_hint.camera_progression
                        if shot_hint
                        else "establish → push-in → emotional close"
                    ),
                    expected_shot_count=shot_hint.expected_shots if shot_hint else 2,
                    linked_scene_ref_id=scene_job.reference_path if scene_job else None,
                    linked_character_ids=characters,
                    needs_scene_image=scene_job is None or scene_job.reference_path is None,
                )
            )
        return full_plot, narrative_arc, outlines

    scene_count = _infer_scene_count(payload, intake)
    protagonist = intake.characters_for_script[0] if intake.characters_for_script else "protagonist"
    prompt = payload.raw_prompt.strip() or intake.script_brief
    style = payload.style_notes or payload.style_preset or "cinematic short-form vertical video"

    arc_beats = [
        ("setup", "introduce world and longing"),
        ("inciting", "something changes"),
        ("development", "character commits to action"),
        ("turn", "emotional shift"),
        ("climax", "peak feeling"),
        ("resolution", "quiet payoff"),
    ][:scene_count]

    outline_parts: list[str] = []
    outlines = []
    for index, (beat_name, beat_desc) in enumerate(arc_beats, start=1):
        scene_id = f"scene_{index:03d}"
        heading = f"SCENE {index} — {beat_name.upper()}"
        story_text = (
            f"{heading}\n\n"
            f"{protagonist} is in a concrete place tied to the user request: {prompt}\n\n"
            f"Beat: {beat_desc}. We see visible action, readable emotion, and staging that "
            f"advances the 30-second arc. Visual style: {style}.\n\n"
            f"Camera begins wide to orient the viewer, moves to medium coverage for action, "
            f"and finishes on a close beat that carries the emotion forward."
        )
        if index == scene_count:
            story_text += (
                f"\n\n{protagonist} reaches a small but clear emotional payoff that resolves "
                "the opening tension."
            )
        outline_parts.append(story_text)
        scene_job = next((j for j in intake.scene_jobs if j.scene_id == scene_id), None)
        shot_hint = next((h for h in intake.scene_shot_hints if h.scene_id == scene_id), None)
        outlines.append(
            PlotSceneOutline(
                scene_id=scene_id,
                scene_order=index,
                heading=heading,
                story_text=story_text,
                emotional_beat=beat_name,
                characters=intake.characters_for_script or [protagonist],
                location=f"Location derived from user prompt ({index})",
                time_of_day="night" if index <= 2 else "continuous",
                visual_style_hint=style,
                scene_style_hint=style,
                dialogue_intent="add concise spoken lines only where they deepen emotion",
                camera_progression=(
                    shot_hint.camera_progression
                    if shot_hint
                    else "wide establish → medium action → close emotional beat"
                ),
                expected_shot_count=shot_hint.expected_shots if shot_hint else 2,
                linked_scene_ref_id=scene_job.reference_path if scene_job else None,
                linked_character_ids=intake.characters_for_script or [protagonist],
                needs_scene_image=scene_job is None or scene_job.reference_path is None,
            )
        )

    full_plot = "\n\n---\n\n".join(outline_parts)
    narrative_arc = " → ".join(beat for beat, _ in arc_beats)
    return full_plot, narrative_arc, outlines


def _review_user_script(payload: GatewayPayload) -> list[str]:
    text = (payload.user_script_text or "").strip()
    gaps: list[str] = []
    if len(text) < 80:
        gaps.append("用户剧本过短，尚不足以作为完整剧情。")
    if not re.search(r"(CUT|场景|scene|镜|镜头|INT\.|EXT\.)", text, re.IGNORECASE):
        gaps.append("未检测到明确的场景或镜头划分。")
    if not re.search(r"(风格|style|色调|visual|画面)", text, re.IGNORECASE):
        gaps.append("缺少画面/场景风格描述。")
    return gaps


def _enrich_user_script_plot(
    payload: GatewayPayload,
    intake: IntakePlan,
    gaps: list[str],
) -> tuple[str, str, list[PlotSceneOutline]]:
    """Treat user script as base and expand into a complete plot document."""
    user_text = (payload.user_script_text or payload.raw_prompt or "").strip()
    supplements = [
        "补全每个场景的可视化动作与情绪变化",
        "明确镜头推进方式与台词意图",
        "统一 visual_style / scene_style",
    ]
    full_plot = (
        f"{user_text}\n\n"
        "[Plot Agent review — suggested supplements]\n"
        + "\n".join(f"- {item}" for item in supplements)
    )
    if gaps:
        full_plot += "\n\n[Plot gaps]\n" + "\n".join(f"- {g}" for g in gaps)

    scene_count = max(1, _infer_scene_count(payload, intake))
    outlines: list[PlotSceneOutline] = []
    for index in range(1, scene_count + 1):
        scene_id = f"scene_{index:03d}"
        story_text = (
            f"Scene {index} derived from user material:\n{user_text[:600]}\n\n"
            "Plot Agent note: expand this into concrete staging, visible action, "
            "and camera progression before Script JSON."
        )
        outlines.append(
            PlotSceneOutline(
                scene_id=scene_id,
                scene_order=index,
                heading=f"SCENE {index}",
                story_text=story_text,
                emotional_beat="development",
                characters=intake.characters_for_script or ["protagonist"],
                location="from user script",
                camera_progression="wide establish → medium → close",
                expected_shot_count=2,
                dialogue_intent="preserve user dialogue intent; add timing in Script stage",
                missing_notes=gaps if index == 1 else [],
            )
        )
    return full_plot, "user script → reviewed plot", outlines


def _build_plot_prompts(
    job: JobPaths,
    payload: GatewayPayload,
    intake: IntakePlan,
) -> tuple[str, str]:
    director = _load_rule(job, "DIRECTOR.md")
    master = _load_rule(job, "MASTER.md")
    system = (
        "You are the Plot Agent (剧情 Agent) for PIP. Your job is to produce a COMPLETE plot "
        "(完整剧情) — not a bullet outline. Write full scene prose with action, emotion, "
        "staging, dialogue intent, and camera progression. Output one strict JSON object matching "
        "the PlotPlan contract.\n\n"
        f"{director}\n\n{master}"
    )
    user = (
        f"User request:\n{payload.raw_prompt or intake.script_brief}\n\n"
        f"Characters: {', '.join(intake.characters_for_script) or 'infer from brief'}\n"
        f"Language: {payload.language}\n"
        f"Target duration: {payload.target_duration_sec or 30}s\n\n"
        "Requirements:\n"
        "1. full_plot must read like a complete short screenplay narrative (multiple scenes).\n"
        "2. Each scene_outlines[].story_text must be full prose for that scene, not one line.\n"
        "3. Include dialogue_beats where characters speak.\n"
        "4. Link scene_id scene_001.. sequentially; include camera_progression per scene.\n"
        "5. Set narrative_arc and visual_style_hint / scene_style_hint."
    )
    if payload.user_script_text:
        user += f"\n\nUser-provided material to review/expand:\n{payload.user_script_text}"
    return system, user


def _script_handoff(
    plan: PlotPlan,
    *,
    gaps: list[str],
    supplements: list[str],
) -> str:
    lines = [
        f"Plot mode: {plan.mode}",
        f"Narrative arc: {plan.narrative_arc}",
        f"Summary: {plan.plot_summary}",
        f"Visual style: {plan.visual_style_hint or 'see full plot'}",
        "",
        "=== FULL PLOT (complete narrative for Script Agent) ===",
        plan.full_plot,
        "",
        "=== PER-SCENE DETAIL ===",
    ]
    for outline in plan.scene_outlines:
        dialogue = (
            "\n".join(f"  {d.speaker}: {d.line}" for d in outline.dialogue_beats)
            or outline.dialogue_intent
            or "no dialogue"
        )
        lines.append(
            f"\n{outline.scene_id} | {outline.heading}\n"
            f"location={outline.location}; time={outline.time_of_day}; "
            f"emotion={outline.emotional_beat}\n"
            f"camera={outline.camera_progression}; shots≈{outline.expected_shot_count}\n"
            f"characters={', '.join(outline.characters)}\n"
            f"dialogue:\n{dialogue}\n"
            f"story:\n{outline.story_text}"
        )
    if gaps:
        lines.append("\nPlot review gaps:")
        lines.extend(f"- {gap}" for gap in gaps)
    if supplements:
        lines.append("\nSuggested supplements:")
        lines.extend(f"- {item}" for item in supplements)
    lines.append(
        "\nScript Agent: convert this COMPLETE plot into MASTER JSON. "
        "Do not invent a different story — normalize this plot into script.json fields."
    )
    return "\n".join(lines)


def run_plot_agent(
    job: JobPaths,
    payload: GatewayPayload,
    intake: IntakePlan,
    *,
    mock: bool,
    app_settings: Settings | None = None,
) -> PlotPlan:
    route: PlotRoute = intake.plot_route
    gaps: list[str] = []
    supplements: list[str] = []
    mode: str = "generated"

    if route == "review_plot" or (payload.has_script and payload.user_script_text):
        gaps = _review_user_script(payload) if payload.user_script_text else ["缺少完整剧本"]
        supplements = ["补全场景可视化、风格、镜头推进、台词意图"]
        if gaps:
            mode = "reviewed"
            full_plot, narrative_arc, outlines = _enrich_user_script_plot(payload, intake, gaps)
        else:
            mode = "from_user_script"
            full_plot = payload.user_script_text or ""
            narrative_arc = "from user script"
            _, _, outlines = _generate_full_plot_mock(payload, intake)
            if payload.user_script_text:
                outlines[0] = outlines[0].model_copy(
                    update={"story_text": payload.user_script_text, "heading": "USER SCRIPT"}
                )
    else:
        mode = "generated"
        if not payload.raw_prompt.strip():
            gaps.append("缺少可用于生成完整剧情的用户描述")
        full_plot, narrative_arc, outlines = _generate_full_plot_mock(payload, intake)

    if not mock:
        cfg = app_settings or settings
        if not cfg.deepseek_api_key:
            raise ValueError(
                "DEEPSEEK_API_KEY is required for Plot Agent. Use --mock for local fixtures."
            )
        system, user = _build_plot_prompts(job, payload, intake)
        data = deepseek_chat_json(
            api_key=cfg.deepseek_api_key,
            base_url=cfg.deepseek_base_url,
            model=cfg.deepseek_model,
            system_prompt=system,
            user_prompt=user,
        )
        plan = PlotPlan.model_validate({**data, "job_id": job.job_id})
        plan = plan.model_copy(
            update={
                "script_handoff": _script_handoff(
                    plan, gaps=plan.gaps_found or gaps, supplements=plan.supplements or supplements
                )
            }
        )
        write_json(job.plot_plan_path, plan)
        _write_plot_narrative(job, plan.full_plot)
        return plan

    plot_summary = payload.raw_prompt.strip() or intake.script_brief[:500]
    draft = PlotPlan(
        job_id=job.job_id,
        mode=mode,  # type: ignore[arg-type]
        plot_summary=plot_summary,
        narrative_arc=narrative_arc,
        full_plot=full_plot,
        visual_style_hint=payload.style_notes or payload.style_preset,
        scene_style_hint=payload.style_notes or payload.style_preset,
        scene_outlines=outlines,
        gaps_found=gaps,
        supplements=supplements,
        ready_for_script=len(gaps) == 0 or mock,
        script_handoff="pending",
    )
    plan = draft.model_copy(
        update={
            "script_handoff": _script_handoff(
                draft, gaps=gaps, supplements=supplements
            )
        }
    )
    write_json(job.plot_plan_path, plan)
    _write_plot_narrative(job, plan.full_plot)
    return plan


def _write_plot_narrative(job: JobPaths, full_plot: str) -> None:
    path = job.plot_dir / "plot_narrative.txt"
    path.write_text(full_plot, encoding="utf-8")
