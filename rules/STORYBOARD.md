# Storyboard Rules / 分镜规则

## Split Rules / 拆分规则

Split a scene into a new shot when any of these conditions are true:

当满足以下任一条件时，拆成新镜头：

1. Camera movement changes.
   运镜变化。
2. Subject or character changes.
   主体或角色变化。
3. Location changes.
   场景地点变化。
4. Continuous action exceeds 8 seconds.
   连续动作超过 8 秒。

## Shot Requirements / 分镜要求

Each shot must include:

每个镜头必须包含：

- `shot_id`
- `duration_sec`
- `subject`
- `camera_move`
- `action`
- `mood`
- `scene_type`
- `motion_intensity`
- `has_characters`
- `character_prompts`
- `preferred_model`
- `fallback_model`

## Important Boundary / 重要边界

`preferred_model` and `fallback_model` are placeholders in `shots.json`. The Storyboard Agent must leave them as `null` unless the orchestrator explicitly asks for a manual override.

`preferred_model` 和 `fallback_model` 在 `shots.json` 中只是占位字段。除非主控流程明确要求人工覆盖，否则分镜 Agent 必须将它们保留为 `null`。

The Routing Agent is the only authoritative owner of model selection.

Routing Agent 是唯一拥有最终模型选择权的层。

## Output Contract / 输出契约

The Storyboard Agent must return strict JSON:

分镜 Agent 必须返回严格 JSON：

```json
{
  "shots": [
    {
      "shot_id": "shot_001",
      "scene_id": "scene_001",
      "duration_sec": 4,
      "subject": "hero running through rainy neon alley",
      "camera_move": "low handheld tracking shot",
      "action": "hero sprints past flickering signs and looks back",
      "mood": "tense",
      "scene_type": "realistic",
      "motion_intensity": "high",
      "has_characters": true,
      "character_ids": ["hero"],
      "character_prompts": ["hero: determined face, athletic build, dark practical jacket"],
      "style_tags": ["cinematic", "night", "rain", "neon"],
      "dialogue": [],
      "preferred_model": null,
      "fallback_model": null
    }
  ]
}
```

## Field Rules / 字段规则

- `shot_id` must be sequential: `shot_001`, `shot_002`, `shot_003`.
- `shot_id` 必须顺序递增：`shot_001`、`shot_002`、`shot_003`。
- `scene_id` must match a scene from `script.json`.
- `scene_id` 必须对应 `script.json` 中的场景。
- `duration_sec` must be greater than 0 and no more than 8.
- `duration_sec` 必须大于 0，且不超过 8 秒。
- `mood` must use values compatible with `POSTPROD.md`.
- `mood` 必须使用 `POSTPROD.md` 支持的值。
- `scene_type` must be one of `realistic`, `simple`, `creative`, `abstract`.
- `scene_type` 必须是 `realistic`、`simple`、`creative`、`abstract` 之一。
- `motion_intensity` must be one of `low`, `medium`, `high`.
- `motion_intensity` 必须是 `low`、`medium`、`high` 之一。
- `style_tags` should be compact strings used by generation prompts and routing.
- `style_tags` 应该是用于生成 prompt 和路由判断的简短标签。

## Duration Math / 时长计算

- The sum of shot durations for a scene must match the parent scene duration within ±0.5 seconds.
- 同一场景下所有镜头时长总和必须与父场景时长相差不超过 0.5 秒。
- The sum of all shot durations must match `script.total_duration_sec` within ±1 second.
- 所有镜头时长总和必须与 `script.total_duration_sec` 相差不超过 1 秒。
- If a scene is longer than 8 seconds and no other split rule applies, split by time into natural action beats.
- 如果某场景超过 8 秒且没有其他拆分条件，则按自然动作节奏拆分。

## Character Injection / 角色注入

- If `has_characters=true`, `character_ids` must not be empty.
- 如果 `has_characters=true`，`character_ids` 不得为空。
- Each `character_id` must be resolved to a visual prompt from `CHARACTERS.md`.
- 每个 `character_id` 都必须从 `CHARACTERS.md` 解析出视觉描述。
- Character prompts must emphasize visible identity, clothing, movement style, and negative prompt.
- 角色 prompt 必须强调可见身份、服装、动作风格和 negative prompt。
- If a shot contains no character, `has_characters=false`, `character_ids=[]`, and `character_prompts=[]`.
- 如果镜头没有角色，则 `has_characters=false`、`character_ids=[]`、`character_prompts=[]`。

