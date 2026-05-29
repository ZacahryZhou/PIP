# Wan T2V Provider Notes / Wan T2V 模型说明

## Best For / 适合场景

- Simple scene generation.
- 简单场景生成。
- Low-cost batch shots.
- 低成本批量镜头。
- Background, establishing, or non-character shots.
- 背景、空镜、非人物镜头。

## MVP Adapter Requirements / MVP 适配器要求

- Accept compact prompt and duration.
- 接收简洁 prompt 和时长。
- Prefer simple shots with low motion.
- 优先处理低运动简单镜头。
- Use Kling fallback if output fails QC.
- 如果输出质检失败，使用 Kling 备用。

## Adapter Input / 适配器输入

```json
{
  "job_id": "job_20260528_173000",
  "shot_id": "shot_003",
  "duration_sec": 4,
  "prompt": "quiet wide shot of empty street at dawn",
  "negative_prompt": "heavy motion, distorted buildings, flicker",
  "motion_intensity": "low",
  "target_resolution": "1920x1080",
  "output_path": "storage/jobs/.../clips/raw/shot_003_wan_t2v_attempt_1.mp4"
}
```

## Prompt Guidance / Prompt 指南

- Keep prompts short and concrete.
- prompt 保持简短具体。
- Prefer single-subject environment shots.
- 优先用于单主体环境镜头。
- Avoid complex character motion.
- 避免复杂人物动作。
- Avoid dense dialogue or text appearing in frame.
- 避免画面中出现大量对白或文字。

## Best MVP Use Cases / MVP 最适合场景

- Establishing shots.
- 建立镜头。
- Background or atmosphere clips.
- 背景或氛围片段。
- Low-motion cutaways.
- 低运动插入镜头。
- Simple non-character scenes.
- 简单非人物场景。

## QC Expectations / 质检预期

Wan T2V output should be treated as low-cost but more likely to need QC fallback.

Wan T2V 应视为低成本模型，但更可能需要质检备用生成。

Common QC risks:

常见质检风险：

- Duration mismatch.
- 时长不匹配。
- Flicker.
- 闪烁。
- Low detail.
- 细节不足。
- Inconsistent resolution.
- 分辨率不一致。

