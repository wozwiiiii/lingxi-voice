"""P0 超时与收敛测试：任何异常路径都必须收敛项目状态并释放幂等锁。

背景：课件任务跑在 Celery worker 里，LLM/供应商调用原先无超时（SDK 默认
600s），加上 worker --concurrency=2，两个卡死任务即全站停摆，且项目永久
停在 synthesizing、幂等锁挂满 3600s——用户彻底失去自救手段。

这些测试直接 ``await cw._synthesize(...)`` 绕过 Celery 入口（现有测试都是
整体 mock 掉入口，任务内部逻辑零覆盖），通过 task_db fixture 让任务内部的
模块级 AsyncSessionLocal 落到与 db_session 相同的测试库。
"""

import asyncio
import uuid

import pytest
from sqlalchemy import select

import app.tasks.courseware_tasks as cw
from app.config import settings
from app.models.courseware import CoursewareProject, CoursewareSlide, CoursewareSlide as _CWS  # noqa: F401
from app.models.user import User


def _as_uuid(v):
    """Python 3.10 的 uuid.UUID() 不接受 UUID 实例，这里统一归一化。"""
    return v if isinstance(v, uuid.UUID) else uuid.UUID(str(v))


async def _make_project_with_slides(db_session, n_slides=2, status="ready"):
    from sqlalchemy import select as _select

    result = await db_session.execute(
        _select(User).where(User.email == "cw_test@example.com")
    )
    user = result.scalar_one()
    project = CoursewareProject(user_id=user.id, title="Timeout Test", status=status)
    db_session.add(project)
    await db_session.flush()
    for i in range(n_slides):
        db_session.add(
            CoursewareSlide(
                project_id=project.id, slide_index=i,
                original_text=f"第{i}页内容",
            )
        )
    await db_session.commit()
    return project


async def _reload_project(db_session, project_id):
    result = await db_session.execute(
        select(CoursewareProject)
        .where(CoursewareProject.id == _as_uuid(project_id))
        .execution_options(populate_existing=True)
    )
    return result.scalar_one()


async def _reload_slides(db_session, project_id):
    result = await db_session.execute(
        select(CoursewareSlide)
        .where(CoursewareSlide.project_id == _as_uuid(project_id))
        .order_by(CoursewareSlide.slide_index)
        .execution_options(populate_existing=True)
    )
    return list(result.scalars().all())


@pytest.mark.asyncio
async def test_slide_timeout_marks_failed_and_releases_lock(client, auth_headers, task_db, db_session, monkeypatch):
    """单页超时 → 页标 failed(timeout)、项目收敛 failed、幂等锁释放。"""
    project = await _make_project_with_slides(db_session)
    from app.utils import redis_client as redis_module

    redis = redis_module.redis_client
    lock_key = f"courseware:lock:{project.id}"
    await redis.set(lock_key, "1", ex=3600)

    async def hang(db, slide):
        await asyncio.sleep(10)

    monkeypatch.setattr(cw, "_synthesize_slide", hang)
    monkeypatch.setattr(settings, "COURSEWARE_SLIDE_TIMEOUT_S", 0.1)

    await cw._synthesize(str(project.id))

    slides = await _reload_slides(db_session, project.id)
    assert all(s.status == "failed" for s in slides)
    assert all(s.error_code == "timeout" for s in slides)

    project_row = await _reload_project(db_session, str(project.id))
    assert project_row.status == "failed"
    assert project_row.error_code == "provider_unavailable"  # timeout 可重试

    assert await redis.get(lock_key) is None, "收敛后必须释放幂等锁"


@pytest.mark.asyncio
async def test_cancelled_error_still_finalizes(client, auth_headers, task_db, db_session, monkeypatch):
    """CancelledError 穿透 except Exception：页留 pending，但项目必须收敛。

    这是本次改造的核心陷阱：wait_for 触发的 CancelledError 是 BaseException，
    旧代码（except Exception 吞掉一切）抓不到它，gather 外抛后
    _finalize_project 被跳过——项目永久卡在 synthesizing。
    """
    project = await _make_project_with_slides(db_session)
    from app.utils import redis_client as redis_module

    redis = redis_module.redis_client
    lock_key = f"courseware:lock:{project.id}"
    await redis.set(lock_key, "1", ex=3600)

    async def cancelled(db, slide):
        raise asyncio.CancelledError()

    monkeypatch.setattr(cw, "_synthesize_slide", cancelled)

    await cw._synthesize(str(project.id))

    slides = await _reload_slides(db_session, project.id)
    # 页不被误标 failed：取消不是失败，留 pending 供下次重试
    assert all(s.status == "pending" for s in slides)
    assert all(s.error_code is None for s in slides)

    project_row = await _reload_project(db_session, str(project.id))
    # 仍有未处理页 → 必须判 failed（可重试），而不是 completed（缺页 zip）
    assert project_row.status == "failed"
    assert await redis.get(lock_key) is None


@pytest.mark.asyncio
async def test_push_progress_failure_does_not_break_task(client, auth_headers, task_db, db_session, monkeypatch):
    """进度推送（旁路）失败绝不能冒泡——旧行为是跳过 _finalize_project。"""
    project = await _make_project_with_slides(db_session, n_slides=1)

    async def broken_push(pid):
        raise RuntimeError("redis down")

    async def instant(db, slide):
        slide.status = "completed"

    monkeypatch.setattr(cw, "_push_progress", broken_push)
    monkeypatch.setattr(cw, "_synthesize_slide", instant)

    await cw._synthesize(str(project.id))  # 不应抛出

    project_row = await _reload_project(db_session, str(project.id))
    assert project_row.status == "completed"


@pytest.mark.asyncio
async def test_task_deadline_marks_unexecuted_slides_failed(client, auth_headers, task_db, db_session, monkeypatch):
    """总时长软墙：deadline 已过的页必须标 failed（timeout），不留 pending。"""
    project = await _make_project_with_slides(db_session, n_slides=3)
    monkeypatch.setattr(settings, "COURSEWARE_TASK_TOTAL_TIMEOUT_S", -1.0)

    async def instant(db, slide):
        slide.status = "completed"

    monkeypatch.setattr(cw, "_synthesize_slide", instant)

    await cw._synthesize(str(project.id))

    slides = await _reload_slides(db_session, project.id)
    assert all(s.status == "failed" for s in slides)
    assert all(s.error_code == "timeout" for s in slides)
