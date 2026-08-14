"""TDD tests for RateLimiter with sliding window via Redis sorted sets."""

import fakeredis.aioredis
import pytest
from starlette.requests import Request

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


def _make_request(headers: dict | None = None, client=("10.0.0.2", 50000)) -> Request:
    headers = headers or {}
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/api/test",
        "headers": [(k.lower().encode(), v.encode()) for k, v in headers.items()],
        "client": client,
        "query_string": b"",
    }
    return Request(scope)


class TestClientIp:
    def test_uses_first_forwarded_entry(self):
        from app.main import _client_ip

        req = _make_request({"X-Forwarded-For": "203.0.113.7, 10.0.0.2"})
        assert _client_ip(req) == "203.0.113.7"

    def test_falls_back_to_client_host(self):
        from app.main import _client_ip

        req = _make_request({})
        assert _client_ip(req) == "10.0.0.2"

    def test_ignores_blank_forwarded_header(self):
        from app.main import _client_ip

        req = _make_request({"X-Forwarded-For": ""})
        assert _client_ip(req) == "10.0.0.2"


class TestRateLimitMiddlewareKey:
    @pytest.mark.asyncio
    async def test_rate_key_uses_forwarded_ip(self, client):
        """Behind nginx the middleware must key on the original client IP (#9)."""
        from app.security import rate_limit as rl_module

        captured = {}

        class _FakeLimiter:
            async def check(self, key, max_override=None):
                captured["key"] = key

        original = rl_module.rate_limiter
        rl_module.rate_limiter = _FakeLimiter()
        try:
            resp = await client.get(
                "/api/capabilities",
                headers={"X-Forwarded-For": "203.0.113.7, 10.0.0.2"},
            )
        finally:
            rl_module.rate_limiter = original

        assert resp.status_code == 200
        assert captured["key"] == "tts:rate:ip:203.0.113.7:1min"

    @pytest.mark.asyncio
    async def test_rate_key_falls_back_to_client_host(self, client):
        """No forwarded header (direct dev access) keys on request.client.host."""
        from app.security import rate_limit as rl_module

        captured = {}

        class _FakeLimiter:
            async def check(self, key, max_override=None):
                captured["key"] = key

        original = rl_module.rate_limiter
        rl_module.rate_limiter = _FakeLimiter()
        try:
            resp = await client.get("/api/capabilities")
        finally:
            rl_module.rate_limiter = original

        assert resp.status_code == 200
        # ASGITransport reports the client host as 127.0.0.1
        assert captured["key"] == "tts:rate:ip:127.0.0.1:1min"
