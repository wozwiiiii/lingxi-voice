"""Redis 客户端：缓存库与安全状态库分离。

- `redis_client`（db 0）：TTS 结果缓存、合成锁、课件进度、限流窗口等可淘汰数据。
- `security_redis_client`（REDIS_SECURITY_DB，默认 db 1）：JWT 黑名单、访客会话、
  SSE 一次性 ticket 等安全状态。分库后缓存侧的淘汰策略（allkeys-lru 等）
  不会逐出安全状态，避免"已登出 token 复活"类问题。
"""

import redis.asyncio as aioredis

from app.config import settings


def _security_url() -> str:
    """将 REDIS_URL 的逻辑库替换为 REDIS_SECURITY_DB。"""
    url = settings.REDIS_URL
    # 形如 redis://host:6379/0 或 redis://:pass@host:6379/0
    base, sep, _db = url.rpartition("/")
    if sep and base.startswith(("redis://", "rediss://")) and _db.isdigit():
        return f"{base}/{settings.REDIS_SECURITY_DB}"
    # URL 未带 db 段，直接追加
    return f"{url}/{settings.REDIS_SECURITY_DB}"


redis_client: aioredis.Redis = aioredis.from_url(
    settings.REDIS_URL,
    encoding="utf-8",
    decode_responses=True,
)

security_redis_client: aioredis.Redis = aioredis.from_url(
    _security_url(),
    encoding="utf-8",
    decode_responses=True,
)


async def get_redis() -> aioredis.Redis:
    return redis_client


async def get_security_redis() -> aioredis.Redis:
    return security_redis_client
