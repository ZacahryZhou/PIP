# Development Task Roadmap / 开发任务流程表

This roadmap assumes one developer building a working MVP in 2 to 3 weeks. Each phase produces a usable artifact so development can move step by step.

本流程表按一个开发者 2 到 3 周完成 MVP 估算。每个阶段都要产出可验证的结果，方便一步步推进。

## Summary Timeline / 总体时间线

| Time 时间 | Phase 阶段 | Goal 目标 | Deliverable 产出 |
|---|---|---|---|
| Day 1 | Foundation | Project setup and contracts. 搭建项目基础和数据契约。 | Repo skeleton, schemas, fixtures |
| Day 2 | Local Orchestrator | Run one job through mocked stages. 本地跑通一个 mock 任务。 | Job folder with JSON artifacts |
| Day 3 | Script Agent | Generate validated `script.json`. 生成并校验剧本 JSON。 | Claude script call + schema validation |
| Day 4 | Storyboard Agent | Generate validated `shots.json`. 生成并校验分镜 JSON。 | Shot splitting and character injection |
| Day 5 | Routing Agent | Assign model routes and costs. 分配模型和成本估算。 | `routing.json` |
| Days 6-7 | Mock E2E | Full mock generation pipeline. 完整 mock 端到端。 | Fake clips, QC report, final mock video |
| Week 2 Days 1-2 | Real Provider 1 | Add first real video model. 接入第一个真实视频模型。 | Seedance or Kling adapter |
| Week 2 Day 3 | QC Loop | Regenerate failed clips. 失败片段自动重试。 | QC retry loop |
| Week 2 Day 4 | Post-production | FFmpeg assembly, SRT, music. FFmpeg 合成、字幕、配乐。 | `final.mp4` |
| Week 2 Day 5 | Telegram Delivery | Send final video to user. Telegram 自动回传。 | Delivered video |
| Week 3 | Hardening | WhatsApp, monitoring, cost reports. WhatsApp、监控、成本报告。 | Stable MVP |

## Engineering Guardrails / 工程护栏

These rules apply to every phase.

以下规则适用于所有阶段。

- Build the mock pipeline before connecting real video APIs.
- 先跑通 mock 流水线，再接真实视频 API。
- Every boundary must have a Pydantic schema or Zod schema.
- 每个边界必须有 Pydantic 或 Zod 数据契约。
- Every stage must write an artifact and a report.
- 每个阶段必须写入产物和报告。
- The orchestrator must be resumable from the latest valid artifact.
- 主控流程必须能从最近的有效产物恢复。
- Routing must be deterministic Python logic, not another LLM call.
- 路由必须是确定性 Python 逻辑，不再调用 LLM。
- Generation must use bounded concurrency, not unlimited parallel API calls.
- 生成层必须使用有上限并发，不能无限并行调用 API。
- Cost must be estimated before generation starts.
- 生成开始前必须先估算成本。
- QC retry loops must have max retry limits.
- QC 重试循环必须有最大重试次数。

## Recommended First PR / 推荐第一个 PR

The first implementation PR should be small and boring:

第一个实现 PR 应该小而稳定：

- Create `src/video_pipeline/schemas/`.
- 创建 `src/video_pipeline/schemas/`。
- Add fixtures under `tests/fixtures/`.
- 在 `tests/fixtures/` 添加样例。
- Add schema tests.
- 添加 schema 测试。
- Add minimal `config.py`.
- 添加最小 `config.py`。

Do not include Claude calls, video providers, Telegram, WhatsApp, or FFmpeg in the first PR.

第一个 PR 不要包含 Claude 调用、视频供应商、Telegram、WhatsApp 或 FFmpeg。

Acceptance command:

验收命令：

```bash
pytest tests/test_schemas.py
```

## Recommended Second PR / 推荐第二个 PR

The second implementation PR should create the local job lifecycle:

第二个实现 PR 应创建本地任务生命周期：

- CLI accepts `--payload`.
- CLI 支持 `--payload`。
- Orchestrator creates a job folder.
- 主控创建任务目录。
- Rules are snapshotted into `rules_snapshot/`.
- 规则复制到 `rules_snapshot/`。
- Mock stages write `script.json`, `shots.json`, and `routing.json`.
- Mock 阶段写入 `script.json`、`shots.json` 和 `routing.json`。
- `job_state.json` is updated after every stage.
- 每个阶段后更新 `job_state.json`。

Acceptance command:

验收命令：

```bash
python -m video_pipeline.main --payload tests/fixtures/gateway_payload.json --mock --stop-after routing
```

## Recommended Third PR / 推荐第三个 PR

The third implementation PR should produce a playable mock final video:

第三个实现 PR 应生成可播放的 mock 最终视频：

- Mock provider generates small mp4 clips.
- Mock provider 生成小 mp4 片段。
- QC validates or normalizes clips.
- QC 校验或标准化片段。
- FFmpeg assembles `final.mp4`.
- FFmpeg 合成 `final.mp4`。
- Reports include generation, QC, and post-production details.
- 报告包含生成、质检和后期细节。

Acceptance command:

验收命令：

```bash
python -m video_pipeline.main --payload tests/fixtures/gateway_payload.json --mock
```

## Phase 0: Product and API Preparation / 产品与 API 准备

### Task 0.1: Decide MVP Channel / 确定 MVP 渠道

What to do:

要做什么：

- Use Telegram as the first channel because setup is faster and debugging is easier.
- 第一版建议先用 Telegram，因为配置更快、调试更简单。
- Keep WhatsApp as Phase 2 unless WhatsApp is mandatory for the first demo.
- WhatsApp 除非首个演示必须使用，否则放到第二阶段。

Output:

产出：

- Telegram bot token.
- Telegram 机器人 token。
- One test user or test group.
- 一个测试用户或测试群。

Acceptance criteria:

验收标准：

- The bot can receive a text message.
- 机器人能收到文字消息。
- The bot can send back a simple test reply.
- 机器人能回传简单测试消息。

### Task 0.2: Decide Video Defaults / 确定视频默认参数

What to do:

要做什么：

- Set target resolution to `1920x1080`.
- 默认分辨率设为 `1920x1080`。
- Set target fps to `24`.
- 默认帧率设为 `24`。
- Set MVP total duration range to `15-45` seconds.
- MVP 总时长范围设为 `15-45` 秒。
- Set max shot duration to `8` seconds.
- 单镜头最长 `8` 秒。

Output:

产出：

- `.env` values.
- `.env` 配置。
- Constants in config.
- 配置常量。

Acceptance criteria:

验收标准：

- Every generated job uses the same target fps and resolution unless overridden.
- 每个任务默认使用相同帧率和分辨率，除非主动覆盖。

## Phase 1: Project Foundation / 项目基础

### Task 1.1: Create Python Package / 创建 Python 包

What to do:

要做什么：

- Create `src/video_pipeline`.
- 创建 `src/video_pipeline`。
- Add `config.py`, `orchestrator.py`, `main.py`.
- 添加 `config.py`、`orchestrator.py`、`main.py`。
- Add structured logging.
- 添加结构化日志。

Output:

产出：

- CLI entrypoint that accepts a payload JSON path.
- 可接收 payload JSON 路径的 CLI 入口。

Acceptance criteria:

验收标准：

- Running `python -m video_pipeline.main --payload tests/fixtures/gateway_payload.json` creates a job folder.
- 执行该命令后能创建任务目录。

### Task 1.2: Define Pydantic Schemas / 定义 Pydantic 数据契约

What to do:

要做什么：

- Define `GatewayPayload`.
- 定义 `GatewayPayload`。
- Define `ScriptPlan`.
- 定义 `ScriptPlan`。
- Define `Shot`.
- 定义 `Shot`。
- Define `RoutingDecision`.
- 定义 `RoutingDecision`。
- Define `GenerationResult`, `QCReport`, `JobState`.
- 定义 `GenerationResult`、`QCReport`、`JobState`。

Output:

产出：

- `src/video_pipeline/schemas/*.py`.
- Schema fixture tests.
- 数据契约 fixture 测试。

Acceptance criteria:

验收标准：

- Invalid JSON fails early with useful error messages.
- 非法 JSON 会尽早失败并给出清晰错误。

### Task 1.3: Artifact Storage / 产物存储

What to do:

要做什么：

- Create one job folder per request.
- 每个请求创建一个任务目录。
- Save input, stage output, logs, reports, clips, and final video in fixed locations.
- 按固定位置保存输入、阶段输出、日志、报告、片段和最终视频。

Output:

产出：

- `storage/artifacts.py`.
- Job folder helper functions.
- 任务目录工具函数。

Acceptance criteria:

验收标准：

- A failed job can be inspected by opening its folder.
- 打开任务目录即可查看失败原因和中间产物。

## Phase 2: Gateway and Orchestrator / 网关与主控

### Task 2.1: Gateway Payload Contract / 网关 Payload 契约

What to do:

要做什么：

- Normalize Telegram and WhatsApp messages to the same payload.
- 将 Telegram 和 WhatsApp 消息标准化为同一个 payload。
- Include `raw_prompt`, `channel`, `user_id`, `timestamp`.
- 包含 `raw_prompt`、`channel`、`user_id`、`timestamp`。
- Pass JSON path to Python subprocess.
- 将 JSON 路径传给 Python 子进程。

Output:

产出：

- `src/openclaw_gateway/payload.ts`.
- `gateway_payload.json`.

Acceptance criteria:

验收标准：

- The Python orchestrator receives identical structure from both channels.
- Python 主控从两个渠道接收到的数据结构一致。

### Task 2.2: Orchestrator State Machine / 主控状态机

What to do:

要做什么：

- Implement stages: `received`, `scripted`, `storyboarded`, `routed`, `generated`, `validated`, `assembled`, `delivered`, `failed`.
- 实现任务状态：`received`、`scripted`、`storyboarded`、`routed`、`generated`、`validated`、`assembled`、`delivered`、`failed`。
- Save state after every stage.
- 每个阶段完成后保存状态。

Output:

产出：

- `orchestrator.py`.
- `job_state.json`.

Acceptance criteria:

验收标准：

- Restarting a job can skip already completed stages.
- 重启任务时可以跳过已完成阶段。

## Phase 3: Script Agent / 剧本 Agent

### Task 3.1: Rule Files / 规则文件

What to do:

要做什么：

- Write `rules/MASTER.md`.
- 编写 `rules/MASTER.md`。
- Write `rules/CHARACTERS.md`.
- 编写 `rules/CHARACTERS.md`。
- Include style, duration, safety, output JSON schema, and character library.
- 包含风格、时长、安全规则、输出 JSON schema 和角色库。

Output:

产出：

- Runtime-readable prompt files.
- 运行时可读取的提示词文件。

Acceptance criteria:

验收标准：

- Script Agent does not hardcode creative rules in Python.
- 剧本 Agent 不在 Python 里硬编码创意规则。

### Task 3.2: Claude Script Call / Claude 剧本调用

What to do:

要做什么：

- Inject `raw_prompt`, `MASTER.md`, and `CHARACTERS.md`.
- 注入 `raw_prompt`、`MASTER.md` 和 `CHARACTERS.md`。
- Request strict JSON output.
- 要求严格 JSON 输出。
- Validate with Pydantic.
- 使用 Pydantic 校验。

Output:

产出：

- `script.json`.

Acceptance criteria:

验收标准：

- The output includes narrative arc, style, color tone, music mood, BPM, camera language, characters, total duration, and scene list.
- 输出包含叙事弧线、视觉风格、色调、音乐情绪、BPM、镜头语言、角色、总时长和场景列表。

## Phase 4: Storyboard Agent / 分镜 Agent

### Task 4.1: Shot Splitting Rules / 分镜拆分规则

What to do:

要做什么：

- Split when camera movement changes.
- 运镜改变时拆分。
- Split when subject or character changes.
- 主体或角色改变时拆分。
- Split when location changes.
- 场景地点改变时拆分。
- Split when continuous action exceeds 8 seconds.
- 连续动作超过 8 秒时拆分。

Output:

产出：

- `shots.json`.

Acceptance criteria:

验收标准：

- No shot duration exceeds 8 seconds.
- 没有镜头超过 8 秒。
- Every shot has `shot_id`, `duration_sec`, `subject`, `camera_move`, `action`, `mood`, `scene_type`, `motion_intensity`, `has_characters`.
- 每个分镜都有完整字段。

### Task 4.2: Character Prompt Injection / 角色提示词注入

What to do:

要做什么：

- Match `characters_in_use` from `script.json`.
- 匹配 `script.json` 里的使用角色。
- Inject character descriptions from `CHARACTERS.md`.
- 从 `CHARACTERS.md` 注入角色描述。

Output:

产出：

- `character_prompts` field per shot.
- 每个分镜的 `character_prompts` 字段。

Acceptance criteria:

验收标准：

- Any shot with characters has enough visual description for video generation.
- 有人物的镜头都具备足够的视频生成视觉描述。

## Phase 5: Routing Agent / 路由 Agent

### Task 5.1: Routing Matrix / 路由矩阵

What to do:

要做什么：

- Implement rules from `ROUTING.md`.
- 实现 `ROUTING.md` 中的规则。
- Implement rule priority exactly as written in `ROUTING.md`.
- 严格按照 `ROUTING.md` 中的优先级判断规则。
- Characters plus high motion: Seedance primary, Kling fallback.
- 人物加高动作：Seedance 首选，Kling 备用。
- Realistic scene: Kling primary, Wan fallback.
- 写实场景：Kling 首选，Wan 备用。
- Simple batch: Wan T2V primary, Kling fallback.
- 简单批量：Wan T2V 首选，Kling 备用。
- Creative abstract: premium API primary, Kling fallback.
- 创意抽象：高端 API 首选，Kling 备用。

Output:

产出：

- `routing.json`.

Acceptance criteria:

验收标准：

- Routing is deterministic and testable without Claude.
- 路由是确定性的，不依赖 Claude，也可测试。
- Ambiguous shots match only the highest-priority route.
- 多条件命中的镜头只采用最高优先级路由。
- Generation workers read model choice from `routing.json`, not `shots.json`.
- 生成 Worker 从 `routing.json` 读取模型选择，而不是 `shots.json`。

### Task 5.2: Cost Estimator / 成本估算

What to do:

要做什么：

- Store per-second or per-shot model cost.
- 保存每秒或每镜头模型成本。
- Estimate per-shot cost and total job cost.
- 估算单镜头成本和总任务成本。
- Compare total estimated cost against `MAX_JOB_COST_USD`.
- 将总预估成本与 `MAX_JOB_COST_USD` 比较。
- Set `should_continue=false` when budget is exceeded.
- 超出预算时设置 `should_continue=false`。

Output:

产出：

- `cost_report.json`.
- `routing.json` with `should_continue`.
- 带有 `should_continue` 的 `routing.json`。

Acceptance criteria:

验收标准：

- User can see estimated cost before generation begins.
- 生成开始前能看到预估成本。
- No real provider request is made when `should_continue=false`.
- 当 `should_continue=false` 时，不发起真实供应商请求。

## Phase 6: Parallel Video Generation / 并行视频生成

### Task 6.1: Provider Interface / 模型供应商接口

What to do:

要做什么：

- Define a shared `VideoProvider` interface.
- 定义统一 `VideoProvider` 接口。
- Method: `generate(shot, route, output_path)`.
- 方法：`generate(shot, route, output_path)`。
- Implement mock provider first.
- 先实现 mock provider。

Output:

产出：

- `providers/base.py`.
- `providers/mock.py`.

Acceptance criteria:

验收标准：

- Mock provider creates placeholder clips for all shots.
- Mock provider 能为所有分镜创建占位视频。

### Task 6.2: Async Generation and Fallback / 异步生成与备用模型

What to do:

要做什么：

- Dispatch shots with `asyncio.gather` plus a semaphore concurrency limit.
- 使用 `asyncio.gather` 加 semaphore 并发上限分发镜头。
- Try preferred model first.
- 先调用首选模型。
- Retry according to policy.
- 按策略重试。
- Switch to fallback model after preferred model fails.
- 首选失败后切换备用模型。
- Isolate failed shots.
- 隔离失败镜头。

Output:

产出：

- `generation_report.json`.
- Raw clip files.
- 原始视频片段。

Acceptance criteria:

验收标准：

- One failed shot does not stop other shots.
- 单个镜头失败不影响其他镜头。
- The number of simultaneous provider calls never exceeds `MAX_CONCURRENT_SHOTS`.
- 同时进行的供应商调用数量不超过 `MAX_CONCURRENT_SHOTS`。
- Attempt history is written per shot.
- 每个镜头写入尝试历史。

## Phase 7: Quality Control / 质检

### Task 7.1: Media Validation / 媒体验证

What to do:

要做什么：

- Validate duration within `±0.5s`.
- 校验时长误差不超过 `±0.5s`。
- Validate resolution consistency.
- 校验分辨率一致。
- Normalize or validate fps to 24.
- 统一或校验帧率为 24。
- Detect all-black and all-white abnormal frames.
- 检测全黑和全白异常帧。
- Validate mp4 readability.
- 校验 mp4 可读取。

Output:

产出：

- `qc_report.json`.
- Validated clips folder.
- 质检通过片段目录。

Acceptance criteria:

验收标准：

- Bad clips are listed with exact failed checks.
- 问题片段会列出具体失败项。

### Task 7.2: QC Regeneration Loop / 质检重生成循环

What to do:

要做什么：

- Send failed shot IDs back to generation.
- 将失败分镜 ID 送回生成流程。
- Reuse the same preferred to fallback logic.
- 复用首选到备用逻辑。
- Stop after max retry limit.
- 达到最大重试次数后停止。
- Keep successful validated clips untouched.
- 保持已通过质检的片段不变。

Output:

产出：

- Updated generation and QC reports.
- 更新后的生成报告和质检报告。

Acceptance criteria:

验收标准：

- The pipeline enters post-production only when all clips pass.
- 只有全部片段通过后才进入后期。
- A permanently failed shot produces a clear failure report instead of an infinite loop.
- 永久失败的镜头生成清晰失败报告，而不是无限循环。

## Phase 8: Post-production / 后期合成

### Task 8.1: Timeline Assembly / 时间线拼接

What to do:

要做什么：

- Sort clips by `shot_id`.
- 按 `shot_id` 排序。
- Match transition by `mood`.
- 按 `mood` 匹配转场。
- Use hard cut, crossfade, dissolve, or fade to black.
- 使用直切、交叉淡入淡出、溶解或黑场淡出。
- Write real timing to `timeline.json`.
- 将真实时间写入 `timeline.json`。

Output:

产出：

- `assembled_video.mp4`.
- `timeline.json`.

Acceptance criteria:

验收标准：

- Final timeline order matches `shots.json`.
- 最终时间线顺序与 `shots.json` 一致。
- Subtitle timing can be derived from `timeline.json`.
- 字幕时间可以从 `timeline.json` 派生。

### Task 8.2: Subtitles and Music / 字幕与配乐

What to do:

要做什么：

- Generate SRT from script dialogue.
- 从剧本台词生成 SRT。
- Assemble video first to get real final duration.
- 先合成视频以获得真实总时长。
- Fit music to final duration.
- 将配乐匹配到最终时长。
- Use FFmpeg `afade` for ending fade-out.
- 使用 FFmpeg `afade` 做结尾淡出。

Output:

产出：

- `final.srt`.
- `subtitled_video.mp4`.
- `final.mp4`.

Acceptance criteria:

验收标准：

- `final.mp4` plays from start to finish with subtitles and music.
- `final.mp4` 可完整播放，包含字幕和配乐。

## Phase 9: Delivery / 自动回传

### Task 9.1: Telegram Delivery / Telegram 回传

What to do:

要做什么：

- Send `final.mp4` to original Telegram user.
- 将 `final.mp4` 发回原 Telegram 用户。
- Send generation summary and cost report.
- 发送生成摘要和成本报告。

Output:

产出：

- Delivered video.
- 已发送视频。
- `delivery_report.json`.

Acceptance criteria:

验收标准：

- User receives the final video without manual file handling.
- 用户无需手动处理文件即可收到视频。

### Task 9.2: WhatsApp Delivery / WhatsApp 回传

What to do:

要做什么：

- Add WhatsApp Cloud API or local prototype integration.
- 接入 WhatsApp Cloud API 或本地原型方案。
- Reuse the same payload and delivery interface.
- 复用同一个 payload 和 delivery 接口。

Output:

产出：

- WhatsApp channel support.
- WhatsApp 渠道支持。

Acceptance criteria:

验收标准：

- Telegram and WhatsApp share the same Python pipeline.
- Telegram 和 WhatsApp 共用同一条 Python 流水线。

## Phase 10: Hardening / 稳定性强化

### Task 10.1: Error Handling / 错误处理

What to do:

要做什么：

- Add error categories: validation, provider, media, delivery, unknown.
- 添加错误分类：校验、模型、媒体、发送、未知。
- Add user-facing failure messages.
- 添加面向用户的失败消息。
- Save stack traces only in logs.
- 堆栈只保存到日志。

Output:

产出：

- Clear failure reports.
- 清晰失败报告。

Acceptance criteria:

验收标准：

- User sees a simple explanation, developer sees full logs.
- 用户看到简单解释，开发者能看到完整日志。

### Task 10.2: Monitoring and Cost Control / 监控与成本控制

What to do:

要做什么：

- Log duration per stage.
- 记录每个阶段耗时。
- Log API cost per shot.
- 记录每镜头 API 成本。
- Add max cost per job.
- 添加单任务最大成本限制。

Output:

产出：

- `cost_report.json`.
- `generation_log.jsonl`.

Acceptance criteria:

验收标准：

- A job can be stopped before generation if estimated cost is too high.
- 如果预估成本过高，可以在生成前停止任务。

## First Milestone Checklist / 第一个里程碑检查清单

The first milestone should be completed before any real video API is connected.

在接入真实视频 API 前，必须先完成第一个里程碑。

- `gateway_payload.json` fixture exists.
- 存在 `gateway_payload.json` 测试样例。
- Schemas validate sample script, shots, and routing.
- Schema 能校验剧本、分镜和路由样例。
- Orchestrator creates a job folder.
- 主控能创建任务目录。
- Mock Script Agent creates valid `script.json`.
- Mock 剧本 Agent 能创建合法 `script.json`。
- Mock Storyboard Agent creates valid `shots.json`.
- Mock 分镜 Agent 能创建合法 `shots.json`。
- Routing Agent creates deterministic `routing.json`.
- 路由 Agent 能创建确定性 `routing.json`。
- Mock provider creates placeholder clips.
- Mock provider 能创建占位视频片段。
- QC can pass or fail clips with a report.
- QC 能生成通过/失败报告。
- FFmpeg can assemble a local `final.mp4`.
- FFmpeg 能在本地合成 `final.mp4`。

