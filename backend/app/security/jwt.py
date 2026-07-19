import uuid
from datetime import datetime, timedelta, timezone

import jwt

from app.config import settings


def create_access_token(user_id: str) -> tuple[str, str, datetime]:
    """Returns (token, jti, expires_at)."""
    jti = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {
        "sub": user_id,
        "jti": jti,
        "type": "access",
        "iat": now,
        "exp": expires_at,
    }
    token = jwt.encode(
        payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM
    )
    return token, jti, expires_at


def create_refresh_token(user_id: str) -> tuple[str, str, datetime]:
    jti = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    payload = {
        "sub": user_id,
        "jti": jti,
        "type": "refresh",
        "iat": now,
        "exp": expires_at,
    }
    token = jwt.encode(
        payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM
    )
    return token, jti, expires_at


def decode_token(token: str) -> dict:
    return jwt.decode(
        token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM]
    )


def create_visitor_token() -> str:
    return f"visitor_{uuid.uuid4().hex}"
