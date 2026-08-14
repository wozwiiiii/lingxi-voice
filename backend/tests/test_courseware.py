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


async def _create_preset(client, db_session, title="Preset Demo"):
    from app.models.courseware import CoursewareProject

    project = CoursewareProject(title=title, status="completed")
    db_session.add(project)
    await db_session.commit()
    return project


@pytest.mark.asyncio
async def test_preset_courseware_cannot_be_deleted(client: AsyncClient, auth_headers, db_session):
    """Preset (user_id IS NULL) must not be deletable by any logged-in user (#6)."""
    project = await _create_preset(client, db_session)
    resp = await client.delete(f"/api/courseware/{project.id}", headers=auth_headers)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_preset_courseware_cannot_be_patched(client: AsyncClient, auth_headers, db_session):
    """Preset slides/settings must not be writable by any logged-in user (#6)."""
    project = await _create_preset(client, db_session)
    resp = await client.patch(
        f"/api/courseware/{project.id}/settings",
        json={"voice_id": "00000000-0000-0000-0000-000000000000"},
        headers=auth_headers,
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_preset_courseware_cannot_be_synthesized(client: AsyncClient, auth_headers, db_session):
    """Preset courseware must not be synthesizable by any logged-in user (#6)."""
    project = await _create_preset(client, db_session)
    resp = await client.post(f"/api/courseware/{project.id}/synthesize", headers=auth_headers)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_preset_courseware_still_readable_without_auth(client: AsyncClient, db_session):
    """Preset read access (GET) must remain open to everyone including visitors (#6)."""
    project = await _create_preset(client, db_session)
    resp = await client.get(f"/api/courseware/{project.id}")
    assert resp.status_code == 200
    assert resp.json()["title"] == "Preset Demo"
