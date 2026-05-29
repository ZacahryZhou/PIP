# Kling Provider Notes / Kling 模型说明

## Best For / 适合场景

- Realistic cinematic scenes.
- 写实电影感场景。
- Fallback generation for most shot types.
- 大多数镜头类型的备用生成。
- Stable environment and camera motion.
- 稳定环境和运镜。

## MVP Adapter Requirements / MVP 适配器要求

- Accept text prompt, duration, aspect ratio, and motion strength.
- 接收文本提示词、时长、画幅比例和运动强度。
- Poll provider status until complete or failed.
- 轮询模型状态直到完成或失败。
- Save failed response body in generation report.
- 将失败响应保存到生成报告。

## Adapter Input / 适配器输入

```json
{
  "job_id": "job_20260528_173000",
  "shot_id": "shot_002",
  "duration_sec": 5,
  "prompt": "realistic cinematic city establishing shot",
  "negative_prompt": "flicker, warped geometry, unreadable text",
  "motion_intensity": "medium",
  "aspect_ratio": "16:9",
  "target_resolution": "1920x1080",
  "output_path": "storage/jobs/.../clips/raw/shot_002_kling_attempt_1.mp4"
}
```

## Prompt Guidance / Prompt 指南

- Best results should come from realistic, physical camera language.
- 写实、物理可信的镜头语言最适合 Kling。
- Avoid overloading the prompt with too many simultaneous actions.
- 避免在一个 prompt 中塞入过多同时发生的动作。
- For fallback character shots, preserve the character prompt but simplify motion.
- 作为人物镜头备用模型时，保留角色描述，但简化动作。
- For environment shots, emphasize lighting, depth, lens, and camera movement.
- 环境镜头应强调光线、空间层次、镜头和运镜。

## Polling Rules / 轮询规则

- Poll until the provider returns success, failure, or timeout.
- 轮询直到供应商返回成功、失败或超时。
- Use exponential backoff with an upper sleep limit.
- 使用指数退避，并设置最大等待间隔。
- Save provider request ID immediately after creation.
- 创建请求后立即保存 provider request ID。
- A process restart should be able to resume polling if the request ID exists.
- 如果 request ID 已存在，进程重启后应能恢复轮询。

## Fallback Role / 备用角色

Kling is the default fallback for:

Kling 默认作为以下场景的备用模型：

- Seedance character or high-motion failures.
- Seedance 人物或强动作失败。
- Wan T2V simple scene failures.
- Wan T2V 简单场景失败。
- Premium API creative scene failures.
- 高端 API 创意场景失败。

