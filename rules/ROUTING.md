# Routing Rules (V2)

V2 routes **every shot** to **Kling first-last-frame** generation via fal.ai. There is no Seedance, Wan, or text-to-video fallback in the active pipeline.

## Decision

| Condition | Model | Mode |
|-----------|-------|------|
| All shots | `kling` | `first_last_frame` |

## Budget gate

- Sum `estimated_cost_per_shot` across routes.
- If total exceeds `max_job_cost_usd`, set `should_continue=false` and stop before generation.

## Cost estimates (MVP)

| Model | Rate |
|-------|------|
| `kling` | $0.08 / billed second (ceil duration) |
| Keyframes | Included per shot via `estimated_keyframe_cost` |

## Output shape

```json
{
  "routes": [
    {
      "shot_id": "shot_001",
      "preferred_model": "kling",
      "fallback_model": "kling",
      "generation_mode": "first_last_frame",
      "generation_mode_reason": "V2 pipeline requires first-last-frame",
      "routing_reason": "V2: Kling first-last-frame only"
    }
  ],
  "should_continue": true
}
```

## Product rules

See `docs/ARCHITECTURE.md` for the current Multi-Agent architecture (refactoring in progress).
