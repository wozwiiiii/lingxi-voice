"""P1 Beat 三合一任务测试：卡死收敛 + 音频清理 + 孤儿清理。

直接调用任务内部的异步函数（绕过 Celery 入口），用 task_db fixture
让任务内的 AsyncSessionLocal 落到测试库。
"""

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

import app.tasks.courseware_tasks as cw
from app.models.courseware import CoursewareProject
from app.models.task import SynthesisTask
from app.models.user import User
from app.models.voice import Voice


async def _make_user(db_session):
    result = await db_session.execute(
        select(User).where(User.email == "cw_test@example.com")
    )
    return result.scalar_one()


@pytest.mark.asyncio
async def test_converge_stuck_marks_failed_and_releases_lock(
    client, auth_headers, task_db, db_session, monkeypatch
):
    """卡死在 synthesizing 超 2 小时的项目 → failed + 释放锁。"""
    user = await _make_user(db_session)
    project = CoursewareProject(
        user_id=user.id, title="Stuck", status="synthesizing"
    )
    db_session.add(project)
    await db_session.commit()

    # 直接改 DB 把 updated_at 拨回 3 小时前（绕过 ORM onupdate，模拟
    # worker 崩溃后项目长期未更新）
    from sqlalchemy import update

    await db_session.execute(
        update(CoursewareProject)
        .where(CoursewareProject.id == project.id)
        .values(updated_at=datetime.now(timezone.utc) - timedelta(hours=3))
    )
    await db_session.commit()

    from app.utils import redis_client as redis_module

    redis = redis_module.redis_client
    lock_key = f"courseware:lock:{project.id}"
    await redis.set(lock_key, "1", ex=3600)

    await cw._converge_stuck()

    # 用独立查询重读（绕过 db_session 的 identity map，拿到 DB 最新值）
    async with cw.AsyncSessionLocal() as s:
        fresh = await s.get(CoursewareProject, project.id)
        status = fresh.status
        error_code = fresh.error_code
    assert status == "failed"
    assert error_code == "timeout"
    assert await redis.get(lock_key) is None


@pytest.mark.asyncio
async def test_converge_stuck_skips_recently_updated(
    client, auth_headers, task_db, db_session, monkeypatch
):
    """仍在正常推进（updated_at 很新）的项目不被误判为卡死。"""
    user = await _make_user(db_session)
    project = CoursewareProject(
        user_id=user.id, title="Active", status="synthesizing"
    )
    db_session.add(project)
    await db_session.commit()

    await cw._converge_stuck()

    async with cw.AsyncSessionLocal() as s:
        fresh = await s.get(CoursewareProject, project.id)
        status = fresh.status
    assert status == "synthesizing", "刚更新过的项目不应被收敛"


@pytest.mark.asyncio
async def test_cleanup_audio_deletes_orphan_only(
    client, auth_headers, task_db, db_session, monkeypatch, tmp_path
):
    """只删「无 DB 引用且超 30 天」的音频，被引用的保留。"""
    # 用临时目录替换 storage 的 root，避免污染真实 media 目录
    import app.tasks.courseware_tasks as cw_tasks
    from app.utils.storage import LocalStorage

    tmp_storage = LocalStorage(root=str(tmp_path))
    monkeypatch.setattr(cw_tasks, "storage", tmp_storage)

    # 造一个被引用的音频 + 一个孤儿音频
    user = await _make_user(db_session)
    voice = Voice(name="v", type="preset", provider="cloud:siliconflow", is_public=True)
    db_session.add(voice)
    await db_session.flush()

    referenced_path = await tmp_storage.save(b"audio1", "audio", "mp3")
    orphan_path = await tmp_storage.save(b"audio2", "audio", "mp3")

    task = SynthesisTask(
        user_id=user.id, voice_id=voice.id, type="tts",
        output_audio_path=referenced_path, status="completed",
    )
    db_session.add(task)
    await db_session.commit()

    # 孤儿音频 mtime 拨回 40 天前
    import os

    orphan_abs = tmp_path / orphan_path
    old = datetime.now().timestamp() - 40 * 86400
    os.utime(orphan_abs, (old, old))

    await cw._cleanup_audio()

    # 孤儿被删，被引用的保留
    assert not (tmp_path / orphan_path).exists()
    assert (tmp_path / referenced_path).exists()
