from fastapi import APIRouter, Depends, Request
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.auth import (
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    TokenResponse,
    UserResponse,
)
from app.security.dependencies import get_current_user
from app.security.jwt import decode_token
from app.services.auth_service import (
    login_user,
    logout_refresh_token,
    logout_user,
    refresh_access_token,
    register_user,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])


class LogoutRequest(BaseModel):
    """Optional body carrying the refresh token to revoke on logout."""
    refresh_token: str | None = None


@router.post("/register", response_model=UserResponse, status_code=201)
async def register(data: RegisterRequest, db: AsyncSession = Depends(get_db)):
    user = await register_user(db, data)
    return user


@router.post("/login", response_model=TokenResponse)
async def login(data: LoginRequest, db: AsyncSession = Depends(get_db)):
    return await login_user(db, data)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(data: RefreshRequest, db: AsyncSession = Depends(get_db)):
    return await refresh_access_token(db, data.refresh_token)


@router.post("/logout", status_code=204)
async def logout(
    request: Request,
    body: LogoutRequest | None = None,
    user=Depends(get_current_user),
):
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        token = auth[7:]
        try:
            payload = decode_token(token)
            jti = payload.get("jti", "")
            if jti:
                await logout_user(jti)
        except Exception:
            pass  # Token already invalid; logout still effective

    # 同时拉黑 refresh token：否则登出后泄露的 refresh token 仍可换取新 token（#8）
    if body and body.refresh_token:
        await logout_refresh_token(body.refresh_token)

    return Response(status_code=204)


@router.get("/me", response_model=UserResponse)
async def get_me(user=Depends(get_current_user)):
    return user
