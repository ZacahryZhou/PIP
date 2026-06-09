# PIP 续开发备忘

> 更新：2026-06-08 — **Multi-Agent 重构中**  
> **架构唯一权威：** `docs/ARCHITECTURE.md`  
> 仓库：`/Users/yixinzhou/Desktop/PIP`

---

## 当前在做什么

**按定稿架构重构：** Intake 一分五路（叙事左支 + 资产右支并行），不再按旧 V2 线性文档开发。

旧架构文档已全部删除（`NEW_ARCHITECTURE_V2.md`、`NEW_ARCHITECTURE_TASKFLOW.md`、`PIP_DEVELOPMENT_FLOW.md` 等）。

---

## 定稿架构（速览）

```text
用户：文字 + 图片
  → Intake Agent（分析 + 分类 + 缺口询问）
      ├─ 无完整剧情 → Plot 生成完整剧情 ─┐
      ├─ 有剧情/剧本 → Plot review 补全 ──┼→ Script → Storyboard（scene_shot_hints）
      ├─ 人物图     → Character Agent ────┤
      ├─ 场景图     → Scene Agent ──────────┼→ 缺图 → API 生成
      └─ 其它参考图 → Reference Agent ────┘
```

完整图见 **`docs/ARCHITECTURE.md`**。

---

## 实现进度

| 环 | 状态 |
|----|------|
| Intake + Clarification | ✅ |
| Plot（完整剧情） | ✅ 规则/mock |
| Script | ✅ |
| Storyboard ↔ scene_shot_hints | ⏭ |
| Character / Scene / Reference 从 Intake 分叉 | ⏭ |
| 下游 Preview / Kling / 交付 | 🔄 待对齐重构 |

---

## 回来先跑

```bash
cd ~/Desktop/PIP
source .venv/bin/activate
pytest tests/ -q
python -m video_pipeline.main \
  --payload tests/fixtures/gateway_payload.json \
  --mock --skip-approval
```

---

## `.env`

见 `.env.example`。不要把 Key 提交进 git。
