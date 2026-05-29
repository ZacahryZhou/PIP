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
    target_fps: int = 24
    max_shot_duration_sec: int = 8
    min_video_duration_sec: int = 15
    max_video_duration_sec: int = 45
    max_concurrent_shots: int = 4
    max_job_cost_usd: float = 5.0
    max_generation_retries: int = 2
    video_pipeline_mock: bool = True

    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_model: str = "deepseek-chat"
    anthropic_api_key: str = ""


settings = Settings()
