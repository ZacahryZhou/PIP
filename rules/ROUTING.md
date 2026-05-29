# Routing Rules / 路由规则

## Decision Matrix / 决策矩阵

| Condition 条件 | Primary 首选 | Fallback 备用 |
|---|---|---|
| `has_characters=true` and `motion_intensity=high` / 有人物且强动作 | Seedance | Kling |
| `scene_type=realistic` / 写实场景 | Kling | Wan T2V |
| `scene_type=simple` or low-cost batch / 简单批量 | Wan T2V | Kling |
| `scene_type=creative` or abstract / 创意抽象 | Premium API | Kling |

## Cost Rules / 成本规则

- Estimate cost before generation.
- 生成前先估算成本。
- Store per-shot and total cost.
- 保存单镜头成本和总成本。
- Stop the job before generation if estimated total cost exceeds configured maximum.
- 如果预估总成本超过配置上限，在生成前停止。

## Deterministic Priority / 确定性优先级

Routing rules must be evaluated in this exact order. The first matching rule wins.

路由规则必须按以下顺序判断。第一个命中的规则就是最终结果。

1. Character plus high motion.
   有人物且强动作。
2. Creative or abstract scene.
   创意或抽象场景。
3. Realistic scene.
   写实场景。
4. Simple or low-cost batch scene.
   简单或低成本批量场景。
5. Default fallback.
   默认兜底。

This avoids ambiguous cases such as a shot that is both `has_characters=true` and `scene_type=realistic`.

这样可以避免同时满足多条规则的冲突，例如一个镜头既有人物又是写实场景。

## Routing Output Contract / 路由输出契约

The Routing Agent must output:

Routing Agent 必须输出：

```json
{
  "routes": [
    {
      "shot_id": "shot_001",
      "preferred_model": "seedance",
      "fallback_model": "kling",
      "routing_reason": "has_characters=true and motion_intensity=high",
      "estimated_cost_per_shot": 0.45,
      "estimated_duration_sec": 4
    }
  ],
  "total_estimated_cost": 3.6,
  "currency": "USD",
  "should_continue": true,
  "budget_message": null
}
```

## Default Routing Rules / 默认路由规则

- If `has_characters=true` and `motion_intensity=high`: primary `seedance`, fallback `kling`.
- 如果 `has_characters=true` 且 `motion_intensity=high`：首选 `seedance`，备用 `kling`。
- Else if `scene_type=creative` or `scene_type=abstract`: primary `premium_api`, fallback `kling`.
- 否则如果 `scene_type=creative` 或 `scene_type=abstract`：首选 `premium_api`，备用 `kling`。
- Else if `scene_type=realistic`: primary `kling`, fallback `wan_t2v`.
- 否则如果 `scene_type=realistic`：首选 `kling`，备用 `wan_t2v`。
- Else if `scene_type=simple` or `motion_intensity=low`: primary `wan_t2v`, fallback `kling`.
- 否则如果 `scene_type=simple` 或 `motion_intensity=low`：首选 `wan_t2v`，备用 `kling`。
- Else: primary `kling`, fallback `wan_t2v`.
- 其他情况：首选 `kling`，备用 `wan_t2v`。

## Budget Gate / 预算闸门

The Routing Agent must compare `total_estimated_cost` against configured `MAX_JOB_COST_USD`.

Routing Agent 必须将 `total_estimated_cost` 与配置项 `MAX_JOB_COST_USD` 比较。

- If the estimate is within budget, set `should_continue=true`.
- 如果预估成本在预算内，设置 `should_continue=true`。
- If the estimate exceeds budget, set `should_continue=false` and write a human-readable `budget_message`.
- 如果预估成本超过预算，设置 `should_continue=false` 并写入人类可读的 `budget_message`。
- The orchestrator must not call any video provider when `should_continue=false`.
- 当 `should_continue=false` 时，主控流程不得调用任何视频供应商。

## Cost Estimation Defaults / 成本估算默认值

Until real provider pricing is confirmed, use conservative placeholder values:

在真实供应商价格确认前，使用保守占位值：

| Model 模型 | Estimated Cost 估算成本 |
|---|---|
| `seedance` | `$0.10` per second |
| `kling` | `$0.08` per second |
| `wan_t2v` | `$0.03` per second |
| `premium_api` | `$0.20` per second |

Round each shot cost up to the nearest whole second.

每个镜头成本按秒向上取整。

