# Next Milestone / 下一开发里程碑

## Milestone 1: Local Mock End-to-End Pipeline / 里程碑 1：本地 Mock 端到端流水线

Goal:

目标：

Build the whole pipeline locally without calling paid video APIs. This proves the architecture, JSON contracts, job folders, routing, QC, and FFmpeg assembly before API money is spent.

先不调用付费视频 API，在本地跑通完整流水线。这样可以先验证架构、JSON 契约、任务目录、路由、质检和 FFmpeg 合成，再接真实模型。

## What You Should Build First / 你第一步应该做什么

1. Implement Pydantic schemas.
   实现 Pydantic 数据契约。
2. Add sample fixtures in `tests/fixtures`.
   在 `tests/fixtures` 中加入样例数据。
3. Implement a CLI entrypoint that accepts `gateway_payload.json`.
   实现一个能接收 `gateway_payload.json` 的 CLI 入口。
4. Create a job folder and save every stage artifact.
   创建任务目录，并保存每个阶段产物。
5. Use mock agents to produce `script.json`, `shots.json`, and `routing.json`.
   使用 mock Agent 生成 `script.json`、`shots.json` 和 `routing.json`。
6. Use mock video provider to generate placeholder clips.
   使用 mock 视频供应商生成占位视频片段。
7. Run QC on placeholder clips.
   对占位片段进行质检。
8. Use FFmpeg to assemble `final.mp4`.
   使用 FFmpeg 合成 `final.mp4`。

## Definition of Done / 完成标准

- One local command can run the whole mock pipeline.
- 一个本地命令可以跑完整 mock 流水线。
- The job folder contains input, script, shots, routing, clips, reports, and final video.
- 任务目录包含输入、剧本、分镜、路由、片段、报告和最终视频。
- All JSON artifacts validate against schemas.
- 所有 JSON 产物都能通过 schema 校验。
- The mock `final.mp4` can be opened locally.
- mock `final.mp4` 可以在本地打开播放。

## Suggested Command / 建议命令

```bash
python -m video_pipeline.main --payload tests/fixtures/gateway_payload.json --mock
```

## Detailed Execution Plan / 详细执行计划

### Step 1: Create Contracts / 第一步：创建数据契约

Files to create:

需要创建的文件：

- `src/video_pipeline/schemas/gateway.py`
- `src/video_pipeline/schemas/script.py`
- `src/video_pipeline/schemas/storyboard.py`
- `src/video_pipeline/schemas/routing.py`
- `src/video_pipeline/schemas/generation.py`
- `src/video_pipeline/schemas/qc.py`
- `src/video_pipeline/schemas/job.py`

Acceptance:

验收：

- `pytest tests/test_schemas.py` passes.
- `pytest tests/test_schemas.py` 通过。
- Invalid fixture JSON fails with readable validation messages.
- 非法 fixture JSON 会给出可读校验错误。

### Step 2: Create Fixture Artifacts / 第二步：创建样例产物

Files to create:

需要创建的文件：

- `tests/fixtures/gateway_payload.json`
- `tests/fixtures/script.json`
- `tests/fixtures/shots.json`
- `tests/fixtures/routing.json`

Acceptance:

验收：

- Fixtures represent one complete 15-30 second sample job.
- fixture 能代表一个完整的 15-30 秒样例任务。
- `script.json` duration matches scene durations.
- `script.json` 总时长与场景时长匹配。
- `shots.json` duration matches script duration.
- `shots.json` 总时长与剧本总时长匹配。

### Step 3: Implement Job Storage / 第三步：实现任务存储

Files to create:

需要创建的文件：

- `src/video_pipeline/storage/jobs.py`
- `src/video_pipeline/storage/artifacts.py`

Acceptance:

验收：

- A job folder is created under `storage/jobs/job_YYYYMMDD_HHMMSS`.
- 在 `storage/jobs/job_YYYYMMDD_HHMMSS` 下创建任务目录。
- Rules are snapshotted into `rules_snapshot/`.
- 规则文件会复制到 `rules_snapshot/`。
- Every stage writes to a stable path.
- 每个阶段写入稳定路径。

### Step 4: Implement Mock Agents / 第四步：实现 Mock Agent

Files to create:

需要创建的文件：

- `src/video_pipeline/agents/script_agent.py`
- `src/video_pipeline/agents/storyboard_agent.py`
- `src/video_pipeline/agents/routing_agent.py`

Acceptance:

验收：

- Mock Script Agent writes valid `script.json`.
- Mock 剧本 Agent 写出合法 `script.json`。
- Mock Storyboard Agent writes valid `shots.json`.
- Mock 分镜 Agent 写出合法 `shots.json`。
- Routing Agent uses deterministic rules from `ROUTING.md`.
- Routing Agent 使用 `ROUTING.md` 的确定性规则。

### Step 5: Implement Mock Provider / 第五步：实现 Mock 视频生成

Files to create:

需要创建的文件：

- `src/video_pipeline/providers/base.py`
- `src/video_pipeline/providers/mock.py`
- `src/video_pipeline/pipeline/generation.py`

Acceptance:

验收：

- Mock provider creates one small playable mp4 per shot.
- Mock provider 为每个镜头生成一个可播放的小 mp4。
- Generation report records preferred/fallback attempts, even in mock mode.
- 即使在 mock 模式，生成报告也记录首选/备用尝试。
- Concurrency limit is applied.
- 并发上限生效。

### Step 6: Implement QC / 第六步：实现质检

Files to create:

需要创建的文件：

- `src/video_pipeline/pipeline/quality_control.py`
- `src/video_pipeline/media/ffmpeg.py`

Acceptance:

验收：

- QC verifies duration, fps, resolution, blank frames, and mp4 readability.
- QC 校验时长、帧率、分辨率、空帧和 mp4 可读性。
- Failed clips are reported with exact failed check names.
- 失败片段会报告具体失败检查名。
- Validated clips are copied or normalized into `clips/validated/`.
- 通过的片段会复制或标准化到 `clips/validated/`。

### Step 7: Implement Post-production / 第七步：实现后期

Files to create:

需要创建的文件：

- `src/video_pipeline/pipeline/postproduction.py`
- `src/video_pipeline/media/subtitles.py`
- `src/video_pipeline/media/music.py`

Acceptance:

验收：

- FFmpeg assembles all validated clips in shot order.
- FFmpeg 按镜头顺序拼接所有通过质检的片段。
- `timeline.json` is written.
- 写入 `timeline.json`。
- `final.mp4` can be opened locally.
- `final.mp4` 可以在本地打开播放。

### Step 8: Implement CLI Orchestrator / 第八步：实现 CLI 主控

Files to create:

需要创建的文件：

- `src/video_pipeline/main.py`
- `src/video_pipeline/orchestrator.py`
- `src/video_pipeline/config.py`
- `src/video_pipeline/logging.py`

Acceptance:

验收：

- The suggested command runs the whole mock pipeline.
- 建议命令可以跑完整 mock 流水线。
- `job_state.json` updates after every stage.
- 每个阶段后更新 `job_state.json`。
- Re-running a completed job can skip valid completed stages.
- 重新运行已完成任务时可以跳过已完成且有效的阶段。

## What Not To Do Yet / 暂时不要做什么

- Do not connect Seedance, Kling, or Wan before the mock pipeline works.
- mock 流水线跑通前，不要接 Seedance、Kling 或 Wan。
- Do not optimize prompts before schemas are stable.
- schema 稳定前，不要过早优化提示词。
- Do not build WhatsApp first unless Telegram is already working.
- Telegram 未跑通前，不要优先做 WhatsApp。

## Stop Conditions / 停止条件

Stop Milestone 1 work and fix foundations if any of these happen:

如果出现以下情况，停止继续堆功能，先修基础：

- JSON artifacts cannot be validated consistently.
- JSON 产物无法稳定通过校验。
- Job folders are hard to inspect manually.
- 任务目录无法人工快速排查。
- A failed stage does not leave enough report data.
- 失败阶段没有留下足够报告数据。
- Mock provider cannot produce playable clips.
- Mock provider 无法生成可播放片段。
- FFmpeg command is too brittle to reproduce in tests.
- FFmpeg 命令过于脆弱，无法在测试中复现。

## After Milestone 1 / 里程碑 1 之后

Only after the mock command produces a playable `final.mp4`, move to:

只有 mock 命令能生成可播放的 `final.mp4` 后，才进入：

1. Telegram gateway receive/send loop.
   Telegram 网关收发闭环。
2. Claude Script Agent.
   Claude 剧本 Agent。
3. Claude Storyboard Agent.
   Claude 分镜 Agent。
4. First real video provider.
   第一个真实视频供应商。
5. Provider fallback and QC regeneration loop.
   供应商备用模型和 QC 重生成循环。

