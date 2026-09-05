import uuid

from fastapi import HTTPException, status
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse
from app.security.jwt import create_access_token, create_refresh_token, decode_token
from app.utils.redis_client import get_security_redis

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# 账号锁定参数（防暴力破解）
_LOGIN_FAILURE_LIMIT = 5      # 连续失败 5 次触发锁定
_LOGIN_LOCKOUT_SECONDS = 900  # 锁定 15 分钟


def _fail_key(email: str) -> str:
    """登录失败计数 key（db1）。"""
    return f"auth:login_fail:{email.strip().lower()}"


def _lock_key(email: str) -> str:
    """账号锁定标记 key（db1）。"""
    return f"auth:lockout:{email.strip().lower()}"


async def _is_locked(email: str) -> bool:
    redis = await get_security_redis()
    return bool(await redis.exists(_lock_key(email)))


async def _record_login_failure(email: str) -> None:
    """累计一次登录失败，达到阈值则设置锁定标记。

    失败计数与锁定标记分离：失败计数 key 只做累计（带观察窗口 TTL），
    达到阈值时另设一个锁定 key（带 15 分钟 TTL）。这样「有过 1 次失败」
    不会误判为「已锁定」。
    """
    redis = await get_security_redis()
    fail_key = _fail_key(email)
    failures = await redis.incr(fail_key)
    # 失败计数观察窗口：窗口内未达到阈值，过期后重新从 0 计（防永久累积）
    if failures == 1:
        await redis.expire(fail_key, _LOGIN_LOCKOUT_SECONDS)
    if failures >= _LOGIN_FAILURE_LIMIT:
        # 达到阈值：设置锁定标记（15 分钟），并清失败计数
        await redis.setex(_lock_key(email), _LOGIN_LOCKOUT_SECONDS, "1")
        await redis.delete(fail_key)


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
    # 账号锁定：锁定期间即使密码正确也拒绝，防止暴力破解。
    # 用邮箱归一化做 key，未命中用户也纳入失败计数（避免「探测邮箱是否存在」）。
    if await _is_locked(data.email):
        raise HTTPException(
            status_code=status.HTTP_423_LOCKED,
            detail="登录失败次数过多，账号已锁定，请 15 分钟后再试",
        )

    result = await db.execute(select(User).where(User.email == data.email))
    user = result.scalar_one_or_none()
    if not user or not pwd_context.verify(data.password, user.password_hash):
        await _record_login_failure(data.email)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials"
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Account disabled"
        )

    # 登录成功：清除失败计数与锁定标记，让用户从锁定风险中复位
    redis = await get_security_redis()
    await redis.delete(_lock_key(data.email))
    await redis.delete(_fail_key(data.email))

    access_token, _, _ = create_access_token(str(user.id))
    refresh_token, _, _ = create_refresh_token(str(user.id))

    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


async def refresh_access_token(db: AsyncSession, refresh_token_str: str) -> TokenResponse:
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

    # Reject revoked refresh tokens (logout or prior rotation) (#8)
    jti = payload.get("jti", "")
    if jti:
        redis = await get_security_redis()
        if await redis.get(f"jwt:blacklist:{jti}"):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token revoked"
            )

    # Re-check user state: banned/deleted users must not be able to refresh (#7)
    try:
        result = await db.execute(
            select(User).where(User.id == uuid.UUID(payload["sub"]))
        )
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token"
        )
    user = result.scalar_one_or_none()
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Account disabled"
        )

    # Rotate refresh token: blacklist old one, issue new pair
    if jti:
        redis = await get_security_redis()
        remaining_ttl = max(0, int(payload.get("exp", 0) - __import__("time").time()))
        await redis.setex(f"jwt:blacklist:{jti}", remaining_ttl, "1")

    access_token, _, _ = create_access_token(str(user.id))
    new_refresh_token, _, _ = create_refresh_token(str(user.id))
    return TokenResponse(access_token=access_token, refresh_token=new_refresh_token)


async def logout_user(access_jti: str) -> None:
    """Blacklist an access token's jti until its natural expiry."""
    from app.config import settings

    redis = await get_security_redis()
    ttl = settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    await redis.setex(f"jwt:blacklist:{access_jti}", ttl, "1")


async def logout_refresh_token(refresh_token_str: str) -> None:
    """Blacklist a refresh token's jti so it can no longer be used to refresh.

    Without this, a leaked refresh token stays valid for up to 7 days after logout.
    """
    try:
        payload = decode_token(refresh_token_str)
    except Exception:
        return  # Invalid/expired token — nothing to blacklist; logout still effective
    if payload.get("type") != "refresh":
        return
    jti = payload.get("jti", "")
    if not jti:
        return
    import time

    remaining_ttl = max(0, int(payload.get("exp", 0) - time.time()))
    if remaining_ttl <= 0:
        return
    redis = await get_security_redis()
    await redis.setex(f"jwt:blacklist:{jti}", remaining_ttl, "1")
