# PIP 开发流程（只看这一份）

产品名：**PIP**（文本 → 短视频，自动回传 Telegram）

---

## 一、你现在在哪

| 项目 | 状态 |
|------|------|
| 规划 + 规则文档 | ✅ 完成 |
| JSON 契约 + 测试（Phase A） | ✅ 完成 |
| 能跑整条流水线（mock） | ✅ 完成 |
| 能出真视频（画面无声） | ✅ Step 18 已跑通（~$3.2/30s COGS） |
| 能出完整成片（配音+BGM+字幕） | ❌ Step 18b |
| Telegram 回传 | ❌ Step 19 |

**下一步：Step 18b（音频后期）或 Step 19（Telegram）。成本与省钱见 `docs/COST_AND_OPTIMIZATION.md`。**

---

## 二、仓库里重要东西是干什么的（简写）

### 文档 `docs/`

| 文件 | 作用 | 要不要常看 |
|------|------|------------|
| **PIP_DEVELOPMENT_FLOW.md** | **开发步骤清单（本文件）** | ✅ 只看这个 |
| **COST_AND_OPTIMIZATION.md** | **成本拆解、省钱工作流、商业化 COGS 预期** | 接 fal 后必读 |
| ARCHITECTURE.md | 架构为什么这样设计 | 不懂再看 |
| PROJECT_STRUCTURE.md | 代码将来放哪个文件夹 | 写代码时看 |
| DEVELOPMENT_TASKS.md | 超细任务表（备用） | 可不看 |
| NEXT_MILESTONE.md | 里程碑说明（备用） | 可不看 |

### 规则 `rules/`（运行时会被程序读取）

| 文件 | 作用 |
|------|------|
| MASTER.md | 剧本 Agent：风格、时长、输出 JSON 格式 |
| CHARACTERS.md | 角色库描述 |
| STORYBOARD.md | 分镜 Agent：怎么拆镜头 |
| ROUTING.md | 路由 Agent：每镜用哪个视频模型 |
| POSTPROD.md | 后期：转场、字幕、音乐 |

### 模型说明 `models/`

| 文件 | 作用 |
|------|------|
| seedance.md | Seedance API 怎么用 |
| kling.md | Kling API 怎么用 |
| wan_t2v.md | Wan API 怎么用 |

### 代码 `src/video_pipeline/`（正在逐步补）

| 路径 | 作用 |
|------|------|
| schemas/ | 规定每种 JSON 长什么样 ✅ 已有 |
| config.py | 读 `.env` 配置 ✅ 已有 |
| storage/ | 每次请求一个 job 文件夹 |
| agents/ | 剧本 / 分镜 / 路由 |
| providers/ | 调 Seedance、Kling、Wan |
| pipeline/ | 生成、质检、后期、回传 |
| main.py | 命令行入口 `python -m video_pipeline.main` |
| orchestrator.py | 按顺序调用各阶段 |

### 测试 `tests/`

| 路径 | 作用 |
|------|------|
| fixtures/*.json | 样例数据（30 秒赛博朋克追逐） |
| test_schemas.py | 检查 JSON 是否合法 ✅ 已有 |

### 一次任务产生的文件（将来在 `storage/jobs/job_xxx/`）

| 文件 | 作用 |
|------|------|
| gateway_payload.json | 用户原始输入 |
| script.json | 剧本 ★ 后面都听它的 |
| shots.json | 分镜列表 |
| routing.json | 每镜用哪个模型 + 多少钱 |
| clips/*.mp4 | 每个镜头生成的视频 |
| qc_report.json | 质检结果 |
| final.mp4 | 最终成片 |

---

## 三、数据怎么走（一条线）

```text
用户消息 → gateway_payload → script → shots → routing → 生成视频 → 质检 → 合成 → 发回用户
```

---

## 四、开发步骤（按顺序做，不要跳）

说明：`[x]` 已完成　`[ ]` 未做

---

### 步骤 1　上传 GitHub　`[ ]` 或 `[x]`

| | |
|---|---|
| **做什么** | `git push origin main`，把代码备份到 GitHub |
| **涉及** | 整个项目 |
| **验收** | 浏览器里能看到仓库文件 |

---

### 步骤 2　JSON 数据契约　`[x]`

| | |
|---|---|
| **做什么** | 用 Pydantic 定义每种 JSON 的字段和校验规则 |
| **涉及** | `src/video_pipeline/schemas/*.py` |
| **验收** | 文件存在，无报错 |

---

### 步骤 3　样例 JSON　`[x]`

| | |
|---|---|
| **做什么** | 放一套完整的假数据（30 秒短片）供测试用 |
| **涉及** | `tests/fixtures/gateway_payload.json`、`script.json`、`shots.json`、`routing.json` |
| **验收** | 四个文件都在 |

---

### 步骤 4　跑通 schema 测试　`[x]`

| | |
|---|---|
| **做什么** | 确认样例 JSON 合法、非法数据会被拒绝 |
| **涉及** | `tests/test_schemas.py`、`config.py` |
| **验收** | `pytest tests/test_schemas.py -v` → 8 passed |

---

### 步骤 5　任务目录（job folder）　`[x]`

| | |
|---|---|
| **做什么** | 每次请求自动创建 `storage/jobs/job_时间戳/`，下面有 input、script、clips、final 等子文件夹 |
| **涉及** | `storage/jobs.py`、`storage/artifacts.py` |
| **验收** | 调用一次函数能生成完整目录树 |

---

### 步骤 6　命令行入口　`[x]`

| | |
|---|---|
| **做什么** | 写 `main.py`，支持 `python -m video_pipeline.main --payload xxx.json --mock` |
| **涉及** | `main.py` |
| **验收** | 命令能执行，不报错（哪怕只创建空目录） |

---

### 步骤 7　主控 + 状态文件　`[x]`

| | |
|---|---|
| **做什么** | `orchestrator.py` 按阶段执行，每步更新 `job_state.json`（received → scripted → …） |
| **涉及** | `orchestrator.py` |
| **验收** | job 文件夹里有 `job_state.json`，状态会变 |

---

### 步骤 8　复制规则快照　`[x]`

| | |
|---|---|
| **做什么** | 任务开始时把 `rules/*.md` 复制到 `job_xxx/rules_snapshot/` |
| **涉及** | `storage/artifacts.py` |
| **验收** | job 里能看到 MASTER、STORYBOARD 等副本 |

---

### 步骤 9　Mock 剧本 Agent　`[x]`

| | |
|---|---|
| **做什么** | 不调 Claude，直接把 fixture 写入 `script/script.json` |
| **涉及** | `agents/script_agent.py` |
| **验收** | job 里有合法 `script.json` |

---

### 步骤 10　Mock 分镜 Agent　`[x]`

| | |
|---|---|
| **做什么** | 写入 `storyboard/shots.json`（`preferred_model` 保持 null） |
| **涉及** | `agents/storyboard_agent.py` |
| **验收** | job 里有合法 `shots.json` |

---

### 步骤 11　路由 Agent（真逻辑）　`[x]`

| | |
|---|---|
| **做什么** | 用 Python 读 `ROUTING.md` 规则，生成 `routing/routing.json` + 成本 |
| **涉及** | `agents/routing_agent.py` |
| **验收** | `python -m video_pipeline.main ... --mock --stop-after routing` 成功 |

---

### 步骤 12　Mock 视频生成　`[x]`

| | |
|---|---|
| **做什么** | 每个镜头生成一个占位 mp4（不调真 API） |
| **涉及** | `providers/mock.py`、`pipeline/generation.py` |
| **验收** | `clips/raw/` 里每个 shot 有一个 mp4 |

---

### 步骤 13　质检 QC　`[x]`

| | |
|---|---|
| **做什么** | 检查时长、分辨率、文件能否播放 |
| **涉及** | `pipeline/quality_control.py` |
| **验收** | 有 `reports/qc_report.json` |

---

### 步骤 14　后期合成　`[x]`

| | |
|---|---|
| **做什么** | FFmpeg 拼接镜头 → `final/final.mp4` |
| **涉及** | `pipeline/postproduction.py`、`media/ffmpeg.py` |
| **验收** | 本地能打开 `final.mp4` 播放 |

---

### 步骤 15　里程碑 1 完成　`[x]`

| | |
|---|---|
| **做什么** | 一条命令跑完全程（仍是 mock，不花钱） |
| **涉及** | 上面全部 |
| **验收** | `python -m video_pipeline.main --payload tests/fixtures/gateway_payload.json --mock` |

---

### 步骤 16　接入 DeepSeek 剧本　`[x]`

| | |
|---|---|
| **做什么** | 真调 API 生成 `script.json`（读 MASTER + CHARACTERS） |
| **涉及** | `agents/script_agent.py`、`.env` 里 `ANTHROPIC_API_KEY` |
| **验收** | 用户一句话能生成新剧本 JSON |

---

### 步骤 17　接入 DeepSeek 分镜　`[x]`

| | |
|---|---|
| **做什么** | 真调 API 从 script 拆 shots |
| **涉及** | `agents/storyboard_agent.py` |
| **验收** | shots 和 script 时长对得上 |

---

### 步骤 18　接入第一个真视频 API　`[ ]`

| | |
|---|---|
| **做什么** | 接 Kling 或 Seedance，替换 mock 生成 |
| **涉及** | `providers/kling.py` 或 `seedance.py` |
| **验收** | 一个镜头能生成真视频 |

---

### 步骤 19　Telegram 收发　`[ ]`

| | |
|---|---|
| **做什么** | 收消息 → 跑 pipeline → 发回 `final.mp4` |
| **涉及** | `src/openclaw_gateway/`、`pipeline/delivery.py` |
| **验收** | 手机 Telegram 收到视频 |

---

### 步骤 20　加固（可选）　`[ ]`

| | |
|---|---|
| **做什么** | 失败重试、成本上限、错误提示、WhatsApp |
| **涉及** | 各处 |
| **验收** | 稳定 demo |

---

## 五、常用命令

```bash
# 进入项目
cd multi-agent-video-pipeline
source .venv/bin/activate

# 测试 JSON（现在就能用）
pytest tests/test_schemas.py -v

# 仅测 DeepSeek 剧本（会消耗少量 API 额度）
python -m video_pipeline.main \
  --payload tests/fixtures/gateway_payload.json \
  --stop-after scripted

# 全流程：DeepSeek 剧本+分镜 + mock 视频（不加 --mock）
python -m video_pipeline.main \
  --payload tests/fixtures/gateway_payload.json

# 完全免费 mock（fixture + 占位视频）
python -m video_pipeline.main \
  --payload tests/fixtures/gateway_payload.json \
  --mock
```

---

## 六、命名 PIP（备忘）

| 要改的 | 要不要现在改 |
|--------|----------------|
| 产品名显示 PIP | 随时 |
| GitHub 仓库名 | 可选 |
| Python 包名不要用 `pip`（和 pip 冲突） | 发布时再定 |
| 文件夹 `video_pipeline/` | 可以后再改 |

---

*更新：里程碑 1（步骤 2–15）已完成，从步骤 16 继续。*
