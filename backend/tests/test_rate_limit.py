"""TDD tests for RateLimiter with sliding window via Redis sorted sets."""

import fakeredis.aioredis
import pytest

from app.security.rate_limit import RateLimiter
from app.utils import redis_client as redis_module


@pytest.fixture(autouse=True)
def _mock_redis():
    fake = fakeredis.aioredis.FakeRedis(decode_responses=True)
    original = redis_module.redis_client
    redis_module.redis_client = fake
    yield
    redis_module.redis_client = original


@pytest.fixture
def limiter():
    return RateLimiter(window_seconds=3600, max_requests=2)


class TestRateLimiterBasic:
    @pytest.mark.asyncio
    async def test_allows_first_request(self, limiter):
        await limiter.check("test:basic")

    @pytest.mark.asyncio
    async def test_allows_up_to_limit(self, limiter):
        """Should allow exactly max_requests calls (2)."""
        await limiter.check("test:exact_1")
        await limiter.check("test:exact_2")

    @pytest.mark.asyncio
    async def test_blocks_over_limit(self, limiter):
        """3rd call on same key should raise HTTP 429."""
        from fastapi import HTTPException

        await limiter.check("test:block")
        await limiter.check("test:block")
        with pytest.raises(HTTPException) as exc:
            await limiter.check("test:block")
        assert exc.value.status_code == 429

    @pytest.mark.asyncio
    async def test_different_keys_isolated(self, limiter):
        """Key A at limit should not affect Key B."""
        from fastapi import HTTPException

        await limiter.check("test:iso_a")
        await limiter.check("test:iso_a")
        with pytest.raises(HTTPException):
            await limiter.check("test:iso_a")
        await limiter.check("test:iso_b")


class TestRateLimiterOverride:
    @pytest.mark.asyncio
    async def test_max_override(self, limiter):
        """max_override overrides default max."""
        from fastapi import HTTPException

        await limiter.check("test:override", max_override=1)
        with pytest.raises(HTTPException):
            await limiter.check("test:override", max_override=1)
