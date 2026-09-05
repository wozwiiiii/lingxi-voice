"""P0 月度配额测试：防滥用闸门的计数、超限、游客豁免与失败回退。"""

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select

import app.services.tts_service as tts_service
from app.models.user import User
from app.security import quota as quota_mod
from app.security.quota import (
    QUOTA_KIND_COURSEWARE,
    QUOTA_KIND_TTS,
    check_quota,
    consume_quota,
    month_key,
    quota_key,
    refund_quota,
)


def _redis(client):
    from app.utils import redis_client as redis_module

    return redis_module.redis_client


async def _make_preset_voice(db_session):
    """造一个公开预设音色：TTS 请求会先解析 voice_id，不存在直接 404，
    根本走不到 provider——必须先落库。"""
    from app.models.voice import Voice

    voice = Voice(name="测试音色", type="preset", provider="cloud:siliconflow",
                  is_public=True)
    db_session.add(voice)
    await db_session.commit()
    return voice


# ---------- 纯函数 ----------


def test_month_key_is_utc_format():
    from datetime import datetime, timezone

    assert month_key(datetime(2026, 9, 3, 23, 59, tzinfo=timezone.utc)) == "2026-09"
    # UTC 23 点之后的北京时间已是次日，但配额月不应漂移
    assert month_key(datetime(2026, 12, 31, 23, 0, tzinfo=timezone.utc)) == "2026-12"


def test_quota_key_includes_kind_and_month():
    k = quota_key(uuid.UUID(int=1), QUOTA_KIND_TTS)
    assert k.startswith("quota:monthly:tts:00000000-0000-0000-0000-000000000001:")
    assert k.endswith(month_key())


@pytest.mark.asyncio
async def test_consume_and_refund_roundtrip(client):
    r = _redis(client)
    uid = uuid.uuid4()
    usage = await consume_quota(uid, QUOTA_KIND_TTS, cost=1)
    assert usage == 1
    assert int(await r.get(quota_key(uid, QUOTA_KIND_TTS))) == 1

    await refund_quota(uid, QUOTA_KIND_TTS, cost=1)
    assert await r.get(quota_key(uid, QUOTA_KIND_TTS)) is None, "减到 0 必须删 key，不留负值"


@pytest.mark.asyncio
async def test_check_quota_raises_429_with_retry_after(client, monkeypatch):
    uid = uuid.uuid4()
    # 连续扣满默认额度，验证超限路径
    monkeypatch.setattr(quota_mod.settings, "QUOTA_MONTHLY_TTS", 2)
    await consume_quota(uid, QUOTA_KIND_TTS, cost=2)

    from fastapi import HTTPException

    class _U:
        id = uid
        quota_override = None

    with pytest.raises(HTTPException) as exc:
        await check_quota(_U(), QUOTA_KIND_TTS)
    assert exc.value.status_code == 429
    assert "Retry-After" in exc.value.headers
    assert "配额" in exc.value.detail


@pytest.mark.asyncio
async def test_quota_override_takes_precedence(client):
    uid = uuid.uuid4()

    class _U:
        id = uid
        quota_override = {"tts": 1}

    await check_quota(_U(), QUOTA_KIND_TTS)  # 用量 0，未超限
    await consume_quota(uid, QUOTA_KIND_TTS)

    from fastapi import HTTPException

    with pytest.raises(HTTPException):
        await check_quota(_U(), QUOTA_KIND_TTS)  # 用量 1，覆盖额度 1，超限


@pytest.mark.asyncio
async def test_redis_down_fails_open(client, monkeypatch):
    """Redis 故障时必须放行：配额是保护措施，不能反噬业务。"""

    async def broken():
        raise ConnectionError("redis down")

    monkeypatch.setattr(quota_mod, "get_redis", broken)
    # 不抛异常即通过
    await check_quota(uuid.uuid4(), QUOTA_KIND_TTS)
    usage = await consume_quota(uuid.uuid4(), QUOTA_KIND_TTS)
    assert usage == 1


# ---------- API 集成 ----------


@pytest.mark.asyncio
async def test_guest_tts_creates_no_quota_key(client, db_session, monkeypatch):
    """游客路径跳过配额（无 user_id 可计数），不得产生任何配额 key。"""
    from app.providers.errors import ProviderUnavailableError

    voice = await _make_preset_voice(db_session)

    class FakeProvider:
        name = "cloud:siliconflow"

        async def synthesize(self, text, voice_id, params):
            raise ProviderUnavailableError("down")

    async def get_provider():
        return FakeProvider()

    monkeypatch.setattr(tts_service, "get_active_provider_async", get_provider)
    monkeypatch.setattr(tts_service, "get_circuit_for_provider", lambda name: None)

    resp = await client.post("/api/tts/synthesize", json={
        "text": "你好世界", "voice_id": str(voice.id),
    })
    assert resp.status_code == 503

    r = _redis(client)
    keys = await r.keys("quota:monthly:*")
    assert keys == [], "游客不得产生配额计数"


@pytest.mark.asyncio
async def test_logged_in_failed_tts_is_not_charged(client, auth_headers, db_session, monkeypatch):
    """后置计数：失败的合成不计费（由 IP 限流兜底）。"""
    from app.providers.errors import ProviderUnavailableError

    voice = await _make_preset_voice(db_session)

    class FakeProvider:
        name = "cloud:siliconflow"

        async def synthesize(self, text, voice_id, params):
            raise ProviderUnavailableError("down")

    async def get_provider():
        return FakeProvider()

    monkeypatch.setattr(tts_service, "get_active_provider_async", get_provider)
    monkeypatch.setattr(tts_service, "get_circuit_for_provider", lambda name: None)

    resp = await client.post("/api/tts/synthesize", json={
        "text": "你好世界", "voice_id": str(voice.id),
    }, headers=auth_headers)
    assert resp.status_code == 503

    r = _redis(client)
    assert await r.keys("quota:monthly:*") == []


@pytest.mark.asyncio
async def test_courseware_quota_blocks_before_side_effects(
    client: AsyncClient, auth_headers, db_session, monkeypatch
):
    """课件配额按待合成页数预扣；超限时零副作用（状态不变、锁不留、不投递）。"""
    from app.models.courseware import CoursewareProject, CoursewareSlide

    result = await db_session.execute(
        select(User).where(User.email == "cw_test@example.com")
    )
    user = result.scalar_one()
    user.quota_override = {"courseware": 2}
    db_session.add(user)

    project = CoursewareProject(user_id=user.id, title="Quota Test", status="ready")
    db_session.add(project)
    await db_session.flush()
    for i in range(3):
        db_session.add(
            CoursewareSlide(project_id=project.id, slide_index=i, original_text=f"p{i}")
        )
    await db_session.commit()

    delay_called = []

    class FakeTask:
        @staticmethod
        def delay(*a, **kw):
            delay_called.append(a)

    import app.tasks.courseware_tasks as cw_tasks

    # 端点是请求时局部导入（from app.tasks.courseware_tasks import ...），
    # 所以必须 patch 任务模块本身的属性，patch api 模块无效
    monkeypatch.setattr(cw_tasks, "synthesize_courseware_task", FakeTask, raising=False)

    resp = await client.post(
        f"/api/courseware/{project.id}/synthesize", headers=auth_headers
    )
    assert resp.status_code == 429
    assert "配额" in resp.json()["detail"]
    assert delay_called == [], "超限必须在投递任务之前被拦下"

    fresh = await db_session.get(CoursewareProject, project.id)
    assert fresh.status == "ready", "超限请求不得改变项目状态"

    r = _redis(client)
    assert await r.get(f"courseware:lock:{project.id}") is None, "超限不得留下幂等锁"


@pytest.mark.asyncio
async def test_courseware_quota_charges_pending_pages(
    client: AsyncClient, auth_headers, db_session, monkeypatch
):
    """预扣口径是 pending+failed 页数（重试只跑这些页），不是 slides_count。"""
    from app.models.courseware import CoursewareProject, CoursewareSlide

    result = await db_session.execute(
        select(User).where(User.email == "cw_test@example.com")
    )
    user = result.scalar_one()
    user.quota_override = {"courseware": 2}
    db_session.add(user)

    project = CoursewareProject(user_id=user.id, title="Charge Test", status="ready")
    db_session.add(project)
    await db_session.flush()
    # 1 页已完成 + 2 页待合成：重试只跑 2 页，配额 2 应该刚好够
    db_session.add(CoursewareSlide(
        project_id=project.id, slide_index=0, status="completed"))
    db_session.add(CoursewareSlide(project_id=project.id, slide_index=1))
    db_session.add(CoursewareSlide(project_id=project.id, slide_index=2))
    await db_session.commit()

    submitted = []

    class FakeTask:
        @staticmethod
        def delay(*a, **kw):
            submitted.append(a)

    import app.tasks.courseware_tasks as cw_tasks

    # 端点是请求时局部导入（from app.tasks.courseware_tasks import ...），
    # 所以必须 patch 任务模块本身的属性，patch api 模块无效
    monkeypatch.setattr(cw_tasks, "synthesize_courseware_task", FakeTask, raising=False)

    resp = await client.post(
        f"/api/courseware/{project.id}/synthesize", headers=auth_headers
    )
    assert resp.status_code == 200
    assert len(submitted) == 1

    r = _redis(client)
    usage = await r.get(quota_key(user.id, QUOTA_KIND_COURSEWARE))
    assert int(usage) == 2, "只按待合成页数计费，已完成页不重复扣"


@pytest.mark.asyncio
async def test_courseware_quota_refunded_on_broker_failure(
    client: AsyncClient, auth_headers, db_session, monkeypatch
):
    """任务投递失败 → 预扣必须回退（否则用户为一次没发生的合成买单）。"""
    from app.models.courseware import CoursewareProject, CoursewareSlide

    result = await db_session.execute(
        select(User).where(User.email == "cw_test@example.com")
    )
    user = result.scalar_one()
    project = CoursewareProject(user_id=user.id, title="Refund Test", status="ready")
    db_session.add(project)
    await db_session.flush()
    db_session.add(CoursewareSlide(project_id=project.id, slide_index=0))
    await db_session.commit()

    class FakeTask:
        @staticmethod
        def delay(*a, **kw):
            raise ConnectionError("broker down")

    import app.tasks.courseware_tasks as cw_tasks

    # 端点是请求时局部导入（from app.tasks.courseware_tasks import ...），
    # 所以必须 patch 任务模块本身的属性，patch api 模块无效
    monkeypatch.setattr(cw_tasks, "synthesize_courseware_task", FakeTask, raising=False)

    resp = await client.post(
        f"/api/courseware/{project.id}/synthesize", headers=auth_headers
    )
    assert resp.status_code in (500, 503)

    r = _redis(client)
    assert await r.get(quota_key(user.id, QUOTA_KIND_COURSEWARE)) is None, \
        "投递失败必须退还预扣配额"
