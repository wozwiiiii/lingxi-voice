import pytest
from httpx import AsyncClient
from unittest.mock import MagicMock


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


async def _create_owned_project(db_session, title="Owned Project"):
    """Create a project owned by the auth fixture's user (cw_test@example.com)."""
    from sqlalchemy import select
    from app.models.courseware import CoursewareProject
    from app.models.user import User

    result = await db_session.execute(select(User).where(User.email == "cw_test@example.com"))
    user = result.scalar_one()
    project = CoursewareProject(user_id=user.id, title=title, status="ready")
    db_session.add(project)
    await db_session.commit()
    return project


@pytest.mark.asyncio
async def test_patch_slide_clears_emotion_to_null(client: AsyncClient, auth_headers, db_session):
    """An explicit null in the PATCH body must clear the field, not be stripped (#16)."""
    from sqlalchemy import select
    from app.models.courseware import CoursewareSlide

    project = await _create_owned_project(db_session, "Null Clear Test")
    slide = CoursewareSlide(project_id=project.id, slide_index=0, emotion="happy", style="gentle")
    db_session.add(slide)
    await db_session.commit()

    resp = await client.patch(
        f"/api/courseware/{project.id}/slides/0",
        json={"emotion": None},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["emotion"] is None
    assert data["style"] == "gentle"  # untouched field preserved

    fresh = await db_session.execute(
        select(CoursewareSlide).where(CoursewareSlide.id == slide.id)
    )
    assert fresh.scalar_one().emotion is None


@pytest.mark.asyncio
async def test_synthesize_submits_to_celery(client: AsyncClient, auth_headers, db_session, monkeypatch):
    """Synthesize must submit to Celery and return immediately with status synthesizing (#15)."""
    from sqlalchemy import select
    from app.models.courseware import CoursewareProject
    import app.tasks.courseware_tasks as cw_tasks

    project = await _create_owned_project(db_session, "Async Submit Test")
    project_id = str(project.id)

    delay_mock = MagicMock()
    task_mock = MagicMock()
    task_mock.delay = delay_mock
    monkeypatch.setattr(cw_tasks, "synthesize_courseware_task", task_mock)

    resp = await client.post(f"/api/courseware/{project_id}/synthesize", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "synthesizing"
    assert "进度" in data["message"]

    delay_mock.assert_called_once_with(project_id)

    fresh = await db_session.execute(
        select(CoursewareProject).where(CoursewareProject.id == project.id)
    )
    assert fresh.scalar_one().status == "synthesizing"


@pytest.mark.asyncio
async def test_synthesize_submit_failure_resets_status(client: AsyncClient, auth_headers, db_session, monkeypatch):
    """If Celery submission fails (e.g. broker down), reset status and return 500 (#15)."""
    from sqlalchemy import select
    from app.models.courseware import CoursewareProject
    import app.tasks.courseware_tasks as cw_tasks

    project = await _create_owned_project(db_session, "Broker Down Test")
    project_id = str(project.id)

    delay_mock = MagicMock(side_effect=Exception("broker unreachable"))
    task_mock = MagicMock()
    task_mock.delay = delay_mock
    monkeypatch.setattr(cw_tasks, "synthesize_courseware_task", task_mock)

    resp = await client.post(f"/api/courseware/{project_id}/synthesize", headers=auth_headers)
    assert resp.status_code == 500
    assert "提交失败" in resp.json()["detail"]

    fresh = await db_session.execute(
        select(CoursewareProject).where(CoursewareProject.id == project.id)
    )
    assert fresh.scalar_one().status == "ready"


@pytest.mark.asyncio
async def test_synthesize_rejects_resubmit(client: AsyncClient, auth_headers, db_session, monkeypatch):
    """P1-8：synthesizing 状态下再次提交必须 409，不得叠加第二个 Celery 任务。"""
    import app.tasks.courseware_tasks as cw_tasks

    project = await _create_owned_project(db_session, "Idempotency Test")

    task_mock = MagicMock()
    task_mock.delay = MagicMock()
    monkeypatch.setattr(cw_tasks, "synthesize_courseware_task", task_mock)

    first = await client.post(f"/api/courseware/{project.id}/synthesize", headers=auth_headers)
    assert first.status_code == 200

    second = await client.post(f"/api/courseware/{project.id}/synthesize", headers=auth_headers)
    assert second.status_code == 409
    # 状态机拦截之外，并发窗口靠 Redis NX 锁兜底——锁必须存在
    from app.utils.redis_client import get_redis
    redis = await get_redis()
    assert await redis.exists(f"courseware:lock:{project.id}")
    # 只提交了一个任务
    task_mock.delay.assert_called_once_with(str(project.id))


@pytest.mark.asyncio
async def test_synthesize_lock_blocks_concurrent_submit(client: AsyncClient, auth_headers, db_session, monkeypatch):
    """P1-8：状态仍读到 ready 的并发请求，靠 Redis NX 锁拒绝第二个提交。"""
    import app.tasks.courseware_tasks as cw_tasks

    project = await _create_owned_project(db_session, "Lock Race Test")

    task_mock = MagicMock()
    task_mock.delay = MagicMock()
    monkeypatch.setattr(cw_tasks, "synthesize_courseware_task", task_mock)

    # 预置锁，模拟第一个请求已抢到锁、但状态提交尚未可见的窗口
    from app.utils.redis_client import get_redis
    redis = await get_redis()
    await redis.set(f"courseware:lock:{project.id}", "1", nx=True, ex=3600)

    resp = await client.post(f"/api/courseware/{project.id}/synthesize", headers=auth_headers)
    assert resp.status_code == 409
    assert "请勿重复提交" in resp.json()["detail"]
    task_mock.delay.assert_not_called()


@pytest.mark.asyncio
async def test_delete_purges_tts_cache_refs(client: AsyncClient, auth_headers, db_session):
    """P2-6：删除课件时必须清掉指向其音频的 tts:result 缓存与反向索引。"""
    from app.models.courseware import CoursewareSlide

    project = await _create_owned_project(db_session, "Cache Purge Test")
    audio_path = "audio/deadbeef.mp3"
    slide = CoursewareSlide(
        project_id=project.id, slide_index=0,
        audio_path=audio_path, status="completed",
    )
    db_session.add(slide)
    await db_session.commit()

    from app.utils.redis_client import get_redis
    redis = await get_redis()
    cache_hash = "abc123"
    await redis.setex(f"tts:result:{cache_hash}", 3600, audio_path)
    await redis.setex(f"tts:refs:{audio_path}", 3600, cache_hash)

    resp = await client.delete(f"/api/courseware/{project.id}", headers=auth_headers)
    assert resp.status_code == 204

    assert await redis.get(f"tts:result:{cache_hash}") is None
    assert await redis.get(f"tts:refs:{audio_path}") is None
