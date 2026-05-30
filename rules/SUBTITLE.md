# Subtitle Rules / 字幕规则

## Purpose / 目的

Burn or attach readable subtitles aligned with dialogue and `timeline.json`.

生成与台词、`timeline.json` 对齐的可读字幕。

Read together with `AUDIO.md` and `POSTPROD.md`.

请与 `AUDIO.md`、`POSTPROD.md` 一起阅读。

---

## Text Source / 文本来源

Same priority as `AUDIO.md`:

与 `AUDIO.md` 相同优先级：

1. Shot-level dialogue in `shots.json`
2. Scene-level dialogue in `script.json` (mapped by scene / shot)
3. No dialogue → no SRT, skip burn-in

Format per line:

每行格式：

```json
{
  "speaker": "hero",
  "text": "Keep moving.",
  "start_sec": 2.0,
  "end_sec": 3.5
}
```

---

## Timing / 时间

- Convert scene-relative timestamps to **global** time using `timeline.json`.
- 用 `timeline.json` 把场景相对时间换成 **全局** 时间。
- Minimum on-screen duration: **0.8s** per subtitle block.
- 每条字幕最短显示 **0.8 秒**。
- Maximum characters per line (MVP):
- 每行最大字数（MVP）：

| Language 语言 | Max chars 最大字符 |
|---|---|
| English | 42 |
| Chinese | 18 |

- Two lines max per block; wrap at punctuation when possible.
- 每个块最多两行；尽量在标点处换行。
- Clamp block to shot boundaries on the final timeline.
- 字幕块不得超出镜头在成片上的起止时间。

---

## SRT Output / SRT 输出

- Path: `final/final.srt`
- Index from 1, UTF-8, Unix newlines.
- 从 1 编号，UTF-8，Unix 换行。
- Time format: `HH:MM:SS,mmm`
- Do not include speaker name in SRT text unless user prompt asks for name labels.
- 除非用户要求显示说话人，SRT 正文不含 speaker 名。

---

## Burn-in Style / 烧录样式（MVP）

| Property 属性 | Value 值 |
|---|---|
| Font 字体 | System sans fallback (Arial / PingFang SC) |
| Size 大小 | ~4% of frame height |
| Position 位置 | Bottom center, safe margin 8% from bottom |
| Color 颜色 | White `#FFFFFF` |
| Outline 描边 | Black 2px |
| Background 背景 | None (outline only) |

Bilingual MVP: **one language per job** (the language of dialogue text). Do not auto-translate in MVP.

双语 MVP：**每个任务一种语言**（与台词文本一致）。MVP 不自动翻译。

---

## VO vs Subtitles / 配音与字幕

| Mode 模式 | When 何时 |
|---|---|
| VO + subtitles | Default when dialogue exists |
| Subtitles only | TTS failed after retry |
| VO only | Not allowed in MVP (accessibility) |
| Neither | No dialogue in script |

When both VO and subtitles exist, text must be **identical**.
有 VO 又有字幕时，文本必须 **完全一致**。

---

## Artifacts / 产物

1. `final/final.srt`
2. `final/subtitled_video.mp4` — video + burned subtitles, **no BGM yet**
3. `final/final.mp4` — subtitled video + mixed audio (see `POSTPROD.md`)
