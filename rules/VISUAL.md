# Visual & Color Rules / 视觉与色彩规则

## Purpose / 目的

Keep **color, lighting, and style consistent** across all shots in one job.

保证同一任务内所有镜头的 **色彩、光线、风格一致**。

Used by: Script Agent, Storyboard Agent, video prompt builders.

使用者：剧本 Agent、分镜 Agent、视频 prompt 构建器。

---

## Field Roles / 字段分工

| Field 字段 | Level 层级 | Role 作用 |
|---|---|---|
| `visual_style` | `script.json` top | Overall look: genre, era, lens feel (e.g. cinematic cyberpunk) |
| `color_tone` | `script.json` top | Palette + lighting mood (e.g. neon blue, magenta rim, wet reflections) |
| `camera_language` | `script.json` top | Global camera grammar (handheld, slow push-in, etc.) |
| `mood` | scene / shot | Emotional color for transitions and pacing |
| `style_tags` | shot | Short tags appended to video prompts |

**Rule:** `color_tone` is **global**. Every shot prompt must **repeat or inherit** it unless a scene explicitly breaks tone (dream/memory only).

**规则：** `color_tone` 是 **全局** 的。每个镜头 prompt 必须 **重复或继承**，除非场景明确破调（仅 dream/memory）。

---

## Script Agent / 剧本 Agent

When filling `color_tone`:

填写 `color_tone` 时：

- Name **3–5 concrete visual anchors**: key light color, shadow color, accent, surface (wet, dusty, metallic).
- 写 **3–5 个具体视觉锚点**：主光色、阴影色、点缀色、材质（湿、尘、金属）。
- Tie `color_tone` to `visual_style` (do not contradict).
- `color_tone` 必须与 `visual_style` 一致，不可矛盾。
- Avoid vague words alone ("beautiful", "cool"). Replace with visible cues.
- 避免空词（「好看」「很酷」），换成可见线索。

Bad 错误:

```text
color_tone: nice colors
```

Good 正确:

```text
color_tone: neon blue and magenta rim light on wet asphalt, deep teal shadows, warm skin highlight separation
```

---

## Storyboard Agent / 分镜 Agent

For each shot's implied video prompt (subject + action + character_prompts):

每个镜头的视频 prompt（subject + action + character_prompts）：

1. Append a **`color_anchor`** clause copied from `script.color_tone` (shortened if needed).
   追加来自 `script.color_tone` 的 **`color_anchor`** 短句。
2. Per-shot lighting may vary **intensity**, not **palette**, except `dream` / `memory` moods.
   每镜光线可变 **强度**，不可变 **色板**，`dream` / `memory` 除外。
3. Keep skin tones natural; avoid green/magenta cast on faces unless story requires it.
   肤色保持自然；除非剧情需要，避免脸部偏绿/偏洋红。

Example shot prompt tail:

镜头 prompt 尾部示例：

```text
... neon blue and magenta rim on wet surfaces, deep teal shadows, cinematic contrast
```

---

## Post-production Color / 后期调色

MVP default: **no LUT / no color grade in FFmpeg**.

MVP 默认：**FFmpeg 不做 LUT / 不做调色**。

Consistency comes from prompts + QC rejection of obvious drift.

一致性靠 prompt + QC 拒绝明显色偏。

V2 optional: single global LUT pass after assembly (document in `POSTPROD.md` when implemented).

V2 可选：合成后统一 LUT（实现后再写入 `POSTPROD.md`）。

---

## QC Visual Checks / 画面质检

Flag for regeneration if:

以下情况应标记重生成：

- Shot looks like a different film stock from neighbors (warm vs cold without mood reason).
- 与相邻镜头像不同胶片（无 mood 理由的冷暖跳变）。
- Character outfit or face identity drifts from `CHARACTERS.md`.
- 角色服装或脸部身份偏离 `CHARACTERS.md`。
- Unreadable text or broken geometry (existing QC rules).
- 文字不可读或几何破碎（现有 QC 规则）。
