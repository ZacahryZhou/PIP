# Post-production Rules / 后期规则

## Overview / 总览

Post-production turns **validated silent clips** into **final.mp4 with BGM, optional VO, and subtitles**.

后期把 **已质检的无声片段** 变成 **带 BGM、可选配音、字幕的 final.mp4**。

Read together with:

请一起阅读：

- `AUDIO.md` — VO, BGM, mix levels, mute source clips
- `SUBTITLE.md` — SRT and burn-in
- `MUSIC_LIBRARY.md` — BGM asset selection
- `VISUAL.md` — no MVP color grade (prompt-only)

---

## Transition Mapping / 转场映射

| Mood 情绪 | Transition 转场 |
|---|---|
| `action` or `tense` / 动作或紧张 | hard cut / 直切 |
| `calm` or `normal` / 平静或普通 | crossfade 0.3s / 交叉淡入淡出 0.3 秒 |
| `dream` or `memory` / 梦境或回忆 | dissolve 0.8s / 溶解 0.8 秒 |
| major scene jump / 大场景跳切 | fade to black 0.5s / 黑场淡出 0.5 秒 |

When two rules conflict, major scene jump wins over mood.

当规则冲突时，大场景跳切优先于情绪规则。

---

## Timeline Rules / 时间线规则

- Final clip order must follow `shots.json` order by `shot_id`.
- 最终片段顺序必须按照 `shots.json` 中的 `shot_id` 顺序。
- Transitions may change the real timeline duration.
- 转场可能改变真实时间线长度。
- Write `final/timeline.json` with real start/end per shot.
- 写入 `final/timeline.json`，记录每个镜头真实起止时间。
- Subtitles and VO must use **global** times from `timeline.json`.
- 字幕与 VO 必须使用 `timeline.json` 的 **全局** 时间。

Example `timeline.json`:

```json
{
  "shots": [
    {
      "shot_id": "shot_001",
      "source_clip": "clips/validated/shot_001.mp4",
      "start_sec": 0.0,
      "end_sec": 4.0,
      "transition_out": "hard_cut"
    }
  ],
  "final_duration_sec": 30.0
}
```

---

## FFmpeg Output Stages / FFmpeg 输出阶段

Produce artifacts in this **exact order**:

必须按以下 **顺序** 产出：

1. **`final/timeline.json`** — real timing after transitions.
2. **`final/assembled_video.mp4`** — muted clips + transitions; **no** subtitles, VO, or BGM.
3. **`audio/`** — TTS segments + BGM track per `AUDIO.md` + `MUSIC_LIBRARY.md`.
4. **`final/final.srt`** — if dialogue exists (`SUBTITLE.md`).
5. **`final/subtitled_video.mp4`** — burn subtitles when dialogue exists; still **no** final mix.
6. **`final/final.mp4`** — mux video + VO + ducked BGM; apply BGM fade-out last 1.5s.

If no dialogue: skip steps 4–5; assemble → audio mix → `final.mp4`.

无台词：跳过 4–5；拼接 → 混音 → `final.mp4`。

---

## Music / 配乐

- Select asset via `MUSIC_LIBRARY.md` using `script.music_mood` and `script.music_bpm`.
- 用 `script.music_mood` 和 `script.music_bpm` 按 `MUSIC_LIBRARY.md` 选曲。
- Trim/loop to `timeline.json.final_duration_sec`.
- 裁剪/循环至 `timeline.json.final_duration_sec`。
- See `AUDIO.md` for ducking during dialogue.
- 对白时段 BGM 压低见 `AUDIO.md`。

---

## Subtitles / 字幕

Full rules: **`SUBTITLE.md`** (timing, style, VO alignment).

完整规则见 **`SUBTITLE.md`**（时间、样式、与 VO 对齐）。

---

## Media QC / 成片质检

Before `delivered`:

- `final.mp4` exists and plays start to finish.
- Has video + audio streams.
- Duration within ±0.5s of `timeline.json.final_duration_sec`.
- If dialogue in script: subtitles and/or VO present per `AUDIO.md`.

---

## Current Implementation Note / 当前实现说明

Until post-production code catches up, the orchestrator may only produce **`assembled_video.mp4` copied to `final.mp4`** (video-only).

在后期代码补齐前，主控可能只产出 **`assembled_video.mp4` 复制为 `final.mp4`**（仅画面）。

Rules above are the **target contract** for Step 18+ implementation.

以上 rules 是 Step 18+ 实现的 **目标契约**。
