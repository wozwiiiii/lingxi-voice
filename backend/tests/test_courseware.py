import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_upload_rejects_non_pptx(client: AsyncClient, auth_headers):
    resp = await client.post(
        "/api/courseware/upload",
        files={"file": ("test.txt", b"not a pptx", "text/plain")},
        headers=auth_headers,
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_upload_rejects_bad_magic(client: AsyncClient, auth_headers):
    resp = await client.post(
        "/api/courseware/upload",
        files={"file": ("fake.pptx", b"not a zip file",
               "application/vnd.openxmlformats-officedocument.presentationml.presentation")},
        headers=auth_headers,
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_list_presets(client: AsyncClient, auth_headers):
    resp = await client.get("/api/courseware?type=preset", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "projects" in data


@pytest.mark.asyncio
async def test_list_my_empty(client: AsyncClient, auth_headers):
    resp = await client.get("/api/courseware?type=my", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 0


@pytest.mark.asyncio
async def test_access_without_auth(client: AsyncClient):
    resp = await client.post("/api/courseware/upload")
    assert resp.status_code == 401
