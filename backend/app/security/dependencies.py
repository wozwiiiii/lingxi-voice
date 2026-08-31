import uuid

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.security.jwt import create_visitor_token, decode_token
from app.utils.redis_client import get_security_redis


async def get_current_user(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> User:
    """Extract JWT from Authorization header and return user. Raises 401 on failure."""
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing token"
        )

    token = auth_header[7:]
    # P2-10：限流中间件已解码过则复用，避免每请求双重验签。
    # 中间件解码失败时不写 state，这里照常自行解码并 401。
    payload = getattr(request.state, "jwt_payload", None)
    if payload is None:
        try:
            payload = decode_token(token)
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token"
            )

    if payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Wrong token type"
        )

    # Check blacklist（安全状态存于独立 Redis 库，不受缓存淘汰影响）
    redis = await get_security_redis()
    blacklisted = await redis.get(f"jwt:blacklist:{payload['jti']}")
    if blacklisted:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Token revoked"
        )

    result = await db.execute(
        select(User).where(User.id == uuid.UUID(payload["sub"]))
    )
    user = result.scalar_one_or_none()
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found"
        )

    return user


async def get_visitor_or_user(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> tuple[User | None, str | None]:
    """Returns (user_or_none, visitor_token_or_none).
    Logged-in users get their User object. Guests get a visitor_token.
    """
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        try:
            user = await get_current_user(request, db)
            return user, None
        except HTTPException:
            pass

    visitor_token = request.cookies.get("visitor_token")
    redis = await get_security_redis()
    if visitor_token and await redis.exists(f"guest:{visitor_token}"):
        await redis.expire(f"guest:{visitor_token}", 86400)
        return None, visitor_token

    new_token = create_visitor_token()
    await redis.setex(f"guest:{new_token}", 86400, "1")
    return None, new_token
