# Character assets / 角色参考图

One folder per character **id** (must match `rules/CHARACTERS.md`).

每个角色一个文件夹，**id 必须与 `rules/CHARACTERS.md` 里一致**。

## Folder layout / 目录结构

```text
assets/characters/
  {character_id}/
    reference.png          ← required 主参考图（正脸/半身，16:9，≥1080p）
    reference_full.png     ← optional 全身
    reference_side.png     ← optional 侧面
```

## Image guidelines / 图片要求

| Item | Recommendation |
|------|----------------|
| Format | PNG or JPG |
| Aspect | 16:9 (matches pipeline `1920x1080`) |
| Resolution | ≥ 1920×1080 |
| Content | Clear face, stable outfit, simple background |
| Source | Your model output or art from your team — save as `reference.png` |

## How to add a character / 如何新增

1. Create folder: `assets/characters/your_id/`
2. Put `reference.png` inside.
3. Fill the matching block in `rules/CHARACTERS.md` (same `id`, `reference_image` path).

**Note:** Image lookup at Keyframe stage is planned; text in `CHARACTERS.md` is already used by Script / Storyboard agents today.

**说明：** 图片在 Keyframe 环节接入尚在规划中；`CHARACTERS.md` 里的文字已被剧本/分镜 Agent 使用。
