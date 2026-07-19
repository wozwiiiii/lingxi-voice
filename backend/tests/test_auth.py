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
async def test_access_without_token(client: AsyncClient):
    resp = await client.get("/api/auth/me")
    assert resp.status_code == 401
