# PIP 成本、工作流与商业化预期

> 基于 2026-05-30 真实跑片记录整理（Job `job_20260530_010101` 及同会话调试 run）。  
> 本文档记录：**调用了什么 API、钱花在哪儿、如何省钱、成熟商业化后一条 30 秒全要素成片的预期成本**。

---

## 一、当前项目处于什么阶段

| 能力 | 状态 | 是否计费 |
|------|------|----------|
| DeepSeek 剧本 + 分镜 | ✅ 已接入 | DeepSeek 账单（极低） |
| fal 关键帧（Nano Banana Pro，i2v） | ✅ 已接入 | fal 账单 |
| fal 视频（Seedance T2V / Kling T2V·I2V） | ✅ 已接入 | fal 账单 |
| QC + clip 标准化 + FFmpeg 拼接 | ✅ 已接入 | 本地算力，$0 |
| TTS 对白 | ❌ 规则已写，代码未接 | 未来 fal |
| BGM 配乐 | ❌ 规则已写，代码未接 | fal 或本地 $0 |
| 字幕 SRT / 烧录 | ❌ 规则已写，代码未接 | 本地 $0 |
| Telegram 收发 | ❌ 未实现 | Bot API 基本 $0 |

**结论：** 你现在跑通的是 **「无声画面 MVP」**（Step 18），不是最终商业化成片。  
用户侧若看到 fal 消费 **~$3.73**，对应的是 **画面链路 + 调试重复调用**，不含配音和 BGM。

---

## 二、2026-05-30 真实跑片记录（务必记住）

### 2.1 成功成片（唯一应计入「这条 30 秒视频」的 job）

| 字段 | 值 |
|------|-----|
| Job ID | `job_20260530_010101` |
| 状态 | `delivered` |
| 成片路径 | `storage/jobs/job_20260530_010101/final/final.mp4` |
| 规格 | 1920×1080 / 24fps / **30.0s** / ~31MB |
| 镜头数 | **8**（4× t2v + 4× i2v） |
| 项目内估算成本 | **$3.17 USD**（见 `routing/routing.json`） |

### 2.2 同会话内的其他 run（调试浪费，但可能已计费）

| Job ID | 做了什么 | 结果 | 对 fal 账单的影响 |
|--------|----------|------|-------------------|
| `job_20260530_005515` | `--stop-after storyboarded` | DeepSeek 分镜成功 | 仅 DeepSeek，fal $0 |
| `job_20260530_005635` | 全流程 | keyframe **下载 SSL 失败**（fal 可能已生成图） | 可能多 3 次 Nano Banana 计费 |
| `job_20260530_005823` | `--stop-after keyframes` | 4 张 keyframe 成功 | 可能多 4 次 Nano Banana 计费 |
| **`job_20260530_010101`** | **全流程** | **成功 delivered** | **主账单 ~$3.17** |

**用户 fal 控制台显示 ~$3.73 的合理解释：**

```text
~$3.17（最终成片 job）
+ ~$0.50–0.60（调试 run 重复 keyframe / fal 实际单价略高于内部估算）
≈ $3.73
```

---

## 三、成功 job 调用了哪些 API（逐项清单）

### 3.1 DeepSeek（剧本 + 分镜）— 不在 fal $3.73 里

| 阶段 | Endpoint | 模型 | 次数 |
|------|----------|------|------|
| Script Agent | `{DEEPSEEK_BASE_URL}/v1/chat/completions` | `deepseek-chat` | 1 |
| Storyboard Agent | 同上 | `deepseek-chat` | 1（若校验失败会自动重试，最多 2 次） |

**作用：** 读 `rules/*.md` + 用户 prompt → 输出 `script.json`、`shots.json`（含每镜 `generation_mode: t2v|i2v`）。

**典型费用：** 约 **$0.01–0.08 / 条视频**（视 prompt 长度与输出 token 而定）。在 DeepSeek 控制台查看，与 fal 分开。

---

### 3.2 fal.ai — 画面生成（当前 MVP 的主要成本）

`.env` 中配置的 endpoint（见 `.env.example`）：

| 用途 | 环境变量 | fal endpoint |
|------|----------|--------------|
| i2v 关键帧 | `FAL_IMAGE_MODEL` | `fal-ai/nano-banana-pro` |
| 高动态 t2v | `FAL_VIDEO_MODEL_SEEDANCE` | `fal-ai/bytedance/seedance/v1.5/pro/text-to-video` |
| 写实 t2v | `FAL_VIDEO_MODEL_KLING` | `fal-ai/kling-video/v3/standard/text-to-video` |
| 写实 i2v | `FAL_VIDEO_MODEL_KLING_I2V` | `fal-ai/kling-video/v3/standard/image-to-video` |

**`job_20260530_010101` 实际调用次数：**

| 类型 | 次数 | 明细 |
|------|------|------|
| Nano Banana Pro（图片） | **3** | shot_003、004、006 的 keyframe |
| Seedance T2V（视频） | **2** | shot_001、007 |
| Kling T2V（视频） | **3** | shot_002、005、008 |
| Kling I2V（视频） | **3** | shot_003、004、006（各需先 upload keyframe） |
| **fal 视频合计** | **8** | 每镜 1 次成功，无 fallback 二次计费 |

**未调用（本 run）：**

- `FAL_TTS_MODEL`（`xai/tts/v1`）
- `FAL_BGM_MODEL`（`fal-ai/minimax-music/v2.6`）
- `FAL_VIDEO_MODEL_WAN`（备用，未触发 fallback）
- Telegram / WhatsApp

---

### 3.3 按镜头拆账（项目内 routing 估算，USD）

来源：`storage/jobs/job_20260530_010101/routing/routing.json`

| 镜头 | 模式 | 路由模型 | 时长 | 估算 |
|------|------|----------|------|------|
| shot_001 | t2v | seedance | 4.0s | $0.40 |
| shot_002 | t2v | kling | 4.0s | $0.32 |
| shot_003 | i2v | kling + keyframe | 4.0s | $0.47 |
| shot_004 | i2v | kling + keyframe | 4.0s | $0.47 |
| shot_005 | t2v | kling | 3.5s | $0.32 |
| shot_006 | i2v | kling + keyframe | 3.5s | $0.47 |
| shot_007 | t2v | seedance | 3.5s | $0.40 |
| shot_008 | t2v | kling | 3.5s | $0.32 |
| **合计** | | | **30.0s** | **$3.17** |

**大类占比（估算）：**

| 类别 | 金额 | 占比 |
|------|------|------|
| 视频生成（8 次 fal video） | ~$2.72 | ~86% |
| 关键帧图片（3 次 Nano Banana） | ~$0.45 | ~14% |

**计费逻辑（代码侧，非 fal 官方价目表）：**

```text
src/video_pipeline/agents/routing_agent.py

视频：ceil(duration_sec) × 单价
  seedance: $0.10/s
  kling:    $0.08/s
  wan_t2v:  $0.03/s

i2v 附加：KEYFRAME_COST_USD = $0.15 / 镜
```

fal 官方按模型/档位计价可能与上表略有偏差；以 fal Dashboard 为准。

---

## 四、完整工作流与「钱在哪个阶段花出去」

```text
用户 prompt
    │
    ▼
[DeepSeek] script.json          ← ~$0.01–0.08，几乎可忽略
    │
    ▼
[DeepSeek] shots.json           ← 同上；决定 t2v/i2v 比例（影响 fal 总账）
    │
    ▼
[Python] routing.json           ← $0，仅估算成本、预算闸门
    │
    ▼
[fal] keyframes/ (仅 i2v)       ← $0.15/镜（估算）；调试重复跑会重复扣
    │
    ▼
[fal] clips/raw/ (每镜 1 视频)  ← 主要成本（~86%）
    │
    ▼
[本地] QC + normalize           ← $0
    │
    ▼
[本地] FFmpeg concat            ← $0 → final.mp4（当前：无声）

── 尚未接入 ──
[fal] TTS VO                    ← 未来：按句/字符
[fal 或 library] BGM            ← 未来：~$0.10–0.30 或 $0
[本地] 字幕 + 混音               ← $0
[Telegram] 回传                 ← $0
```

**预算闸门：** `MAX_JOB_COST_USD=5.0`（`.env`）在 routing 后检查；超预算则 **不开始** keyframe/video，避免失控。

---

## 五、如何优化省钱（开发期 vs 产品期）

### 5.1 开发调试（零 fal 或低 fal）

| 做法 | 命令 / 配置 | 效果 |
|------|-------------|------|
| 全流程 mock | `--mock` | DeepSeek 也用 fixture；**fal $0** |
| 只测剧本 | `--stop-after scripted` | 仅 DeepSeek |
| 只测分镜 + 路由 | `--stop-after routed` | 看镜头数、t2v/i2v、**预估 $** 再决定是否生成 |
| 只测 keyframe | `--stop-after keyframes` | **避免**在未确认分镜前跑 8 段视频 |
| 不要重复跑全流程 | 改 prompt 时分阶段 | 同会话曾多花 ~$0.5+ 在重复 keyframe |

推荐调试顺序：

```bash
# 1. 免费
pytest tests/ -v
python -m video_pipeline.main --payload ... --mock

# 2. 只花 DeepSeek
python -m video_pipeline.main --payload ... --stop-after storyboarded

# 3. 看 routing 预估成本（仍无 fal 视频）
python -m video_pipeline.main --payload ... --stop-after routed

# 4. 确认满意后再真生成
python -m video_pipeline.main --payload ...
```

### 5.2 产品策略（降低单条 COGS）

| 策略 | 机制 | 预期节省 |
|------|------|----------|
| **减少镜头数** | Storyboard 规则：30s 用 5–6 镜而非 8 镜 | 线性下降（约 25–35%） |
| **减少 i2v** | 仅 CU/MCU + 对白用 i2v；WS/EWS 用 t2v | 每少 1 镜 i2v ≈ 省 $0.47（估算） |
| **简单镜头用 Wan** | 配置 `FAL_VIDEO_MODEL_WAN`，routing 已支持 | ~$0.03/s vs kling $0.08/s |
| **Seedance 只给高动态** | 已有 routing 规则；避免滥用 | Seedance 单价高于 kling |
| **BGM 用 library** | `PIP_BGM_MODE=library` + `assets/music/` | 每片省 ~$0.10–0.30 |
| **避免 QC 失败后整片重跑** | 待做：job 断点恢复 + 单镜重试 | 减少重复 8 镜全开 |
| **并发上限** | `MAX_CONCURRENT_SHOTS=4`（已配置，待 generation 真正并行） | 不省钱，但控峰值 |
| **用户侧预算** | 降低 `MAX_JOB_COST_USD` 或按套餐 cap 镜头数 | 硬上限 |

### 5.3 i2v vs t2v 成本直觉

```text
t2v 单镜（kling 4s）≈ $0.32

i2v 单镜（kling 4s）≈ $0.32 + $0.15 keyframe ≈ $0.47  （约贵 47%）
```

本次 8 镜里 4 镜 i2v，keyframe  alone 就约 **$0.60**；若改为 2 镜 i2v，可省约 **$0.30**。

### 5.4 已知浪费模式（务必避免）

1. **SSL 下载失败仍可能已扣 fal 图片费**（`job_20260530_005635`）— 已改 httpx 下载。  
2. **`--stop-after keyframes` 后又跑全流程** — keyframe 重复生成。  
3. **DeepSeek 分镜校验失败重试** — 仅 DeepSeek 成本，可忽略。  
4. **video fallback 未触发** — 本次 8/8 一次成功；若 fallback 触发，费用接近翻倍该镜。

---

## 六、成熟商业化：一条 30 秒「全要素」成片成本预期

「全要素」= 画面 + TTS 对白 + BGM + 字幕 + Telegram 交付 + 合理 QC/重试缓冲。

以下均为 **COGS（变动成本）**，不含人力、服务器、存储、支付手续费、毛利。

### 6.1 成本模型假设

| 组件 | 假设 | 备注 |
|------|------|------|
| 镜头数 | 6–8 | 30s 行业常见 |
| i2v 比例 | 2–4 镜 | 商业化应收紧，非本次 4/8 |
| 视频路由 | 混合 seedance + kling + 部分 wan | 与 `ROUTING.md` 一致 |
| TTS | fal `xai/tts/v1`，2–4 句英文 | 尚未接入 |
| BGM | fal MiniMax **或** 本地 library | 二选一 |
| 字幕 | 本地 FFmpeg | $0 |
| LLM | DeepSeek script + storyboard | 极低 |
| QC 重试 | 10–15% 画面成本缓冲 | 1 镜重生成 |

### 6.2 三档预期（USD / 条 30s 视频）

#### 档 A — 当前画面 MVP（已验证，无声）

| 项目 | 低 | 中（**本次实测**） | 高 |
|------|-----|-------------------|-----|
| DeepSeek | $0.01 | $0.03 | $0.08 |
| fal 视频 + keyframe | $2.80 | **$3.17** | $3.80 |
| **合计 COGS** | **~$2.85** | **~$3.20** | **~$3.90** |

对应：**仅画面、无音轨、无字幕、无 Telegram 自动化**。

---

#### 档 B — 完整产品 MVP（画面 + TTS + BGM + 字幕 + 发送）

在档 A 基础上增加（**估算，待 Step 18b 接入后实测**）：

| 项目 | 估算 COGS | 说明 |
|------|-----------|------|
| TTS（2–4 句） | $0.05 – $0.20 | fal xAI TTS，视字数 |
| BGM（fal 生成 1 条） | $0.10 – $0.35 | MiniMax Music v2.6 |
| BGM（library 模式） | **$0** | 一次采购，边际为 0 |
| 字幕生成 + 烧录 | $0 | 本地 |
| Telegram 发送 | ~$0 | Bot API |
| **增量** | **$0.15 – $0.55** | library BGM 取下限 |

| | library BGM | fal BGM |
|--|-------------|---------|
| **完整 MVP COGS** | **~$3.0 – $3.8** | **~$3.2 – $4.3** |

**合理中枢（混合路由 + library BGM + 6 镜）：约 $3.50 / 条。**

---

#### 档 C — 优化后的商业化量产（推荐目标）

通过第 5 节策略刻意压成本：

| 优化项 | 效果 |
|--------|------|
| 6 镜（非 8 镜） | 视频费 −25% |
| 2 镜 i2v（非 4 镜） | keyframe −$0.30 |
| 2 镜 wan 建立镜头 | 视频 −$0.10~0.20 |
| library BGM | −$0.15~0.30 |
| 单镜重试而非整片重跑 | 缓冲从 15% → 8% |

| 项目 | 预期 COGS |
|------|-----------|
| DeepSeek | $0.02 – $0.05 |
| fal 画面（6 镜，优化路由） | **$1.60 – $2.20** |
| TTS | $0.05 – $0.15 |
| BGM（library） | $0 |
| QC/重试缓冲 | $0.15 – $0.25 |
| **合计** | **~$1.85 – $2.65 / 条** |

**量产目标：COGS ≤ $2.50 / 30s 成片（无声优画面 + 配音 + 本地 BGM）。**

---

#### 档 D — 高端 / 重试多 / 全 fal BGM（上限参考）

| 项目 | 预期 COGS |
|------|-----------|
| 8 镜，4 i2v，少 wan | $3.2 – $4.0 |
| TTS + fal BGM | $0.25 – $0.55 |
| 20% 重试缓冲 | $0.60 – $0.80 |
| **合计** | **~$4.0 – $5.5 / 条** |

超过 `MAX_JOB_COST_USD=5.0` 时应触发预算拦截或降级路由。

---

### 6.3 对用户定价的粗算（非财务建议，仅帮助预期）

若 COGS 中枢 **$3.50**（完整 MVP）：

| 毛利率目标 | 建议售价（USD） |
|------------|-----------------|
| 50% | $7.0 |
| 60% | $8.8 |
| 70% | $11.7 |

若优化到 COGS **$2.20**（档 C）：

| 毛利率目标 | 建议售价（USD） |
|------------|-----------------|
| 50% | $4.4 |
| 60% | $5.5 |
| 70% | $7.3 |

实际还需加：支付费、存储 CDN、人工审核、失败退款池。

---

## 七、与项目文档 / 代码的对应关系

| 主题 | 文件 |
|------|------|
| 开发步骤 | `docs/ARCHITECTURE.md` · `docs/RESUME_HERE.md` |
| 路由与估价 | `src/video_pipeline/agents/routing_agent.py`、`rules/ROUTING.md` |
| fal endpoint | `.env.example`、`rules/PROVIDERS.md` |
| 音频策略 | `rules/AUDIO.md`、`rules/MUSIC_LIBRARY.md` |
| 后期顺序 | `rules/POSTPROD.md` |
| 实测 job 产物 | `storage/jobs/job_20260530_010101/` |

---

## 八、待办（降本必做，按优先级）

1. **Job 断点恢复** — 失败镜只重跑该镜，不重复 DeepSeek + 全镜 video。  
2. **generation 并发** — 已配置 `MAX_CONCURRENT_SHOTS`，缩短 wall time（不直接省钱）。  
3. **routing 预估 vs fal 实际对账** — 从 fal Dashboard 拉回真实单价，校准 `COST_PER_SECOND`。  
4. **Storyboard 默认 6 镜 / 30s** — 在 `rules/STORYBOARD.md` 写死上限，防止 LLM 拆太碎。  
5. **接入 TTS + library BGM 优先** — 完整 MVP 用 library 可立刻少 $0.15+/片。  
6. **成本写入 job report** — 每 job 输出 `cost_report.json`（预估 + 可选 fal 回执）。

---

## 九、一句话总结

- **你现在花出去的 ~$3.73（fal）≈ 一条 30s 无声成片的 ~$3.17 + 调试重复 keyframe 的 ~$0.5。**  
- **钱主要在 fal 视频（~86%），其次 i2v 关键帧（~14%）；DeepSeek 可忽略。**  
- **成熟商业化全要素（配音+配乐+字幕+发送），合理预期 COGS 约 $3.0–$4.3/条；优化量产后可压到 $1.85–$2.65/条。**  
- **开发期务必 `--mock` / `--stop-after routed`，确认 routing 预估后再开 fal。**

---

*最后更新：2026-05-30（基于 job_20260530_010101 及同会话调试记录）*
