# Seedance Provider Notes / Seedance 模型说明

## Best For / 适合场景

- Character-heavy shots.
- 人物占比高的镜头。
- High-motion action.
- 强动作镜头。
- Shots where body movement consistency matters.
- 需要人物动作一致性的镜头。

## MVP Adapter Requirements / MVP 适配器要求

- Accept `shot_id`, `duration_sec`, `character_prompts`, `action`, and `style`.
- 接收 `shot_id`、`duration_sec`、`character_prompts`、`action` 和 `style`。
- Return local mp4 path.
- 返回本地 mp4 路径。
- Report provider request ID if available.
- 如可用，记录模型请求 ID。

## Adapter Input / 适配器输入

The provider adapter should receive a normalized internal request, not raw `shots.json`.

模型适配器应接收标准化内部请求，而不是直接读取原始 `shots.json`。

```json
{
  "job_id": "job_20260528_173000",
  "shot_id": "shot_001",
  "duration_sec": 4,
  "prompt": "cinematic shot prompt",
  "negative_prompt": "distorted face, extra limbs",
  "character_prompts": ["hero: determined face, athletic build"],
  "motion_intensity": "high",
  "target_resolution": "1920x1080",
  "target_fps": 24,
  "output_path": "storage/jobs/.../clips/raw/shot_001_seedance_attempt_1.mp4"
}
```

## Prompt Guidance / Prompt 指南

- Put character identity before action details.
- 先写角色身份，再写动作细节。
- Include clothing and movement style in every character shot.
- 每个人物镜头都包含服装和动作风格。
- Keep camera motion concrete and short.
- 运镜描述要具体且简短。
- Include negative prompt terms from `CHARACTERS.md`.
- 包含 `CHARACTERS.md` 中的 negative prompt。

## Failure Handling / 失败处理

Seedance failures should be categorized as:

Seedance 失败应分类为：

- `provider_timeout`
- `provider_rejected_prompt`
- `provider_rate_limited`
- `provider_generation_failed`
- `download_failed`
- `invalid_media`

The adapter must return structured error data so the generation report can decide whether to retry or fallback to Kling.

适配器必须返回结构化错误数据，方便生成报告决定重试或切换 Kling。

