"""端到端契约验证脚本（临时，复用 fakeredis + SQLite in-memory）。

用真实 httpx 客户端走完整 FastAPI HTTP 栈（含中间件、序列化、依赖注入），
验证前端依赖的核心 API 契约。不修改生产代码。

运行: cd backend && python scripts/contract_check.py
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import fakeredis.aioredis
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.database import get_db
from app.main import app
from app.models.base import Base
from app.utils import redis_client as redis_module

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"
PASS = 0
FAIL = 0
FAILURES: list[str] = []


def check(name: str, cond: bool, detail: str = ""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  [OK] {name}")
    else:
        FAIL += 1
        FAILURES.append(f"{name}: {detail}")
        print(f"  [FAIL] {name} - {detail}")


async def run():
    engine = create_async_engine(
        TEST_DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    fake_redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    original_redis = redis_module.redis_client
    redis_module.redis_client = fake_redis

    # 共享单个 session（与 pytest conftest 一致）：SQLite in-memory 每个连接是独立库
    async with session_factory() as shared_session:
        async def override_get_db():
            yield shared_session

        async def override_get_redis():
            return fake_redis

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[redis_module.get_redis] = override_get_redis

        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as c:
                print("== 1. 健康检查 ==")
                r = await c.get("/api/health")
                check("GET /api/health -> 200", r.status_code == 200, str(r.status_code))

                print("\n== 2. 注册 ==")
                r = await c.post("/api/auth/register", json={
                    "email": "e2e@example.com", "username": "e2euser", "password": "password123",
                })
                check("注册 -> 201 + UserResponse snake_case", r.status_code == 201, str(r.status_code))
                if r.status_code == 201:
                    body = r.json()
                    check("UserResponse 字段(id/email/username/role)", all(
                        k in body for k in ("id", "email", "username", "role")), str(body))

                print("\n== 3. 登录（Token 契约）==")
                r = await c.post("/api/auth/login", json={
                    "email": "e2e@example.com", "password": "password123",
                })
                check("登录 -> 200", r.status_code == 200, str(r.status_code))
                tokens = r.json()
                check("TokenResponse 含 access_token/refresh_token/token_type",
                      all(k in tokens for k in ("access_token", "refresh_token", "token_type")),
                      str(tokens))
                access = tokens.get("access_token", "")
                refresh = tokens.get("refresh_token", "")
                check("access_token 非空", bool(access))
                check("refresh_token 非空", bool(refresh))
                auth_headers = {"Authorization": f"Bearer {access}"}

                print("\n== 4. /me ==")
                r = await c.get("/api/auth/me", headers=auth_headers)
                check("/me 带 token -> 200", r.status_code == 200, str(r.status_code))
                if r.status_code == 200:
                    me = r.json()
                    check("/me 返回 email", me.get("email") == "e2e@example.com", str(me))
                r = await c.get("/api/auth/me")
                check("/me 无 token -> 401", r.status_code == 401, str(r.status_code))

                print("\n== 5. refresh ==")
                r = await c.post("/api/auth/refresh", json={"refresh_token": refresh})
                check("refresh -> 200 + 新 access_token",
                      r.status_code == 200 and bool(r.json().get("access_token")), str(r.status_code))
                r = await c.post("/api/auth/refresh", json={"refresh_token": "bogus"})
                check("refresh 伪造 token -> 401", r.status_code == 401, str(r.status_code))

                print("\n== 6. voices（前端 TTS 页依赖）==")
                r = await c.get("/api/voices")
                check("GET /api/voices -> 200", r.status_code == 200, str(r.status_code))
                if r.status_code == 200:
                    voices = r.json()
                    check("voices 是数组", isinstance(voices, list), str(type(voices)))
                    if isinstance(voices, list) and voices:
                        v0 = voices[0]
                        check("voice 字段(id/name/type/is_public)",
                              all(k in v0 for k in ("id", "name", "type", "is_public")), str(v0))

                print("\n== 7. capabilities ==")
                r = await c.get("/api/capabilities")
                check("GET /api/capabilities -> 200", r.status_code == 200, str(r.status_code))

                print("\n== 8. 课件库（预设/我的）==")
                r = await c.get("/api/courseware", params={"type": "preset"}, headers=auth_headers)
                check("GET /api/courseware?type=preset -> 200", r.status_code == 200, str(r.status_code))
                if r.status_code == 200:
                    lib = r.json()
                    check("列表含 projects+total", all(k in lib for k in ("projects", "total")), str(lib))
                r = await c.get("/api/courseware", params={"type": "my"}, headers=auth_headers)
                check("GET /api/courseware?type=my -> 200", r.status_code == 200, str(r.status_code))

                print("\n== 9. 未登录访问受保护路由 ==")
                r = await c.get("/api/courseware", params={"type": "my"})
                check("无 token 访问 /api/courseware -> 401", r.status_code == 401, str(r.status_code))

                print("\n== 10. 登出（#8 相关：后端契约）==")
                r = await c.post("/api/auth/logout", headers=auth_headers)
                check("POST /api/auth/logout -> 204", r.status_code == 204, str(r.status_code))
                r = await c.get("/api/auth/me", headers=auth_headers)
                check("登出后旧 token /me -> 401", r.status_code == 401, str(r.status_code))

                print("\n== 11. 权限守卫（#6 相关）==")
                await c.post("/api/auth/register", json={
                    "email": "other@example.com", "username": "otheruser", "password": "password123",
                })
                r = await c.post("/api/auth/login", json={
                    "email": "other@example.com", "password": "password123",
                })
                check("用户2 登录 -> 200", r.status_code == 200, str(r.status_code))
        finally:
            app.dependency_overrides.clear()
            redis_module.redis_client = original_redis

    # 先退出 session 再 dispose engine，避免 "no active connection"
    await engine.dispose()

    print(f"\n{'=' * 50}")
    print(f"结果: {PASS} 通过, {FAIL} 失败")
    if FAILURES:
        print("失败项:")
        for f in FAILURES:
            print(f"  - {f}")
        return 1
    print("[OK] 所有前端依赖契约验证通过")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(run()))
