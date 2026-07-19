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
    return RateLimiter(window_seconds=3600, max_requests=5)


class TestRateLimiterBasic:
    @pytest.mark.asyncio
    async def test_allows_first_request(self, limiter):
        await limiter.check("test:basic")

    @pytest.mark.asyncio
    async def test_allows_within_limit(self, limiter):
        """Should allow up to max_requests calls without error."""
        for i in range(5):
            await limiter.check(f"test:within_{i}")

    @pytest.mark.asyncio
    async def test_blocks_with_override(self, limiter):
        """max_override=1: second call with same key raises 429."""
        from fastapi import HTTPException

        await limiter.check("test:block")
        with pytest.raises(HTTPException) as exc:
            await limiter.check("test:block", max_override=1)
        assert exc.value.status_code == 429
        assert "Retry-After" in exc.value.headers

    @pytest.mark.asyncio
    async def test_different_keys_isolated(self, limiter):
        """Key A at limit should not affect Key B."""
        from fastapi import HTTPException

        await limiter.check("test:key_a_1")
        with pytest.raises(HTTPException):
            await limiter.check("test:key_a_1", max_override=1)
        # Different key should still work
        await limiter.check("test:key_b")


class TestRateLimiterOverride:
    @pytest.mark.asyncio
    async def test_override_enforces_stricter_limit(self, limiter):
        from fastapi import HTTPException

        # Override to 1: second call fails
        await limiter.check("test:ov_1")
        with pytest.raises(HTTPException):
            await limiter.check("test:ov_1", max_override=1)

    @pytest.mark.asyncio
    async def test_override_more_lenient(self, limiter):
        """Override to > default: allows more calls."""
        # With override=10, we can make 9 calls (default max=5 would block)
        for i in range(9):
            await limiter.check("test:lenient", max_override=10)
