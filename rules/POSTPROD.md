# Post-production Rules / 后期规则

## Transition Mapping / 转场映射

| Mood 情绪 | Transition 转场 |
|---|---|
| `action` or `tense` / 动作或紧张 | hard cut / 直切 |
| `calm` or `normal` / 平静或普通 | crossfade 0.3s / 交叉淡入淡出 0.3 秒 |
| `dream` or `memory` / 梦境或回忆 | dissolve 0.8s / 溶解 0.8 秒 |
| major scene jump / 大场景跳切 | fade to black 0.5s / 黑场淡出 0.5 秒 |

## Subtitle Rules / 字幕规则

- Generate SRT from dialogue fields in `script.json`.
- 从 `script.json` 的台词字段生成 SRT。
- Use timeline order from `shots.json`.
- 使用 `shots.json` 的时间线顺序。

## Music Rules / 配乐规则

- Assemble video first to get real duration.
- 先合成视频以获得真实时长。
- Fit music to final duration.
- 将音乐匹配最终时长。
- Use FFmpeg `afade` for ending fade-out.
- 使用 FFmpeg `afade` 做结尾淡出。

## Timeline Rules / 时间线规则

- Final clip order must follow `shots.json` order by `shot_id`.
- 最终片段顺序必须按照 `shots.json` 中的 `shot_id` 顺序。
- Transitions may change the real timeline duration.
- 转场可能改变真实时间线长度。
- The post-production step must write a `timeline.json` report with real start and end time for each shot.
- 后期阶段必须写入 `timeline.json`，记录每个镜头真实开始和结束时间。
- Subtitles must be timed against `timeline.json`, not only against original planned durations.
- 字幕必须基于 `timeline.json` 计时，不能只基于原始计划时长。

Example `timeline.json`:

示例 `timeline.json`：

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

## Transition Selection / 转场选择

Use the current shot mood and the next shot context:

使用当前镜头情绪和下一个镜头上下文：

- `action` or `tense`: hard cut.
- `action` 或 `tense`：直切。
- `calm` or `normal`: crossfade 0.3s.
- `calm` 或 `normal`：交叉淡入淡出 0.3 秒。
- `dream` or `memory`: dissolve 0.8s.
- `dream` 或 `memory`：溶解 0.8 秒。
- If `scene_id` changes and location changes strongly: fade to black 0.5s.
- 如果 `scene_id` 改变且地点明显变化：黑场淡出 0.5 秒。

When two rules conflict, major scene jump wins over mood.

当规则冲突时，大场景跳切优先于情绪规则。

## Subtitle Rules / 字幕细则

- Dialogue may originate from `script.json` scene dialogue or shot-level dialogue in `shots.json`.
- 台词可以来自 `script.json` 的场景台词，也可以来自 `shots.json` 的镜头级台词。
- Shot-level dialogue wins if both exist.
- 如果两者都存在，以镜头级台词为准。
- Empty dialogue produces no subtitle block.
- 空台词不生成字幕块。
- SRT timestamps must be clamped to the shot's real timeline range.
- SRT 时间戳必须限制在该镜头真实时间范围内。
- If no dialogue exists for the whole video, skip subtitle burn-in and still produce `final.mp4`.
- 如果整条视频没有台词，跳过字幕烧录，但仍然生成 `final.mp4`。

## FFmpeg Output Stages / FFmpeg 输出阶段

Post-production should produce artifacts in this order:

后期应按以下顺序产出：

1. `timeline.json`: planned and real timing.
   `timeline.json`：计划时间和真实时间。
2. `assembled_video.mp4`: clips assembled with transitions, no subtitles or music.
   `assembled_video.mp4`：只拼接画面和转场，不含字幕和音乐。
3. `final.srt`: subtitle file if dialogue exists.
   `final.srt`：如果有台词则生成字幕文件。
4. `subtitled_video.mp4`: video with subtitles if applicable.
   `subtitled_video.mp4`：如适用，生成带字幕视频。
5. `final.mp4`: final video with music.
   `final.mp4`：带配乐的最终视频。

## Music Selection / 配乐选择

- Use `script.music_mood` and `script.music_bpm` to choose a music asset.
- 使用 `script.music_mood` 和 `script.music_bpm` 选择音乐素材。
- If no matching music exists, use a neutral fallback loop.
- 如果没有匹配音乐，使用中性兜底循环。
- Music must never extend past the final video duration.
- 音乐不得超过最终视频时长。
- Apply ending fade-out with `afade` for the last 1.5 seconds by default.
- 默认对最后 1.5 秒使用 `afade` 做淡出。

