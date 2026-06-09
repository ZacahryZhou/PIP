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
    max_video_duration_sec: int = 60
    max_concurrent_shots: int = 4
    max_job_cost_usd: float = 10.0
    max_generation_retries: int = 2
    max_storyboard_revisions: int = 2
    video_pipeline_mock: bool = False

    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_model: str = "deepseek-chat"
    anthropic_api_key: str = ""

    pip_default_language: str = "en"
    pip_tts_provider: str = "fal"

    fal_key: str = ""
    fal_image_model: str = "fal-ai/nano-banana-pro"
    fal_video_model_kling_fl: str = "fal-ai/kling-video/o1/standard/image-to-video"
    fal_video_generate_audio: bool = False
    fal_tts_model: str = "fal-ai/elevenlabs/tts/eleven-v3"
    fal_tts_voice: str = "21m00Tcm4TlvDq8ikWAM"
    fal_tts_language: str = "en"
    pip_bgm_mode: str = "off"
    pip_music_dir: str = "assets/music"

    elevenlabs_api_key: str = ""
    elevenlabs_voice_id: str = "21m00Tcm4TlvDq8ikWAM"
    elevenlabs_model_id: str = "eleven_multilingual_v2"

    telegram_bot_token: str = ""

settings = Settings()
