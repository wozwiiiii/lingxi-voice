"""Sliding-window rate limiter using Redis sorted sets."""

import time

from fastapi import HTTPException, status

from app.utils.redis_client import get_redis


class RateLimiter:
    def __init__(self, window_seconds: int = 60, max_requests: int = 30):
        self.window = window_seconds
        self.max = max_requests

    async def check(self, key: str, max_override: int | None = None) -> None:
        limit = max_override or self.max
        redis = await get_redis()
        now = time.time()
        window_start = now - self.window

        await redis.zremrangebyscore(key, 0, window_start)
        count = await redis.zcard(key)

        if count >= limit:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="请求过于频繁，请稍后重试",
                headers={"Retry-After": str(self.window)},
            )

        await redis.zadd(key, {str(now): now})
        await redis.expire(key, self.window + 10)


rate_limiter = RateLimiter()
