from fastapi import HTTPException, status
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse
from app.security.jwt import create_access_token, create_refresh_token, decode_token
from app.utils.redis_client import get_redis

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def _hash_password(password: str) -> str:
    """Hash with bcrypt. Truncates to 72 bytes if needed (bcrypt limit)."""
    pw_bytes = password.encode("utf-8")
    if len(pw_bytes) > 72:
        pw_bytes = pw_bytes[:72]
    return pwd_context.hash(pw_bytes.decode("utf-8", errors="replace"))


async def register_user(db: AsyncSession, data: RegisterRequest) -> User:
    existing = await db.execute(
        select(User).where(
            (User.email == data.email) | (User.username == data.username)
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Registration failed. If you already have an account, please log in.",
        )
    user = User(
        email=data.email,
        username=data.username,
        password_hash=_hash_password(data.password),
    )
    db.add(user)
    await db.flush()
    await db.refresh(user)
    return user


async def login_user(db: AsyncSession, data: LoginRequest) -> TokenResponse:
    result = await db.execute(select(User).where(User.email == data.email))
    user = result.scalar_one_or_none()
    if not user or not pwd_context.verify(data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials"
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Account disabled"
        )

    access_token, _, _ = create_access_token(str(user.id))
    refresh_token, _, _ = create_refresh_token(str(user.id))

    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


async def refresh_access_token(refresh_token_str: str) -> TokenResponse:
    try:
        payload = decode_token(refresh_token_str)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token"
        )
    if payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Wrong token type"
        )

    # Rotate refresh token: blacklist old one, issue new pair
    old_jti = payload.get("jti", "")
    if old_jti:
        redis = await get_redis()
        remaining_ttl = max(0, int(payload.get("exp", 0) - __import__("time").time()))
        await redis.setex(f"jwt:blacklist:{old_jti}", remaining_ttl, "1")

    access_token, _, _ = create_access_token(payload["sub"])
    new_refresh_token, _, _ = create_refresh_token(payload["sub"])
    return TokenResponse(access_token=access_token, refresh_token=new_refresh_token)


async def logout_user(access_jti: str) -> None:
    from app.config import settings

    redis = await get_redis()
    ttl = settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    await redis.setex(f"jwt:blacklist:{access_jti}", ttl, "1")
