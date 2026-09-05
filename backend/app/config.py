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

    # ---- 超时（P0 止血：防止任务永久卡死）----
    # 云 TTS 客户端超时。原本 AsyncOpenAI 未传 timeout，用 SDK 默认 600s——
    # 上游 hang 住时，worker --concurrency=2 只需两个请求就全站停摆。
    PROVIDER_TIMEOUT_S: float = 60.0
    # LLM 预处理超时。单页文本 <500 token，p99 约 5-10s。
    LLM_TIMEOUT_S: float = 30.0
    LLM_MAX_ATTEMPTS: int = 3
    # 重试退避基数：sleep(base * 2**attempt)，原实现无退避
    LLM_RETRY_BACKOFF_BASE_S: float = 0.5
    # 单页合成硬超时 = LLM 90s 上限（3 次 × 30s）+ TTS 60s，留余量
    COURSEWARE_SLIDE_TIMEOUT_S: float = 120.0
    # 整个课件任务的软墙 deadline。刻意不用 Celery 的 time_limit：
    # hard kill 会绕过 finally 导致状态不收敛，且 acks_late=True 时
    # hard kill 不计入 max_retries，会造成无限重投反复烧云 API 费用。
    COURSEWARE_TASK_TOTAL_TIMEOUT_S: float = 1800.0
    COURSEWARE_SYNTHESIS_CONCURRENCY: int = 3

    # ---- 月度配额（防滥用，非计费）----
    # TTS 与课件分开计数：1 次 TTS ≈ 1 次云调用，1 页课件 ≈ LLM + TTS 两次。
    # 用户级覆盖走 User.quota_override = {"tts": N, "courseware": N}
    QUOTA_MONTHLY_TTS: int = 300
    QUOTA_MONTHLY_COURSEWARE_PAGES: int = 300

    # CORS (comma-separated string in env, accessed as list via property)
    CORS_ORIGINS: str = "http://localhost:5173"

    @cached_property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    # Storage
    MEDIA_ROOT: str = "/app/media"
    MAX_UPLOAD_SIZE_MB: int = 20


settings = Settings()
