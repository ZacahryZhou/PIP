# Music Library Rules / 配乐库规则

## Purpose / 目的

Map `script.music_mood` and `script.music_bpm` to **local royalty-free files**.

把 `script.music_mood` 和 `script.music_bpm` 映射到 **本地免版税文件**。

Assets live under: `assets/music/`

素材目录：`assets/music/`

---

## BGM Mode / 配乐模式

Controlled by `.env` → `PIP_BGM_MODE`:

由 `.env` 的 `PIP_BGM_MODE` 控制：

| Mode | How | When to use |
|---|---|---|
| **`fal`** (recommended for you) | Generate from `script.music_mood` + `script.music_bpm` via `FAL_BGM_MODEL` | Each job gets custom BGM; no manual mp3 hunt |
| **`library`** | Pick file from table below in `assets/music/` | Offline, zero extra API cost, fixed tracks |

**Recommended for fal.ai users:** `PIP_BGM_MODE=fal` + `FAL_BGM_MODEL=fal-ai/minimax-music/v2.6`

**走 fal 的用户推荐：** 按文本生成，不必事先找 mp3。

Prompt template (instrumental when dialogue exists):

有对白时用纯器乐 prompt 模板：

```text
Instrumental cinematic underscore, {music_mood}, approximately {music_bpm} BPM,
no vocals, no lyrics, suitable for short film background
```

---

## Selection Algorithm (library mode only) / 选曲算法（仅 library 模式）

1. Read `script.music_mood` (string, case-insensitive).
   读取 `script.music_mood`（不区分大小写）。
2. Read `script.music_bpm` (integer).
   读取 `script.music_bpm`（整数）。
3. Find the best row in the catalog below where:
   在下方目录中找最佳匹配行：
   - `mood_tags` contains a token from `music_mood`, **and**
   - `bpm_min <= music_bpm <= bpm_max`
4. If multiple matches: pick the row with the **smallest BPM distance** to `music_bpm`.
   若多行匹配：选与 `music_bpm` **BPM 差最小** 的行。
5. If no match: use **`fallback_neutral_loop`**.
   若无匹配：使用 **`fallback_neutral_loop`**。

---

## Catalog / 目录

Add your own MP3/WAV files to `assets/music/` using these IDs.

请把 MP3/WAV 放到 `assets/music/`，并使用下列 ID 命名或登记。

| asset_id | file | mood_tags | bpm_min | bpm_max | notes |
|---|---|---|---|---|---|
| `tense_electronic_128` | `tense_electronic_128.mp3` | tense, electronic, action, chase | 118 | 138 | Cyberpunk / thriller |
| `calm_ambient_90` | `calm_ambient_90.mp3` | calm, ambient, normal, peaceful | 80 | 100 | Soft pads |
| `dream_ethereal_72` | `dream_ethereal_72.mp3` | dream, memory, ethereal, soft | 60 | 84 | Slow dissolve scenes |
| `action_percussion_140` | `action_percussion_140.mp3` | action, tense, percussion, run | 130 | 150 | High energy |
| `fallback_neutral_loop` | `fallback_neutral_loop.mp3` | *any* | 40 | 220 | Always available |

**Before first quality test:** place at least `fallback_neutral_loop.mp3` in `assets/music/`.

**第一次质量测试前：** 至少放入 `fallback_neutral_loop.mp3`。

---

## Usage Rules / 使用规则

- Loop seamlessly if track is shorter than final video.
- 若曲目短于成片，无缝循环。
- Hard-trim at `final_duration_sec`; do not add silence tail unless fade requires it.
- 在 `final_duration_sec` 硬切；除非淡出需要，不要加静音尾。
- Do not change BGM mid-video in MVP (one mood per job).
- MVP 不要在成片中间换 BGM（每个任务一种情绪）。
- License: user must own redistribution rights for Telegram delivery.
- 许可：用户必须拥有 Telegram 回传所需的重分发权。

---

## Script Agent Guidance / 剧本 Agent 指引

When writing `music_mood` and `music_bpm`:

写 `music_mood` 和 `music_bpm` 时：

- Prefer tags that exist in the catalog (`tense`, `electronic`, `calm`, `dream`, `action`).
- 优先使用目录里有的 tag（`tense`、`electronic`、`calm`、`dream`、`action`）。
- Keep BPM inside the matched row when possible (e.g. tense chase → 128).
- 尽量让 BPM 落在匹配行区间内（如紧张追逐 → 128）。
- If the story is silent-movie style, set `music_mood` to `calm ambient` and leave dialogue empty.
- 若为无声电影风格，设 `music_mood=calm ambient` 且 dialogue 留空。
