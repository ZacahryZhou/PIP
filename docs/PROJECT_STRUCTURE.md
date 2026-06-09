# Project Structure / 项目结构

This document defines the target MVP repository layout. The structure separates gateway, orchestration, rules, schemas, providers, media processing, and runtime artifacts.

本文档定义 MVP 目标项目结构。目录按网关、主控流程、规则、数据契约、模型供应商、媒体处理和运行产物分层。

## Root Layout / 根目录结构

```text
multi-agent-video-pipeline/
├── README.md
├── .env.example
├── pyproject.toml
├── package.json
├── docs/
│   ├── ARCHITECTURE.md
│   ├── RESUME_HERE.md
│   ├── PROJECT_STRUCTURE.md
│   └── COST_AND_OPTIMIZATION.md
├── rules/
│   ├── MASTER.md
│   ├── CHARACTERS.md
│   ├── STORYBOARD.md
│   ├── ROUTING.md
│   └── POSTPROD.md
├── models/
│   └── kling.md
├── src/
│   ├── openclaw_gateway/
│   │   ├── index.ts
│   │   ├── channels/
│   │   │   ├── telegram.ts
│   │   │   └── whatsapp.ts
│   │   └── payload.ts
│   └── video_pipeline/
│       ├── __init__.py
│       ├── main.py
│       ├── config.py
│       ├── logging.py
│       ├── orchestrator.py
│       ├── schemas/
│       │   ├── __init__.py
│       │   ├── gateway.py
│       │   ├── script.py
│       │   ├── storyboard.py
│       │   ├── routing.py
│       │   ├── generation.py
│       │   ├── qc.py
│       │   └── job.py
│       ├── agents/
│       │   ├── __init__.py
│       │   ├── script_agent.py
│       │   ├── storyboard_agent.py
│       │   └── routing_agent.py
│       ├── providers/
│       │   ├── __init__.py
│       │   ├── base.py
│       │   ├── fal_video.py
│       │   └── mock.py
│       ├── pipeline/
│       │   ├── __init__.py
│       │   ├── generation.py
│       │   ├── quality_control.py
│       │   ├── postproduction.py
│       │   └── delivery.py
│       ├── media/
│       │   ├── __init__.py
│       │   ├── ffmpeg.py
│       │   ├── subtitles.py
│       │   └── music.py
│       ├── storage/
│       │   ├── __init__.py
│       │   ├── jobs.py
│       │   └── artifacts.py
│       └── utils/
│           ├── __init__.py
│           ├── ids.py
│           ├── retry.py
│           └── cost.py
├── tests/
│   ├── test_schemas.py
│   ├── test_routing.py
│   ├── test_qc.py
│   └── fixtures/
│       ├── gateway_payload.json
│       ├── script.json
│       └── shots.json
└── storage/
    └── jobs/
        └── .gitkeep
```

## Directory Responsibilities / 目录职责

| Path 路径 | Purpose 用途 |
|---|---|
| `docs/` | Human-facing planning, architecture, and development schedule. 面向人的架构、计划和开发节奏文档。 |
| `rules/` | Prompt and deterministic rule files read at runtime. 运行时读取的提示词和规则文件。 |
| `models/` | Provider-specific API notes, limits, costs, and prompt constraints. 各模型 API 的限制、成本、参数和提示词约束。 |
| `src/openclaw_gateway/` | Node.js gateway bridge for Telegram and WhatsApp. Node.js 网关层，连接 Telegram 和 WhatsApp。 |
| `src/video_pipeline/schemas/` | Pydantic data contracts for every boundary. 每个边界的 Pydantic 数据契约。 |
| `src/video_pipeline/agents/` | Script, storyboard, and routing agents. 剧本、分镜和路由 Agent。 |
| `src/video_pipeline/providers/` | fal Kling, mock, and TTS adapters. 视频与 TTS 适配器。 |
| `src/video_pipeline/pipeline/` | Multi-step generation, QC, post-production, and delivery flows. 生成、质检、后期和发送流程。 |
| `src/video_pipeline/media/` | FFmpeg, subtitle, and music helpers. FFmpeg、字幕和配乐工具。 |
| `src/video_pipeline/storage/` | Job state and artifact persistence. 任务状态和产物存储。 |
| `tests/` | Unit tests, integration tests, and sample fixtures. 单测、集成测试和示例数据。 |
| `storage/jobs/` | Local runtime job folders. 本地任务运行目录。 |

## Runtime Job Folder / 单次任务运行目录

Each user request creates one job folder.

每次用户请求都会创建一个任务目录。

```text
storage/jobs/job_20260528_173000/
├── input/
│   └── gateway_payload.json
├── rules_snapshot/
│   ├── MASTER.md
│   ├── CHARACTERS.md
│   ├── STORYBOARD.md
│   ├── ROUTING.md
│   └── POSTPROD.md
├── script/
│   └── script.json
├── storyboard/
│   └── shots.json
├── routing/
│   └── routing.json
├── clips/
│   ├── raw/
│   │   ├── shot_001_seedance_attempt_1.mp4
│   │   └── shot_002_kling_attempt_1.mp4
│   └── validated/
│       ├── shot_001.mp4
│       └── shot_002.mp4
├── reports/
│   ├── generation_report.json
│   ├── qc_report.json
│   ├── cost_report.json
│   └── delivery_report.json
└── final/
    ├── final.srt
    ├── assembled_video.mp4
    ├── subtitled_video.mp4
    └── final.mp4
```

## Naming Rules / 命名规则

- Job IDs: `job_YYYYMMDD_HHMMSS`.
- 任务 ID：`job_YYYYMMDD_HHMMSS`。
- Shot IDs: `shot_001`, `shot_002`, `shot_003`.
- 分镜 ID：`shot_001`, `shot_002`, `shot_003`。
- Raw clip attempts: `{shot_id}_{model}_attempt_{n}.mp4`.
- 原始片段尝试：`{shot_id}_{model}_attempt_{n}.mp4`。
- Validated clips: `{shot_id}.mp4`.
- 质检通过片段：`{shot_id}.mp4`。
- Reports: one JSON report per stage.
- 报告：每个阶段一个 JSON 报告。

## MVP Implementation Order / MVP 实现顺序

1. Create schemas and fixture data.
   创建数据契约和测试样例。
2. Implement mocked pipeline end-to-end.
   先实现 mock 视频模型的端到端流程。
3. Add Telegram gateway.
   接入 Telegram 网关。
4. Add Claude Script Agent and Storyboard Agent.
   接入 Claude 剧本和分镜 Agent。
5. Add real video providers one by one.
   逐个接入真实视频模型。
6. Add QC and FFmpeg post-production.
   加入质检和 FFmpeg 后期。
7. Add WhatsApp delivery.
   最后加入 WhatsApp 回传。

## Environment Configuration / 环境配置

Create `.env.example` before real API integration. Runtime code should read configuration through `src/video_pipeline/config.py` and gateway code should read channel configuration through `src/openclaw_gateway`.

接入真实 API 前先创建 `.env.example`。Python 运行时配置通过 `src/video_pipeline/config.py` 读取，网关配置通过 `src/openclaw_gateway` 读取。

Required MVP keys:

MVP 必要配置项：

```text
# Runtime mode
VIDEO_PIPELINE_ENV=local
VIDEO_PIPELINE_MOCK=true

# Job limits
MAX_CONCURRENT_SHOTS=4
MAX_JOB_COST_USD=5.00
PROVIDER_MAX_ATTEMPTS=2
FALLBACK_MAX_ATTEMPTS=1
QC_MAX_REGENERATIONS=2

# Media defaults
TARGET_RESOLUTION=1920x1080
TARGET_FPS=24
DEFAULT_ASPECT_RATIO=16:9
MIN_VIDEO_DURATION_SEC=15
MAX_VIDEO_DURATION_SEC=45
MAX_SHOT_DURATION_SEC=8

# Claude
ANTHROPIC_API_KEY=
CLAUDE_SCRIPT_MODEL=claude-sonnet-4
CLAUDE_STORYBOARD_MODEL=claude-sonnet-4

# Gateway
TELEGRAM_BOT_TOKEN=
WHATSAPP_ACCESS_TOKEN=
WHATSAPP_PHONE_NUMBER_ID=

# Providers
SEEDANCE_API_KEY=
KLING_API_KEY=
WAN_T2V_API_KEY=
PREMIUM_VIDEO_API_KEY=
```

## Implementation Status / 当前实现状态

The repository currently contains planning docs, rule files, provider notes, and package metadata. The following implementation folders are target folders and may not exist yet:

当前仓库已经包含规划文档、规则文件、模型说明和包配置。以下实现目录是目标结构，可能尚未创建：

- `src/openclaw_gateway/`
- `src/video_pipeline/`
- `tests/`
- `storage/jobs/`

Do not treat missing `src/` as an architecture problem. It means the project is ready for Milestone 1 implementation.

不要把缺少 `src/` 当作架构问题。这表示项目正处于可开始实现里程碑 1 的状态。

## Python Package Boundaries / Python 包边界

- `agents/` should call LLMs or deterministic rule engines and produce JSON artifacts.
- `agents/` 负责调用 LLM 或确定性规则引擎，并输出 JSON 产物。
- `providers/` should know external video API details but should not know job orchestration.
- `providers/` 负责外部视频 API 细节，但不理解整体任务编排。
- `pipeline/` should coordinate generation, QC, post-production, and delivery.
- `pipeline/` 负责编排生成、质检、后期和发送。
- `media/` should wrap FFmpeg, ffprobe, SRT, and music utilities.
- `media/` 封装 FFmpeg、ffprobe、SRT 和音乐工具。
- `storage/` should be the only package that constructs artifact paths.
- `storage/` 应该是唯一负责构造产物路径的包。
- `schemas/` should contain Pydantic contracts used by all boundaries.
- `schemas/` 包含所有边界共享的 Pydantic 数据契约。

## Test Layout / 测试目录

Recommended tests for Milestone 1:

里程碑 1 推荐测试：

```text
tests/
├── test_schemas.py
├── test_orchestrator_mock.py
├── test_routing.py
├── test_qc.py
├── test_postproduction.py
└── fixtures/
    ├── gateway_payload.json
    ├── script.json
    ├── shots.json
    ├── routing.json
    └── tiny_clip.mp4
```

Acceptance:

验收：

- Schema tests reject malformed JSON.
- Schema 测试能拒绝非法 JSON。
- Routing tests cover every rule priority branch.
- 路由测试覆盖每个优先级分支。
- Orchestrator mock test creates a complete job folder.
- 主控 mock 测试能创建完整任务目录。
- QC tests detect duration, fps, resolution, blank-frame, and unreadable-file failures.
- QC 测试覆盖时长、帧率、分辨率、空帧和不可读文件失败。

## Report Files / 报告文件

Each stage should write a machine-readable report. Reports are for debugging, resume logic, and user-facing summaries.

每个阶段都应写入机器可读报告。报告用于调试、恢复逻辑和面向用户的摘要。

```text
reports/
├── script_report.json
├── storyboard_report.json
├── routing_report.json
├── cost_report.json
├── generation_report.json
├── qc_report.json
├── postproduction_report.json
└── delivery_report.json
```

Each report should include:

每个报告应包含：

- `job_id`
- `stage`
- `status`
- `started_at`
- `finished_at`
- `duration_ms`
- `input_artifacts`
- `output_artifacts`
- `warnings`
- `errors`

