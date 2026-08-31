from functools import cached_property

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://lingxi:lingxi@postgres:5432/lingxi"

    # Redis
    REDIS_URL: str = "redis://redis:6379/0"
    # 安全状态（JWT 黑名单、访客会话、SSE ticket）使用的逻辑库，
    # 与缓存类 key 隔离，避免缓存淘汰策略影响安全状态
    REDIS_SECURITY_DB: int = 1

    # JWT
    JWT_SECRET_KEY: str = "lingxi-dev-secret-do-not-use-in-production"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # TTS Providers (comma-separated string in env, accessed as list via property)
    TTS_PROVIDER_CHAIN: str = "cloud:siliconflow"

    @cached_property
    def tts_provider_chain_list(self) -> list[str]:
        return [p.strip() for p in self.TTS_PROVIDER_CHAIN.split(",") if p.strip()]

    # Provider URLs
    INFERENCE_SERVICE_URL: str = "http://inference:8001"
    SILICONFLOW_API_KEY: str = ""
    SILICONFLOW_BASE_URL: str = "https://api.siliconflow.cn/v1"

    # LLM
    DEEPSEEK_API_KEY: str = ""
    DEEPSEEK_BASE_URL: str = "https://api.deepseek.com"

    # CORS (comma-separated string in env, accessed as list via property)
    CORS_ORIGINS: str = "http://localhost:5173"

    @cached_property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    # Storage
    MEDIA_ROOT: str = "/app/media"
    MAX_UPLOAD_SIZE_MB: int = 20


settings = Settings()
