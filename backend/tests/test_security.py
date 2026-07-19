"""TDD tests for JWT token operations, visitor tokens, and auth dependencies."""

import time
import uuid
from unittest.mock import AsyncMock, patch

import fakeredis.aioredis
import jwt
import pytest
from fastapi import HTTPException
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.security.jwt import (
    create_access_token,
    create_refresh_token,
    create_visitor_token,
    decode_token,
)
from app.utils import redis_client as redis_module


@pytest.fixture(autouse=True)
def _mock_redis():
    fake = fakeredis.aioredis.FakeRedis(decode_responses=True)
    original = redis_module.redis_client
    redis_module.redis_client = fake
    yield
    redis_module.redis_client = original


class TestJWTAccessToken:
    def test_create_returns_token_and_jti(self):
        token, jti, expires_at = create_access_token("test-user-123")
        assert isinstance(token, str)
        assert len(token.split(".")) == 3  # header.payload.signature
        assert isinstance(jti, str)
        assert len(jti) > 0

    def test_token_decodes_correctly(self):
        token, jti, expires_at = create_access_token("user-456")
        payload = decode_token(token)
        assert payload["sub"] == "user-456"
        assert payload["jti"] == jti
        assert payload["type"] == "access"
        assert "exp" in payload
        assert "iat" in payload

    def test_access_token_has_30_min_expiry(self):
        token, jti, expires_at = create_access_token("user-789")
        from datetime import datetime, timedelta, timezone
        expected_min = datetime.now(timezone.utc) + timedelta(minutes=29)
        expected_max = datetime.now(timezone.utc) + timedelta(minutes=31)
        assert expected_min < expires_at < expected_max

    def test_invalid_token_raises(self):
        with pytest.raises(Exception):
            decode_token("not.a.valid.token")

    def test_wrong_secret_rejected(self):
        token, _, _ = create_access_token("user-1")
        with pytest.raises(Exception):
            jwt.decode(token, "wrong-secret-key", algorithms=["HS256"])


class TestJWTRefreshToken:
    def test_refresh_has_type_refresh(self):
        token, jti, expires_at = create_refresh_token("user-1")
        payload = decode_token(token)
        assert payload["type"] == "refresh"

    def test_refresh_has_7_day_expiry(self):
        token, jti, expires_at = create_refresh_token("user-1")
        from datetime import datetime, timedelta, timezone
        expected_min = datetime.now(timezone.utc) + timedelta(days=6)
        expected_max = datetime.now(timezone.utc) + timedelta(days=8)
        assert expected_min < expires_at < expected_max


class TestVisitorToken:
    def test_creates_prefixed_token(self):
        token = create_visitor_token()
        assert token.startswith("visitor_")
        assert len(token) > 30

    def test_two_tokens_are_unique(self):
        t1 = create_visitor_token()
        t2 = create_visitor_token()
        assert t1 != t2


class TestJWTBlacklist:
    @pytest.mark.asyncio
    async def test_blacklisted_token_detected(self):
        redis = redis_module.redis_client
        token, jti, _ = create_access_token("user-1")
        await redis.setex(f"jwt:blacklist:{jti}", 3600, "1")

        blacklisted = await redis.get(f"jwt:blacklist:{jti}")
        assert blacklisted is not None

    @pytest.mark.asyncio
    async def test_non_blacklisted_token_passes(self):
        redis = redis_module.redis_client
        token, jti, _ = create_access_token("user-2")
        blacklisted = await redis.get(f"jwt:blacklist:{jti}")
        assert blacklisted is None
