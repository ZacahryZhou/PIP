# PIP 续开发备忘

> 更新：2026-06-08  
> **架构唯一权威：** `docs/ARCHITECTURE.md`  
> 仓库：`/Users/yixinzhou/Desktop/PIP`

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
      → Preview → 审批 → （视频/音频/交付：待你定稿）
```

完整图见 **`docs/ARCHITECTURE.md`**。

---

## 实现进度

| 环 | 状态 |
|----|------|
| Intake + Clarification | ✅ |
| Plot（完整剧情） | ✅ 规则/mock |
| Script | ✅ |
| Reference / Character / Scene 从 Intake 分叉 | ✅ orchestrator 分阶段并行 |
| Storyboard ↔ scene_shot_hints | ⚠️ 部分 |
| 下游 Preview / 视频 / 交付 | 🔄 待你对齐定稿 |

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
