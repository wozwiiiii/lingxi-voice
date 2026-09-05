"""P0 错误分类测试：区分「重试有用」与「重试没用」，并修复熔断计数（F1）。

F1 是本次最关键的回归断言：provider 的 402/429/5xx 全部以 ValueError 子类
抛出，而 tts_service 的 ``except ValueError → 503`` 分支原先从不调用
``record_failure()``——最常见的失效（上游限流/宕机）永远不会触发熔断，
熔断器形同虚设。下面 sync 链路的用例锁死这个行为。
"""

import asyncio
import uuid

import pytest
from sqlalchemy import select

import app.tasks.courseware_tasks as cw
import app.services.tts_service as tts_service
from app.models.courseware import CoursewareProject, CoursewareSlide
from app.models.user import User
from app.providers.errors import ContentError, ProviderUnavailableError
from app.utils.error_codes import SlideErrorCode, classify_exc


class FakeProvider:
    def __init__(self, exc=None):
        self._exc = exc
        self.name = "cloud:siliconflow"

    async def synthesize(self, text, voice_id, params):
        if self._exc is not None:
            raise self._exc
        return None


class FakeCircuit:
    def __init__(self):
        self.failures = 0
        self.successes = 0

    async def record_failure(self):
        self.failures += 1

    async def record_success(self):
        self.successes += 1


# ---------- classify_exc 纯函数（不需要 DB） ----------


@pytest.mark.parametrize("exc,expected", [
    (ProviderUnavailableError("429"), SlideErrorCode.PROVIDER_UNAVAILABLE),
    (ContentError("400"), SlideErrorCode.CONTENT_ERROR),
    (RuntimeError("All TTS providers are unavailable"), SlideErrorCode.PROVIDER_UNAVAILABLE),
    (asyncio.TimeoutError(), SlideErrorCode.TIMEOUT),
    (ValueError("unknown"), SlideErrorCode.CONTENT_ERROR),  # 未知异常保守归为不可重试
    (KeyError("x"), SlideErrorCode.CONTENT_ERROR),
])
def test_classify_exc(exc, expected):
    assert classify_exc(exc) == expected


# ---------- 课件任务链路 ----------


async def _make_project(db_session, n_slides=1):
    result = await db_session.execute(
        select(User).where(User.email == "cw_test@example.com")
    )
    user = result.scalar_one()
    project = CoursewareProject(user_id=user.id, title="ErrClass", status="ready")
    db_session.add(project)
    await db_session.flush()
    for i in range(n_slides):
        from app.models.voice import Voice
        voice = Voice(name="测试音色", type="preset",
                      provider="cloud:siliconflow", is_public=True)
        db_session.add(voice)
        await db_session.flush()
        db_session.add(
            CoursewareSlide(project_id=project.id, slide_index=i,
                            original_text="内容", voice_id=voice.id)
        )
    await db_session.commit()
    return project


async def _reload(db_session, project_id):
    result = await db_session.execute(
        select(CoursewareSlide).where(
            CoursewareSlide.project_id == uuid.UUID(str(project_id))
        )
    )
    return list(result.scalars().all())


@pytest.mark.asyncio
async def test_provider_unavailable_records_circuit(client, auth_headers, task_db, db_session, monkeypatch):
    circuit = FakeCircuit()
    async def _get_provider():
        return FakeProvider(ProviderUnavailableError("语音服务请求过于频繁"))

    monkeypatch.setattr(cw, "get_active_provider_async", _get_provider)
    monkeypatch.setattr(cw, "get_circuit_for_provider", lambda name: circuit)

    project = await _make_project(db_session)
    await cw._synthesize(str(project.id))

    slides = await _reload(db_session, project.id)
    assert slides[0].status == "failed"
    assert slides[0].error_code == "provider_unavailable"
    assert circuit.failures == 1, "供应商不可用必须计入熔断"


@pytest.mark.asyncio
async def test_content_error_does_not_pollute_circuit(client, auth_headers, task_db, db_session, monkeypatch):
    circuit = FakeCircuit()
    async def _get_provider():
        return FakeProvider(ContentError("语音合成参数错误"))

    monkeypatch.setattr(cw, "get_active_provider_async", _get_provider)
    monkeypatch.setattr(cw, "get_circuit_for_provider", lambda name: circuit)

    project = await _make_project(db_session)
    await cw._synthesize(str(project.id))

    slides = await _reload(db_session, project.id)
    assert slides[0].error_code == "content_error"
    assert circuit.failures == 0, "内容错误不是供应商的锅，不该打开熔断"


@pytest.mark.asyncio
async def test_all_providers_unavailable_classified(client, auth_headers, task_db, db_session, monkeypatch):
    """get_active_provider_async 抛 RuntimeError（熔断全开）→ 可重试类别。"""
    circuit = FakeCircuit()

    async def no_provider():
        raise RuntimeError("All TTS providers are unavailable")

    monkeypatch.setattr(cw, "get_active_provider_async", no_provider)
    monkeypatch.setattr(cw, "get_circuit_for_provider", lambda name: circuit)

    project = await _make_project(db_session)
    await cw._synthesize(str(project.id))

    slides = await _reload(db_session, project.id)
    assert slides[0].error_code == "provider_unavailable"
    assert circuit.failures == 0, "链路层面无 provider 可用，不应归咎于某个 provider"


@pytest.mark.asyncio
async def test_project_error_code_aggregates_retryable(client, auth_headers, task_db, db_session, monkeypatch):
    """任一页可重试 → 项目级 provider_unavailable；全为内容错误 → content_error。"""
    async def _get_provider():
        return FakeProvider(ContentError("参数错误"))

    monkeypatch.setattr(cw, "get_active_provider_async", _get_provider)
    monkeypatch.setattr(cw, "get_circuit_for_provider", lambda name: FakeCircuit())

    project = await _make_project(db_session, n_slides=2)
    await cw._synthesize(str(project.id))

    fresh = await db_session.execute(
        select(CoursewareProject).where(CoursewareProject.id == project.id)
    )
    proj = fresh.scalar_one()
    assert proj.error_code == "content_error"
    assert proj.error_message == "2/2 页合成失败"


# ---------- 同步 TTS 链路（F1 修复的核心回归断言） ----------


async def _make_preset_voice(db_session):
    """TTS 请求先解析 voice_id（不存在直接 404），必须先落库一个预设音色。"""
    from app.models.voice import Voice

    voice = Voice(name="测试音色", type="preset", provider="cloud:siliconflow",
                  is_public=True)
    db_session.add(voice)
    await db_session.commit()
    return voice


@pytest.mark.asyncio
async def test_sync_tts_provider_error_counts_circuit(client, db_session, monkeypatch):
    """provider 抛 ProviderUnavailableError → 503 且熔断失败计数 +1。"""
    circuit = FakeCircuit()
    voice = await _make_preset_voice(db_session)

    async def get_provider():
        return FakeProvider(ProviderUnavailableError("语音服务请求过于频繁，请稍后重试"))

    monkeypatch.setattr(tts_service, "get_active_provider_async", get_provider)
    monkeypatch.setattr(tts_service, "get_circuit_for_provider", lambda name: circuit)

    resp = await client.post("/api/tts/synthesize", json={
        "text": "你好世界", "voice_id": str(voice.id),
    })
    assert resp.status_code == 503
    assert circuit.failures == 1, "F1：此前该路径从不记熔断，最常见的上游失效反而无法触发熔断"


@pytest.mark.asyncio
async def test_sync_tts_content_error_skips_circuit(client, db_session, monkeypatch):
    circuit = FakeCircuit()
    voice = await _make_preset_voice(db_session)

    async def get_provider():
        return FakeProvider(ContentError("语音合成参数错误"))

    monkeypatch.setattr(tts_service, "get_active_provider_async", get_provider)
    monkeypatch.setattr(tts_service, "get_circuit_for_provider", lambda name: circuit)

    resp = await client.post("/api/tts/synthesize", json={
        "text": "你好世界", "voice_id": str(voice.id),
    })
    assert resp.status_code == 503  # 状态码语义不变（继承 ValueError 的契约）
    assert circuit.failures == 0
