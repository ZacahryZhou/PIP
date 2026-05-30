# Provider Rules / 模型与 API 规则

## Purpose / 目的

How PIP calls external APIs — especially **fal.ai** as the unified gateway.

PIP 如何调用外部 API —— 尤其是 **fal.ai** 作为统一网关。

Implementation lives in `src/video_pipeline/providers/` (not in rules).

实现代码在 `src/video_pipeline/providers/`（不在 rules 里）。

---

## fal.ai Gateway / fal.ai 网关

Recommended MVP path:

推荐 MVP 路径：

| Capability 能力 | fal.ai model examples 示例 | PIP stage 阶段 |
|---|---|---|
| Text-to-video 文生视频 | Kling, Seedance (or fal-hosted equivalents) | Generation |
| Text-to-speech 文本转语音 | fal TTS endpoints or routed provider | Audio / VO |
| Optional image refs 可选参考图 | future character consistency | V2 |

Environment variables (local `.env` only):

环境变量（仅本地 `.env`）：

```env
FAL_KEY=
# Optional overrides / 可选覆盖
FAL_VIDEO_MODEL_KLING=
FAL_VIDEO_MODEL_SEEDANCE=
FAL_TTS_MODEL=
```

**Never** commit keys. **Do not** paste keys in chat.

**切勿**提交 Key。**不要**在聊天里粘贴 Key。

---

## Video Providers / 视频模型

### Input contract / 输入契约

Adapters receive normalized internal requests (see `models/kling.md`, `models/seedance.md`):

适配器接收标准化内部请求（见 `models/kling.md`、`models/seedance.md`）：

- Built from `shots.json` + `script.json` + `VISUAL.md` color anchor
- 由 `shots.json` + `script.json` + `VISUAL.md` 色彩锚点构建
- Include negative prompts from shot + character library
- 包含镜头与角色库的 negative prompt

### Output contract / 输出契约

- Save to `clips/raw/{shot_id}_{model}_attempt_{n}.mp4`
- Poll until success / failure / timeout (exponential backoff)
- 轮询至成功 / 失败 / 超时（指数退避）
- Store `provider_request_id` in generation report
- 在生成报告中保存 `provider_request_id`
- **Mute or ignore** embedded audio per `AUDIO.md`
- 按 `AUDIO.md` **静音或忽略** 内嵌音轨

### Routing mapping / 路由映射

`routing.json` `preferred_model` values map to fal endpoints:

| `preferred_model` | fal adapter |
|---|---|
| `seedance` | `providers/fal_seedance.py` (or unified fal client) |
| `kling` | `providers/fal_kling.py` |
| `wan_t2v` | fal Wan endpoint when available |
| `mock` | local mock only (`--mock`) |

Fallback: try `fallback_model` once on structured failure (see `ROUTING.md`).

失败时按 `ROUTING.md` 对 `fallback_model` 重试一次。

---

## TTS Providers / 配音 API

- Triggered only when dialogue exists (`AUDIO.md`).
- 仅在有台词时触发（`AUDIO.md`）。
- Prefer fal.ai TTS if one key simplifies billing; direct ElevenLabs/OpenAI TTS is also valid.
- 若一个 Key 简化计费，优先 fal TTS；直接用 ElevenLabs/OpenAI TTS 也可。
- Output: `audio/vo_segments/{line_id}.wav` → merge to `audio/vo_track.wav`.

---

## What Rules Do NOT Do / Rules 不负责的事

Rules do **not** replace code. After rules are written, you still need:

Rules **不能**代替代码。写完 rules 后仍需要：

1. Provider Python modules calling fal.ai
2. `postproduction.py` implementing timeline, subtitles, BGM, mix
3. `media/music.py`, `media/subtitles.py`, `media/audio_mix.py`
4. At least one file in `assets/music/`

Until then, **`final.mp4` is video-only (concat)** even if rules are complete.

在此之前，即使 rules 完整，**`final.mp4` 仍可能只是纯视频拼接**。

---

## Quality Test Checklist / 质量测试清单

Before calling a run "complete product":

在称为「完整成品」之前：

- [ ] fal video: all routed shots produce validated clips
- [ ] TTS: VO matches dialogue text (if any)
- [ ] BGM: `music_mood` maps to library asset
- [ ] Mix: ducking + fade in `final.mp4`
- [ ] Subtitles: SRT matches VO (if any)
- [ ] QC: audio stream present, no empty final
