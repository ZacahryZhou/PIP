"""Runtime configuration loaded from environment variables."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: str = "local"
    job_storage_dir: str = "storage/jobs"
    target_resolution: str = "1920x1080"
    target_fps: int = 30
    fal_video_resolution: str = "1080p"
    max_shot_duration_sec: int = 8
    min_video_duration_sec: int = 15
    max_video_duration_sec: int = 45
    max_concurrent_shots: int = 4
    max_job_cost_usd: float = 5.0
    max_generation_retries: int = 2
    video_pipeline_mock: bool = False

    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_model: str = "deepseek-chat"
    anthropic_api_key: str = ""

    pip_default_language: str = "en"

    fal_key: str = ""
    fal_image_model: str = "fal-ai/nano-banana-pro"
    fal_video_model_seedance: str = "fal-ai/bytedance/seedance/v1.5/pro/text-to-video"
    fal_video_model_seedance_i2v: str = "fal-ai/bytedance/seedance/v1.5/pro/image-to-video"
    fal_video_model_kling: str = "fal-ai/kling-video/v3/pro/text-to-video"
    fal_video_model_kling_i2v: str = "fal-ai/kling-video/v3/pro/image-to-video"
    fal_video_model_wan: str = ""
    fal_video_generate_audio: bool = False
    fal_tts_model: str = "xai/tts/v1"
    fal_tts_voice: str = "rex"
    fal_tts_language: str = "en"
    pip_bgm_mode: str = "fal"
    fal_bgm_model: str = "fal-ai/minimax-music/v2.6"
    pip_music_dir: str = "assets/music"

    telegram_bot_token: str = ""

settings = Settings()
