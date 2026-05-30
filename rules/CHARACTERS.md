# Character Library / 角色库

## Purpose / 目的

Reusable character descriptions. Script Agent selects IDs; Storyboard Agent injects visual + performance details into each shot.

可复用角色描述。剧本 Agent 选择 ID；分镜 Agent 把视觉与表演细节注入每个镜头。

## Character Template / 角色模板

```text
id:
name:
age_range:
visual_identity:
clothing:
personality:
movement_style:
voice_or_dialogue_style:
expression_by_mood:
negative_prompt:
```

## Default Hero / 默认主角

```text
id: hero
name: Hero
age_range: 25-35
visual_identity: determined face, athletic build, expressive eyes, strong jaw
clothing: dark practical jacket, worn boots, minimal accessories
personality: brave, focused, emotionally restrained under pressure
movement_style: fast, precise, alert sprint and sudden stops
voice_or_dialogue_style: short direct sentences, low urgency
expression_by_mood:
  tense: jaw clenched, eyes scanning, shallow breath, sweat on brow
  action: focused stare, mouth set, kinetic body language
  calm: relaxed shoulders, steady gaze
negative_prompt: distorted face, extra limbs, inconsistent outfit, cartoon proportions
```

## TTS Voice Mapping / TTS 音色映射

Used by post-production (`AUDIO.md`), not by the Script Agent JSON schema.

供后期使用（`AUDIO.md`），不是剧本 JSON 字段。

| character id | tts_profile | language default | notes |
|---|---|---|---|
| `hero` | `hero_en_male_calm` | **English (`en`)** | MVP default; map to `FAL_TTS_VOICE=rex` or `sal` |

MVP uses **English only**. Do not generate Chinese dialogue unless the user explicitly requests Chinese.

MVP **仅英文**。除非用户明确要求中文，否则不要生成中文台词。

Remove `hero_zh_male_calm` from MVP flows.

MVP 流程不使用中文音色配置。

Implementation maps `tts_profile` to fal.ai TTS or another provider ID in code (`PROVIDERS.md`).

实现层在代码中把 `tts_profile` 映射到 fal.ai TTS 或其他 provider ID（见 `PROVIDERS.md`）。

If language is unclear from user prompt, default to **English** for MVP.

若用户未明确语言，MVP 默认 **English**。

## Rules / 规则

- Use only IDs defined in this file unless the user explicitly creates a new character.
- 只能使用本文件中的 ID，除非用户明确要求新角色。
- Keep the same `id` across all scenes and shots.
- 所有场景和镜头中保持同一 `id`。
- Storyboard `character_prompts` must include visual_identity + clothing + expression cues.
- 分镜 `character_prompts` 必须包含外貌、服装、表情线索。
