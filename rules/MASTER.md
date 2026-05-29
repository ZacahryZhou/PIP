# MASTER Rules / 全局规则

## Purpose / 目的

This file is injected into the Script Agent prompt for every job.

此文件会在每次任务中注入剧本 Agent 的 prompt。

## Script Requirements / 剧本要求

- Output strict JSON only.
- 只输出严格 JSON。
- Keep total duration between 15 and 45 seconds for MVP.
- MVP 总时长控制在 15 到 45 秒。
- Include narrative arc, visual style, color tone, music mood, BPM, camera language, characters in use, total duration, and scene list.
- 必须包含叙事弧线、视觉风格、色调、音乐情绪、BPM、镜头语言、使用角色、总时长和场景列表。
- Make each scene visually concrete enough for video generation.
- 每个场景必须足够具体，方便视频模型生成。

## Safety / 安全规则

- Do not include illegal, sexual, hateful, or private personal content.
- 不生成违法、色情、仇恨或私人敏感内容。
- Avoid copyrighted characters unless the user owns the rights.
- 避免使用受版权保护角色，除非用户拥有授权。

## Output Contract / 输出契约

The Script Agent must return one JSON object with exactly these top-level fields:

剧本 Agent 必须返回一个 JSON object，顶层字段如下：

```json
{
  "narrative_arc": "setup -> development -> climax -> ending",
  "visual_style": "cinematic realism",
  "color_tone": "warm gold and deep shadow",
  "music_mood": "tense electronic",
  "music_bpm": 128,
  "camera_language": "handheld tracking, slow push-in, wide establishing shots",
  "characters_in_use": ["hero"],
  "total_duration_sec": 30,
  "scene_list": []
}
```

## Scene Contract / 场景契约

Each item in `scene_list` must include:

`scene_list` 中的每个场景必须包含：

- `scene_id`: stable ID such as `scene_001`.
- `scene_id`：稳定 ID，例如 `scene_001`。
- `duration_sec`: target scene duration.
- `duration_sec`：目标场景时长。
- `location`: concrete visual location.
- `location`：具体可视化地点。
- `time_of_day`: morning, night, sunset, interior, etc.
- `time_of_day`：早晨、夜晚、日落、室内等。
- `characters`: character IDs from `CHARACTERS.md`.
- `characters`：来自 `CHARACTERS.md` 的角色 ID。
- `action_summary`: what visibly happens.
- `action_summary`：画面中实际发生的动作。
- `dialogue`: optional dialogue lines for subtitles.
- `dialogue`：可选台词，用于字幕。
- `mood`: one of `action`, `tense`, `calm`, `normal`, `dream`, `memory`.
- `mood`：取值为 `action`、`tense`、`calm`、`normal`、`dream`、`memory`。
- `camera_notes`: camera intent for this scene.
- `camera_notes`：该场景的镜头意图。

Example:

示例：

```json
{
  "scene_id": "scene_001",
  "duration_sec": 8,
  "location": "rainy neon alley",
  "time_of_day": "night",
  "characters": ["hero"],
  "action_summary": "hero runs past flickering signs while looking back",
  "dialogue": [
    {
      "speaker": "hero",
      "text": "Keep moving.",
      "start_sec": 2.0,
      "end_sec": 3.5
    }
  ],
  "mood": "tense",
  "camera_notes": "low handheld tracking shot"
}
```

## Duration Rules / 时长规则

- `total_duration_sec` must equal the sum of all scene durations within ±1 second.
- `total_duration_sec` 必须与所有场景时长总和相差不超过 1 秒。
- No scene should exceed 12 seconds in the MVP.
- MVP 中单个场景不应超过 12 秒。
- If the user asks for a very long video, compress the idea into 15-45 seconds unless the orchestrator explicitly overrides the limit.
- 如果用户要求很长的视频，除非主控流程明确覆盖限制，否则压缩到 15-45 秒。

## Character Rules / 角色规则

- Use only character IDs that exist in `CHARACTERS.md`, unless the user clearly creates a new generic character.
- 只能使用 `CHARACTERS.md` 中存在的角色 ID，除非用户明确创建新的通用角色。
- Keep character identity consistent across scenes.
- 保持角色在所有场景中的身份一致。
- Do not describe copyrighted characters by name. Convert them into original archetypes.
- 不要直接使用受版权保护角色名，应转换为原创角色原型。

