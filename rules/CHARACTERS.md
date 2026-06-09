# Character Library / 角色库

## Purpose / 目的

Reusable character descriptions. Script Agent selects IDs; Storyboard Agent injects visual + performance details into each shot.

可复用角色描述。剧本 Agent 选择 ID；分镜 Agent 把视觉与表演细节注入每个镜头。

**Reference images:** `assets/characters/{id}/reference.png` — see `assets/characters/README.md`.

**参考图目录：** `assets/characters/{id}/reference.png` — 结构说明见 `assets/characters/README.md`。

---

## How agents use this file / Agent 怎么用本文件

| Stage | Reads | Does not read (yet) |
|-------|--------|---------------------|
| Script Agent | Full `CHARACTERS.md` + your Telegram prompt | PNG files |
| Storyboard Agent | Full `CHARACTERS.md` + `script.json` | PNG files |
| Keyframe (planned) | `reference_image` path + shot prompt | — |

When you say a **name** or **alias** in Telegram, Script Agent picks matching `id` from entries below.

你在 Telegram 里说的 **名字 / 别名**，由 Script Agent 在下表条目里匹配 `id`。

---

## Field guide — what to write / 字段说明（你要填什么）

Copy the template block for each new character. **Fill every line**; delete `(填写说明)` hints when done.

每个新角色复制一份模板。**每行都要填**；填完后删掉中文提示。

| Field | You write | Example |
|-------|-----------|---------|
| `id` | English slug, no spaces; **folder name** under `assets/characters/` | `xiaoming` |
| `name` | Display name | `小明` |
| `aliases` | Other names user might say (comma-separated) | `小明, 明哥, Ming` |
| `reference_image` | Path to main PNG | `assets/characters/xiaoming/reference.png` |
| `age_range` | Apparent age | `25-30` |
| `visual_identity` | Face, hair, body — **look at your reference.png** | `East Asian male, short black hair, sharp jaw` |
| `clothing` | Default outfit (keep stable across shots) | `black hoodie, dark jeans, white sneakers` |
| `personality` | How they act | `quiet under pressure, observant` |
| `movement_style` | Walk / run / gestures | `fast steps, shoulders slightly forward` |
| `voice_or_dialogue_style` | How they speak (for TTS/subtitles tone) | `short sentences, low voice` |
| `expression_by_mood` | Face per mood (one line per mood) | see hero example |
| `negative_prompt` | What to avoid in generation | `wrong face, extra fingers, cartoon face` |

You do **not** need the original image-generation prompt from your leader. Describe what you **see** in the photo.

**不需要**领导当初生图用的 prompt；**对照照片**写 `visual_identity` 和 `clothing` 即可。

---

## Character template — copy for each new role / 复制用模板

```text
id: YOUR_ID_HERE
name: 显示名
aliases: 别名1, 别名2
reference_image: assets/characters/YOUR_ID_HERE/reference.png
age_range:
visual_identity:
clothing:
personality:
movement_style:
voice_or_dialogue_style:
expression_by_mood:
  tense:
  action:
  calm:
negative_prompt: distorted face, extra limbs, inconsistent outfit, wrong character
```

**Your steps / 你要做的：**

1. Copy folder `assets/characters/_your_character/` → rename to your `id` (e.g. `xiaoming`).
2. Put leader's image as `reference.png` inside that folder.
3. Paste template above into section **「Your characters」** below and fill in.

---

## Default Hero / 默认主角（MVP 内置，可改）

```text
id: hero
name: Hero
aliases: hero, 主角
reference_image: assets/characters/hero/reference.png
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

Optional: add `assets/characters/hero/reference.png` if you have a custom hero image.

---

## Your characters / 你的角色（在此追加）

<!-- Duplicate the template block for each character. Example slot: rename _your_character folder and fill below. -->

```text
id: coffeefee
name: Coffeefee
aliases: Coffeefee, COFFEEFEE, 咖啡菲
reference_image: assets/characters/coffeefee/reference.png
age_range: 15 - 20
visual_identity: stylized 3D anthropomorphic black cat, oversized round head, small pear-shaped body, short stubby limbs, matte black fur with fine texture, huge round cream-white eyes with tiny black pupils, thin black eyebrows slanted down in a worried look, small folded Scottish-Fold-style ears, tiny dark grey button nose, small downturned mouth, three long whiskers on each cheek, bipedal standing pose
clothing: none, no outfit, natural black fur only, no accessories
personality: cheerful and curious about everything 
movement_style:light quick steps, hands often in pockets, turns head quickly
voice_or_dialogue_style: soft voice, short casual sentences, friendly tone
expression_by_mood:
  tense:wide eyes, lips pressed, slight frown
  action:focused gaze, mouth open mid-shout, energetic brows
  calm:relaxed smile, soft eyes, neutral mouth
negative_prompt: distorted face, extra limbs, inconsistent outfit, wrong character
```

---

## TTS Voice Mapping / TTS 音色映射

Used by post-production (`AUDIO.md`), not by the Script Agent JSON schema.

供后期使用（`AUDIO.md`），不是剧本 JSON 字段。

| character id | tts_profile | language default | notes |
|---|---|---|---|
| `hero` | `hero_en_male_calm` | **English (`en`)** | MVP default; map to `FAL_TTS_VOICE=rex` or `sal` |

Add a row when you add a character with a dedicated voice.

新增角色时在此加一行（若需要专属音色）。

MVP uses **English only**. Do not generate Chinese dialogue unless the user explicitly requests Chinese.

MVP **仅英文**。除非用户明确要求中文，否则不要生成中文台词。

Implementation maps `tts_profile` to fal.ai TTS or another provider ID in code (`PROVIDERS.md`).

实现层在代码中把 `tts_profile` 映射到 fal.ai TTS 或其他 provider ID（见 `PROVIDERS.md`）。

If language is unclear from user prompt, default to **English** for MVP.

若用户未明确语言，MVP 默认 **English**。

---

## Rules / 规则

- Use only IDs defined in this file unless the user explicitly creates a new character.
- 只能使用本文件中的 ID，除非用户明确要求新角色。
- `id` must match folder name under `assets/characters/`.
- `id` 必须与 `assets/characters/` 下文件夹名一致。
- Keep the same `id` across all scenes and shots.
- 所有场景和镜头中保持同一 `id`。
- Storyboard `character_prompts` must include visual_identity + clothing + expression cues.
- 分镜 `character_prompts` 必须包含外貌、服装、表情线索。
