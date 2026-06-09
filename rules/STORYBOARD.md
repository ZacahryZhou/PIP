# Storyboard Rules / 分镜规则

## Split Rules / 拆分规则

**Scene-first workflow:** iterate `script.scene_list` in `scene_order`; only split shots inside each scene.

**场景优先流程：** 按 `scene_order` 遍历 `script.scene_list`；只在每个场景内部拆分镜头。

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
- `shot_size`: one of `EWS`, `WS`, `MLS`, `MS`, `MCU`, `CU`, `ECU`
- `shot_size`：景别，取 `EWS`、`WS`、`MLS`、`MS`、`MCU`、`CU`、`ECU` 之一
- `camera_angle`: e.g. eye level, low angle, high angle, over-shoulder
- `camera_angle`：机位，如平视、仰拍、俯拍、过肩
- `camera_move`
- `action`
- `facial_expression`: visible face/body expression when a character is present
- `facial_expression`：有角色时必须写可见表情（眉、眼、嘴、呼吸等）
- `character_gaze`: where the character looks (forward, off-screen left, upward, etc.)
- `character_gaze`：角色视线方向
- `blocking`: character position and movement in the frame
- `blocking`：角色在画面中的位置与走位
- `mood`
- `scene_type`
- `motion_intensity`
- `has_characters`
- `character_prompts`
- `generation_mode`: `t2v` or `i2v` — you decide per shot (see below)
- `generation_mode`：`t2v` 或 `i2v` — 由你按镜头判断（见下）
- `generation_mode_reason`: one English sentence explaining the choice
- `generation_mode_reason`：一句英文说明为何选该模式
- `preferred_model`
- `fallback_model`
- `scene_order`, `shot_order_in_scene`: ordering inside script scenes.
- `shot_continuity_from_previous`: required for every shot after the first in a scene.
- `camera_progression`, `emotion_transition`, `preview_desc`, `keyframe_start_desc`, `keyframe_end_desc`.
- `visual_style`, `color_palette`: inherit from parent scene in `script.json`.
- `scene_reference_id`, `scene_reference_image_path`, `character_reference_image_paths` when gateway assets exist.

## Generation Mode / 生成模式（Storyboard Agent 判断）

You must choose **`t2v`** (text-to-video) or **`i2v`** (keyframe image then image-to-video):

必须为每个镜头选择 **`t2v`**（文生视频）或 **`i2v`**（关键帧图再图生视频）：

| Choose `i2v` | Choose `t2v` |
|---|---|
| CU / MCU / MS with visible character performance | `motion_intensity=high` chase, sprint, large movement |
| Shots with dialogue close-ups | EWS / WS establishing, environment-first |
| `motion_intensity` low or medium + face matters | Complex travel / whip pan / drone sweep |

Read `KEYFRAME.md` for i2v pipeline details.

i2v 流程细节见 `KEYFRAME.md`。

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
      "shot_size": "WS",
      "camera_angle": "low angle from behind",
      "camera_move": "low handheld tracking shot",
      "action": "hero sprints past flickering signs and looks back",
      "facial_expression": "jaw clenched, eyes wide scanning for escape",
      "character_gaze": "forward with quick glance backward",
      "blocking": "hero enters frame left, dominates lower third, neon behind",
      "mood": "tense",
      "scene_type": "realistic",
      "motion_intensity": "high",
      "has_characters": true,
      "character_ids": ["hero"],
      "character_prompts": ["hero: determined face, athletic build, dark practical jacket"],
      "style_tags": ["cinematic", "night", "rain", "neon"],
      "dialogue": [],
      "generation_mode": "t2v",
      "generation_mode_reason": "high motion wide shot suits text-to-video",
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
- If a shot contains no character, `has_characters=false`, `character_ids=[]`, `character_prompts=[]`, and set `facial_expression`, `character_gaze`, `blocking` to `"n/a"`.
- 如果镜头没有角色，则 `has_characters=false`，且 `facial_expression`、`character_gaze`、`blocking` 填 `"n/a"`。
- Within each scene, prefer at least two different `shot_size` values when the scene is longer than 5 seconds.
- 同一场景超过 5 秒时，尽量至少使用两种不同 `shot_size`。

