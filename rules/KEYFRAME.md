# Keyframe Rules / 关键帧规则

## Purpose / 目的

For shots with `generation_mode: "i2v"`, generate one still image first, then animate it with image-to-video.

对 `generation_mode: "i2v"` 的镜头，先生成静帧，再用图生视频。

---

## When to use i2v / 何时用 i2v

The **Storyboard Agent (DeepSeek)** sets `generation_mode` per shot using:

**分镜 Agent（DeepSeek）** 按镜头设置 `generation_mode`：

| Prefer `i2v` | Prefer `t2v` |
|---|---|
| CU / MCU / MS with characters | `motion_intensity=high` chase or sprint |
| Dialogue close-ups | EWS / WS establishing |
| Low/medium motion performance | Complex camera move + large displacement |
| Need stable face / composition | Environment-only wide shots |

Always set `generation_mode_reason` in English for MVP.

MVP 理由字段用英文。

---

## Keyframe model / 关键帧模型

- Provider: fal.ai **`fal-ai/nano-banana-pro`**
- Input: `build_keyframe_prompt()` from shot + script color/style
- Output: `keyframes/{shot_id}_keyframe.png`
- Aspect ratio: `16:9` for MVP

---

## Video step after keyframe / 关键帧之后的视频

- Use the same routed model (Kling / Seedance) **image-to-video** endpoint
- Pass `start_image_url` or local upload from keyframe PNG
- Duration from `shot.duration_sec`
- Mute model audio (`AUDIO.md`)

---

## Skip keyframe / 跳过

If `generation_mode` is `t2v`, keyframe stage writes `status: skipped` for that shot.

若为 `t2v`，关键帧阶段对该镜记 `status: skipped`。
