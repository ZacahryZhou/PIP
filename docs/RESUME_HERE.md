# PIP 续开发备忘（回来先看这个）

> 保存时间：2026-05-29（DeepSeek 16–17 已完成；项目路径 Desktop/PIP）
> 仓库路径：`/Users/yixinzhou/Desktop/PIP`（已从 `multi-agent-video-pipeline` 迁到桌面）  
> GitHub：`https://github.com/ZacahryZhou/PIP.git`

---

## 一、当前状态（已完成）

**里程碑 1 ✅** — Mock 端到端流水线已在本机跑通。

| 项目 | 状态 |
|------|------|
| 步骤 2–15（契约 → 合成 → 一条命令） | ✅ |
| `pytest tests/ -v` | ✅ 18 passed |
| 示例成片 | `storage/jobs/job_20260528_194529/final/final.mp4` |

**用户侧产品形态（设计已定，未实现）：**

- 输入：Telegram / WhatsApp 发自然语言
- 输出：同聊天里自动回传 `final.mp4`
- 剧本/分镜：计划用 **DeepSeek** 测试（便宜），Key 只放 `.env`，不要发给任何人

---

## 二、回来先跑这三条（恢复环境）

```bash
cd ~/Desktop/PIP
source .venv/bin/activate          # 注意是 .venv 不是 venv

pytest tests/ -v

python -m video_pipeline.main \
  --payload tests/fixtures/gateway_payload.json \
  --mock

open storage/jobs/$(ls -t storage/jobs | grep '^job_' | head -1)/final/final.mp4
```

若 `.venv` 不存在或报 `bad interpreter`（搬家后常见）：  
`rm -rf .venv && python3 -m venv .venv && pip install -e ".[dev]"`

---

## 三、`.env` 配置（本地已有，勿提交 Git）

文件：项目根目录 `.env`（已从 `.env.example` 创建）

需要你自己填：

```env
DEEPSEEK_API_KEY=sk-你的key
```

可选：`ANTHROPIC_API_KEY`（若改用 Claude）  
视频 API 测试阶段可继续 `VIDEO_PIPELINE_MOCK=true` 或命令行加 `--mock`。

**安全：不要把 Key 发到 Cursor 聊天、不要 `git add .env`。**

---

## 四、接下来的开发任务（按顺序）

主清单见：`docs/PIP_DEVELOPMENT_FLOW.md`（步骤 16 起）  
**成本与省钱策略见：`docs/COST_AND_OPTIMIZATION.md`（含 2026-05-30 真实跑片 $3.73 拆解）**

| 步骤 16–17 DeepSeek 剧本/分镜 | ✅ |
| 步骤 18 fal 真视频 + keyframe | ✅ 已跑通（`job_20260530_010101`，~$3.17 画面 COGS） |
| 步骤 18b TTS + BGM + 字幕混音 | ⏳ **下一步（完整 MVP）** |
| 步骤 19 Telegram 收发 | ⏳ |
| 步骤 20 加固（断点恢复、降本） | ⏳ 可选 |

**用户待办（接步骤 18 前）：** 在本地 `.env` 填 `KLING_API_KEY` 或 `SEEDANCE_API_KEY`（不要发给 AI）。告诉 Cursor「已填 Kling/Seedance，接步骤 18」。

---

## 五、Git / GitHub 注意

- 远端 `main` 可能仍是**最早骨架提交**（只有 `.gitkeep`）。
- 本地有大量**已暂存未提交**的里程碑 1 代码（agents、pipeline、orchestrator 等）。
- 回来若需备份，建议：

```bash
git status
git commit -m "Milestone 1: mock pipeline through final.mp4"
git push origin main
```

不要提交：`.env`、`.venv/`、`storage/jobs/job_*`、`*.egg-info/`

---

## 六、关键文件地图

| 路径 | 作用 |
|------|------|
| `docs/PIP_DEVELOPMENT_FLOW.md` | 日常开发步骤清单 |
| `src/video_pipeline/orchestrator.py` | 主控状态机 |
| `src/video_pipeline/agents/` | 剧本 / 分镜 / 路由 |
| `src/video_pipeline/pipeline/` | 生成、QC、合成 |
| `src/video_pipeline/providers/mock.py` | Mock 视频 |
| `rules/*.md` | Agent 规则（任务时会复制到 job） |
| `tests/fixtures/` | 30 秒赛博朋克样例 JSON |

---

## 七、回来怎么跟 Cursor 说

复制一句即可：

> 请读 `docs/RESUME_HERE.md`，从步骤 18 继续（真视频 API），项目路径 `~/Desktop/PIP`。

---

## 八、架构要点（别忘）

- `script.json` 是剧本阶段后的单一事实来源。
- 路由是 **Python 规则**（`routing_agent.py` + `rules/ROUTING.md`），不是 LLM。
- 每个镜头视频模型写在 `routing.json`，不在 `shots.json` 里填 `preferred_model`（分镜阶段保持 null）。
- 模型专用 prompt 在 **provider 适配器**里做，没有单独的「prompt adapter agent」。
