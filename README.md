# Multi-Agent Video Pipeline / 多 Agent 视频生成流水线

MVP planning and implementation scaffold for an OpenClaw-driven text-to-video automation system.

这是一个 OpenClaw 驱动的自然语言转视频自动化系统 MVP 规划与项目骨架。

## Documents / 文档

- Architecture / 架构: `docs/ARCHITECTURE.md`
- Project Structure / 项目结构: `docs/PROJECT_STRUCTURE.md`
- Development Tasks / 开发任务流程表: `docs/DEVELOPMENT_TASKS.md`
- Next Milestone / 下一里程碑: `docs/NEXT_MILESTONE.md`

## MVP Goal / MVP 目标

User sends a prompt through Telegram or WhatsApp. The system generates a script, splits it into shots, routes shots to video models, generates clips in parallel, performs QC, assembles the final video, and sends it back automatically.

用户通过 Telegram 或 WhatsApp 发送一句提示词。系统自动生成剧本、拆分分镜、路由到视频模型、并行生成片段、质检、合成最终视频，并自动回传给用户。

## First Build Target / 第一阶段目标

The first milestone is a mocked local pipeline that runs end-to-end without paid video APIs.

第一个里程碑是本地 mock 端到端流程，不依赖付费视频 API。

## Current Status / 当前状态

This repository is currently in the planning and implementation-scaffold phase. It contains:

当前仓库处于规划和实现骨架阶段，已经包含：

- Architecture and development docs.
- 架构和开发文档。
- Runtime rule files under `rules/`.
- `rules/` 下的运行时规则文件。
- Provider notes under `models/`.
- `models/` 下的视频模型说明。
- Python and Node package metadata.
- Python 和 Node 包配置。

The next step is not real video API integration. The next step is a local mock end-to-end pipeline.

下一步不是接入真实视频 API，而是先跑通本地 mock 端到端流水线。

## Recommended First Command / 推荐第一条目标命令

After Milestone 1 is implemented, this command should create a complete local job folder and a playable mock `final.mp4`:

里程碑 1 实现后，以下命令应能创建完整本地任务目录，并生成可播放的 mock `final.mp4`：

```bash
python -m video_pipeline.main --payload tests/fixtures/gateway_payload.json --mock
```

## Key Engineering Rules / 关键工程规则

- `script.json` is the single source of truth after Script Agent.
- Script Agent 之后，`script.json` 是唯一事实来源。
- Routing is deterministic and owns final model selection.
- 路由是确定性逻辑，并拥有最终模型选择权。
- Generation uses bounded concurrency, not unlimited parallel requests.
- 生成层使用有上限并发，而不是无限并行请求。
- Cost is estimated before real generation starts.
- 真实生成开始前先估算成本。
- Failed shots retry independently with explicit retry limits.
- 失败镜头独立重试，并有明确重试上限。

