import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_register_success(client: AsyncClient):
    resp = await client.post("/api/auth/register", json={
        "email": "test@example.com",
        "username": "testuser",
        "password": "password123",
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["email"] == "test@example.com"
    assert "id" in data


@pytest.mark.asyncio
async def test_register_duplicate_email(client: AsyncClient):
    await client.post("/api/auth/register", json={
        "email": "dup@example.com", "username": "user1", "password": "password123",
    })
    resp = await client.post("/api/auth/register", json={
        "email": "dup@example.com", "username": "user2", "password": "password123",
    })
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_login_and_access_protected_route(client: AsyncClient):
    await client.post("/api/auth/register", json={
        "email": "login@test.com", "username": "logintest", "password": "password123",
    })
    resp = await client.post("/api/auth/login", json={
        "email": "login@test.com", "password": "password123",
    })
    assert resp.status_code == 200
    tokens = resp.json()
    assert "access_token" in tokens
    assert "refresh_token" in tokens

    me_resp = await client.get("/api/auth/me", headers={
        "Authorization": f"Bearer {tokens['access_token']}"
    })
    assert me_resp.status_code == 200
    assert me_resp.json()["email"] == "login@test.com"


@pytest.mark.asyncio
async def test_login_wrong_password(client: AsyncClient):
    await client.post("/api/auth/register", json={
        "email": "wrong@test.com", "username": "wrong", "password": "password123",
    })
    resp = await client.post("/api/auth/login", json={
        "email": "wrong@test.com", "password": "wrongpassword",
    })
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_register_short_password(client: AsyncClient):
    resp = await client.post("/api/auth/register", json={
        "email": "short@test.com", "username": "shortpw", "password": "123",
    })
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_login_locks_account_after_repeated_failures(client: AsyncClient):
    """连续 5 次密码错误后账号锁定，即使密码正确也返回 423（P1）。"""
    await client.post("/api/auth/register", json={
        "email": "lock@test.com", "username": "lockuser", "password": "password123",
    })
    # 连续输错 5 次
    for _ in range(5):
        resp = await client.post("/api/auth/login", json={
            "email": "lock@test.com", "password": "wrongpassword",
        })
        assert resp.status_code == 401

    # 第 6 次即使密码正确也被锁定
    resp = await client.post("/api/auth/login", json={
        "email": "lock@test.com", "password": "password123",
    })
    assert resp.status_code == 423
    assert "锁定" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_login_success_resets_failure_count(client: AsyncClient):
    """失败几次后成功登录，失败计数清零，不会累积到锁定阈值。"""
    await client.post("/api/auth/register", json={
        "email": "reset@test.com", "username": "resetuser", "password": "password123",
    })
    for _ in range(4):
        resp = await client.post("/api/auth/login", json={
            "email": "reset@test.com", "password": "wrong",
        })
        assert resp.status_code == 401

    # 成功登录
    resp = await client.post("/api/auth/login", json={
        "email": "reset@test.com", "password": "password123",
    })
    assert resp.status_code == 200

    # 再次失败应从 1 重新计数，而不是继续累积到 5 触发锁定
    resp = await client.post("/api/auth/login", json={
        "email": "reset@test.com", "password": "wrong",
    })
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_access_without_token(client: AsyncClient):
    resp = await client.get("/api/auth/me")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_refresh_rejects_disabled_user(client: AsyncClient, db_session):
    """A disabled/deleted user must not be able to refresh tokens (#7)."""
    await client.post("/api/auth/register", json={
        "email": "disabled@test.com", "username": "disableduser", "password": "password123",
    })
    resp = await client.post("/api/auth/login", json={
        "email": "disabled@test.com", "password": "password123",
    })
    assert resp.status_code == 200
    refresh_token = resp.json()["refresh_token"]

    from sqlalchemy import select

    from app.models.user import User

    result = await db_session.execute(select(User).where(User.email == "disabled@test.com"))
    user = result.scalar_one()
    user.is_active = False
    await db_session.commit()

    resp = await client.post("/api/auth/refresh", json={"refresh_token": refresh_token})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_logout_blacklists_refresh_token(client: AsyncClient):
    """Logout must revoke the refresh token so it can't be reused (#8)."""
    await client.post("/api/auth/register", json={
        "email": "logout@test.com", "username": "logoutuser", "password": "password123",
    })
    resp = await client.post("/api/auth/login", json={
        "email": "logout@test.com", "password": "password123",
    })
    assert resp.status_code == 200
    tokens = resp.json()
    access = tokens["access_token"]
    refresh = tokens["refresh_token"]
    headers = {"Authorization": f"Bearer {access}"}

    # 登出：同时携带 refresh_token 供后端拉黑
    resp = await client.post("/api/auth/logout", headers=headers, json={"refresh_token": refresh})
    assert resp.status_code == 204

    # 登出后 access token 立即失效
    resp = await client.get("/api/auth/me", headers=headers)
    assert resp.status_code == 401

    # 登出后 refresh token 也不应能换取新 token
    resp = await client.post("/api/auth/refresh", json={"refresh_token": refresh})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_logout_without_refresh_body_still_works(client: AsyncClient):
    """Logout without a body must remain backward compatible (access-only revoke)."""
    await client.post("/api/auth/register", json={
        "email": "logout2@test.com", "username": "logoutuser2", "password": "password123",
    })
    resp = await client.post("/api/auth/login", json={
        "email": "logout2@test.com", "username": "logoutuser2", "password": "password123",
    })
    assert resp.status_code == 200
    tokens = resp.json()
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}

    resp = await client.post("/api/auth/logout", headers=headers)
    assert resp.status_code == 204
