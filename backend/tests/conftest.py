import asyncio
from typing import AsyncGenerator

import fakeredis.aioredis
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.database import get_db
from app.main import app
from app.models.base import Base
from app.utils import redis_client as redis_module

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

_test_engine = None


def _get_test_engine():
    """session 级惰性单例：全部测试共享一个内存引擎。

    原实现每个 db_session 都建一个独立引擎——对 API 测试没问题（DI 覆盖），
    但任务内部代码走的是模块级 AsyncSessionLocal（不可 DI），要测课件任务
    内部逻辑就必须让两条路径落到同一个库。StaticPool 保证内存库的所有
    AsyncSession 复用同一个 DBAPI 连接，任务里的多 session 并发才能看到
    测试写入的数据（与真实 PG 的行为一致）。
    """
    global _test_engine
    if _test_engine is None:
        _test_engine = create_async_engine(
            TEST_DATABASE_URL,
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
    return _test_engine


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    engine = _get_test_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with session_factory() as session:
        yield session

    # 清理：drop_all 保证每个测试从干净的表开始，避免测试间数据污染
    # （尤其任务内部逻辑直写 DB，不会走 client fixture 的清理）。
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    async def override_get_db():
        yield db_session

    # Replace global redis client with fakeredis (not just FastAPI DI override,
    # because internal code calls get_redis() directly, not via Depends).
    # 缓存库与安全状态库都替换为同一个 fakeredis 实例（逻辑库隔离是部署细节，
    # 测试只关心行为）。
    fake_redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    original_redis = redis_module.redis_client
    original_security_redis = redis_module.security_redis_client
    redis_module.redis_client = fake_redis
    redis_module.security_redis_client = fake_redis

    # Also override get_redis for DI-based calls
    async def override_get_redis():
        return fake_redis

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[redis_module.get_redis] = override_get_redis
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()
    redis_module.redis_client = original_redis
    redis_module.security_redis_client = original_security_redis


@pytest_asyncio.fixture
async def auth_headers(client: AsyncClient) -> dict:
    """Register+login a test user and return Authorization header."""
    await client.post("/api/auth/register", json={
        "email": "cw_test@example.com",
        "username": "cwtestuser",
        "password": "password123",
    })
    resp = await client.post("/api/auth/login", json={
        "email": "cw_test@example.com",
        "password": "password123",
    })
    tokens = resp.json()
    return {"Authorization": f"Bearer {tokens['access_token']}"}


@pytest_asyncio.fixture
async def task_db(db_session: AsyncSession) -> AsyncGenerator[AsyncSession, None]:
    """让课件任务内部的模块级 AsyncSessionLocal 落到同一个测试库。

    绝不能替换成"返回同一个 session"的假对象——任务的 gather 并发跑 3 个
    协程，共享一个 AsyncSession 会触发 "another operation is in progress"。
    这里用同一引擎的独立 session 工厂替换，行为与真实环境一致：每页一个
    独立 session，通过 StaticPool 共享同一连接，相互可见已提交数据。
    """
    import app.tasks.courseware_tasks as cw

    factory = async_sessionmaker(
        _get_test_engine(), class_=AsyncSession, expire_on_commit=False
    )
    original = cw.AsyncSessionLocal
    cw.AsyncSessionLocal = factory
    yield db_session
    cw.AsyncSessionLocal = original
