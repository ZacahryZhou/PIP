# Audio Rules / 音频规则

## Purpose / 目的

Define how PIP builds the **final soundtrack** for every job.

定义 PIP 如何为每个任务构建 **最终音轨**。

Read together with:

请与以下文件一起阅读：

- `POSTPROD.md` — assembly order and FFmpeg stages
- `MUSIC_LIBRARY.md` — BGM asset selection
- `SUBTITLE.md` — on-screen text timing
- `PROVIDERS.md` — fal.ai and other API adapters
- `CHARACTERS.md` — voice style and TTS mapping

---

## Core Strategy / 核心策略

PIP uses a **split audio pipeline**:

PIP 使用 **分离式音频流水线**：

| Layer 层级 | Source 来源 | Rule 规则 |
|---|---|---|
| **Picture 画面** | fal.ai video models (Kling, Seedance, etc.) | Generate **silent or discard model audio** |
| **Dialogue / VO 对白** | TTS API (via fal.ai or direct provider) | Text from `script.json` / `shots.json` dialogue only |
| **BGM 背景音乐** | Local library in `assets/music/` | Match `script.music_mood` + `script.music_bpm` |
| **SFX 音效** | MVP: skip | V2: optional asset library |

**Do not** rely on video-model-generated speech as the final dialogue track.

**不要**把视频模型随机生成的说话声当作最终对白。

Reason: model speech is unstable, hard to subtitle, and inconsistent across shots.

原因：模型对白不稳定、难做字幕、镜头之间不一致。

---

## Video Clip Audio / 视频片段音频

1. Provider adapters must treat clip output as **picture-first**.
   适配器必须把 clip 输出当作 **画面优先**。
2. If the API returns audio, post-production **strips or replaces** it before final mix.
   若 API 返回音轨，后期在最终混音前 **剥离或覆盖**。
3. Never merge per-clip model audio into one continuous soundtrack.
   不要把每个 clip 的模型音轨拼成一条连续音轨。
4. Ambient sounds from models may be used only in MVP-off mode (not default).
   模型环境声仅在非默认的 MVP-off 模式可用。

Default for quality testing: **`mute_source_clips=true`**.

质量测试默认：**`mute_source_clips=true`**。

---

## Dialogue / 对白

### Text source / 文本来源

Priority order:

优先级：

1. Shot-level `dialogue` in `shots.json` (wins if present)
   镜头级 `shots.json` dialogue（存在则优先）
2. Scene-level `dialogue` in `script.json`, mapped onto shots by `scene_id`
   场景级 `script.json` dialogue，按 `scene_id` 映射到镜头
3. If no dialogue anywhere: skip TTS and VO track
   全程无台词：跳过 TTS 与 VO 轨

### Timing / 时间轴

- Dialogue `start_sec` / `end_sec` are relative to the **scene start**, not the full video.
- 对白 `start_sec` / `end_sec` 相对 **场景起点**，不是整条成片。
- Post-production converts them to **global timeline** using `timeline.json` shot offsets.
- 后期用 `timeline.json` 的镜头偏移换算成 **全局时间轴**。
- Clamp VO inside the shot's real `[start_sec, end_sec]` on the final timeline.
- VO 必须限制在该镜头在成片上的真实时间范围内。

### TTS generation / TTS 生成

- One WAV segment per dialogue line (or one merged VO track per job).
- 每条台词一段 WAV，或每个任务合并一条 VO 轨。
- Use character voice mapping from `CHARACTERS.md`.
- 使用 `CHARACTERS.md` 中的角色音色映射。
- Match `voice_or_dialogue_style` in **word choice**, not speaking speed alone.
- `voice_or_dialogue_style` 主要约束 **用词风格**，不只是语速。
- If TTS fails for one line: retry once, then burn subtitles only (no VO) for that line.
- 某条 TTS 失败：重试一次，仍失败则该条仅烧字幕、不配音。

### Lip sync / 口型

- MVP: **no lip sync required**. VO + subtitles is acceptable.
- MVP：**不要求口型同步**。配音 + 字幕即可。
- Do not block delivery waiting for lip-sync models.
- 不要因口型模型未完成而阻塞出片。

---

## Background Music / 背景音乐

- Select asset using `MUSIC_LIBRARY.md`.
- 按 `MUSIC_LIBRARY.md` 选曲。
- Trim or loop to exact `timeline.json.final_duration_sec`.
- 裁剪或循环至 `timeline.json.final_duration_sec` 精确时长。
- Single continuous BGM across the whole video (not per-shot tracks).
- 整条视频 **一条连续 BGM**，不要每镜一条。
- Default mix levels (relative):
- 默认混音电平（相对值）：

| Track 轨道 | Level 电平 |
|---|---|
| BGM (no dialogue) | 100% |
| BGM (during dialogue) | 35% (ducking) |
| VO / dialogue | 100% |

- Ending fade: last **1.5s** BGM fade-out via FFmpeg `afade`.
- 结尾淡出：最后 **1.5 秒** BGM 用 FFmpeg `afade`。

---

## Sound Effects / 音效

MVP default: **disabled**.

MVP 默认：**关闭**。

If enabled later:

后续若开启：

- Use only royalty-free assets under `assets/sfx/`.
- 仅使用 `assets/sfx/` 下免版税素材。
- Max 2 SFX events per 30s video unless user asks for more.
- 30 秒视频默认最多 2 个 SFX，除非用户要求更多。

---

## Artifacts / 产物

Post-production audio folder: `audio/`

| File | Meaning 含义 |
|---|---|
| `audio/vo_manifest.json` | Dialogue lines, TTS provider, paths, global timestamps |
| `audio/vo_track.wav` | Merged dialogue track (optional) |
| `audio/bgm_track.wav` | Trimmed BGM |
| `audio/mix_report.json` | Levels, ducking, fade, errors |
| `final.mp4` | Video + mixed audio (see `POSTPROD.md`) |

---

## QC Checks / 音频质检

Before marking job `delivered`:

交付前检查：

- `final.mp4` has an audio stream.
- `final.mp4` 必须有音频流。
- If dialogue exists in script: either VO present **or** subtitles burned in.
- 若剧本有台词：必须有 VO **或** 已烧录字幕。
- BGM must not clip (peak below -1 dBTP target for MVP).
- BGM 不得爆音（MVP 目标峰值低于 -1 dBTP）。
- No dialogue line starts before its shot or ends after its shot on the global timeline.
- 任何对白不得早于其镜头开始或晚于其镜头结束。

See also `SUBTITLE.md` and `POSTPROD.md`.

另见 `SUBTITLE.md` 与 `POSTPROD.md`。
