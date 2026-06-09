# Kling Provider Notes (V2)

## Role in V2

V2 uses **Kling first-last-frame only** via fal.ai. Every shot supplies a start frame and end frame; the adapter calls `FAL_VIDEO_MODEL_KLING_FL` (default: `fal-ai/kling-video/o1/standard/image-to-video`).

## Best for

- Cinematic motion between two composed stills
- Consistent character/scene continuity when frames come from asset packs + storyboard preview
- ~5s shots after user storyboard approval

## Adapter input

```json
{
  "job_id": "job_20260528_173000",
  "shot_id": "shot_002",
  "duration_sec": 5,
  "prompt": "realistic cinematic city establishing shot",
  "start_image_url": "https://.../shot_002_start.png",
  "end_image_url": "https://.../shot_002_end.png",
  "aspect_ratio": "16:9",
  "output_path": "storage/jobs/.../clips/raw/shot_002_kling_attempt_1.mp4"
}
```

## Prompt guidance

- Prompt describes motion between start and end — not a full reshoot of either frame
- Keep camera motion physically plausible
- Avoid stacking unrelated actions in one 5s beat

## Polling rules

- Poll until success, failure, or timeout
- Save provider request ID immediately after creation
- Resume polling if request ID exists after process restart

## Out of scope (V2)

- Text-to-video or single-image i2v as primary path
- Seedance / Wan routing (removed from `routing_agent.py`)

See `docs/ARCHITECTURE.md` and `rules/ROUTING.md`.
