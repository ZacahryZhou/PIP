# PIP — Multi-Agent 视频流水线

OpenClaw / Telegram 驱动的文本 + 图片 → 短视频自动化系统。

## 文档

| 文件 | 用途 |
|------|------|
| **`docs/ARCHITECTURE.md`** | **架构唯一权威** |
| `docs/RESUME_HERE.md` | 续开发入口 |
| `docs/COST_AND_OPTIMIZATION.md` | 成本参考（非架构定稿） |

## 快速验证

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest tests/ -q
python -m video_pipeline.main --payload tests/fixtures/gateway_payload.json --mock --skip-approval
```

## 工程原则

- Multi-Agent：**Intake 一分五路**（见 `docs/ARCHITECTURE.md`）
- `script.json` 为 Script 阶段后的叙事单一事实来源
- Artifact-first：每阶段读写明确 JSON 产物
- Mock 先行，真实 API 在门禁通过后再接
