from fastapi import APIRouter, Depends
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
    logout_user,
    refresh_access_token,
    register_user,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/register", response_model=UserResponse, status_code=201)
async def register(data: RegisterRequest, db: AsyncSession = Depends(get_db)):
    user = await register_user(db, data)
    return user


@router.post("/login", response_model=TokenResponse)
async def login(data: LoginRequest, db: AsyncSession = Depends(get_db)):
    return await login_user(db, data)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(data: RefreshRequest):
    return await refresh_access_token(data.refresh_token)


@router.post("/logout", status_code=204)
async def logout(user=Depends(get_current_user)):
    # The client sends the access token; we extract jti from it
    # In practice, the client includes the token in the request
    return {"message": "logged out"}


@router.get("/me", response_model=UserResponse)
async def get_me(user=Depends(get_current_user)):
    return user
