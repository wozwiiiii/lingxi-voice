# Security: enable defusedxml BEFORE any lxml import (python-pptx uses lxml internally)
import defusedxml.lxml  # noqa: F401 — side-effect: patches lxml globally

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.api.auth import router as auth_router
from app.api.capabilities import router as capabilities_router
from app.api.courseware import router as courseware_router
from app.api.tts import router as tts_router
from app.api.voices import router as voices_router
from app.config import settings

from contextlib import asynccontextmanager

from dotenv import load_dotenv
load_dotenv(dotenv_path="D:/AI_Program/fuchuang_project/lingxi-voice/deploy/.env")



@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: validate secrets, seed preset data. Shutdown: no-op."""
    weak = (
        "change-me", "change-me-to-random-64-chars", "",
        "lingxi-dev-secret-do-not-use-in-production",
    )
    if settings.JWT_SECRET_KEY in weak:
        raise RuntimeError(
            "JWT_SECRET_KEY must be set to a strong random value. "
            "Generate: openssl rand -base64 64"
        )
    if len(settings.JWT_SECRET_KEY) < 32:
        raise RuntimeError(
            "JWT_SECRET_KEY must be at least 32 characters for HMAC-SHA256 security"
        )

    # 种子数据：预设声音 + 预设课件（幂等）。全新部署后 voices 表为空
    # 会导致前端无音色可选、TTS 全链路不可用，故必须在启动时执行。
    # 失败不阻断启动（如 provider 暂不可用），下次启动会重试。
    import logging

    logger = logging.getLogger(__name__)
    from app.database import AsyncSessionLocal
    from app.services.courseware_service import seed_courseware_presets
    from app.services.voice_service import seed_preset_voices

    try:
        async with AsyncSessionLocal() as db:
            await seed_preset_voices(db)
            await seed_courseware_presets(db)
            await db.commit()
    except Exception as e:
        logger.warning(f"Preset seeding skipped (will retry on next start): {e}")

    yield


app = FastAPI(title="LingXi Voice API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _client_ip(request: Request) -> str:
    """Return the real client IP, honoring X-Forwarded-For set by nginx (#9).

    Behind a reverse proxy, request.client.host is the nginx container IP shared
    by every visitor — keying on it would collapse all traffic into one rate
    bucket.

    信任模型：nginx 用 `$proxy_add_x_forwarded_for` 在**末尾追加**真实来源，
    因此只有最右侧条目由可信代理写入，左侧条目可被客户端任意伪造。
    取最右侧条目可防止攻击者通过自带 X-Forwarded-For 头伪造 IP 绕过限流。
    """
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        entries = [e.strip() for e in forwarded.split(",") if e.strip()]
        if entries:
            return entries[-1]
    return request.client.host if request.client else ""


@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    if request.url.path.startswith("/api/") and not request.url.path.startswith(
        "/api/health"
    ):
        from app.security.rate_limit import rate_limiter

        auth = request.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            try:
                from app.security.jwt import decode_token

                payload = decode_token(auth[7:])
                # P2-10：解码结果挂到 state，get_current_user 复用，
                # 避免每个请求验签两次（中间件一次 + 依赖项一次）
                request.state.jwt_payload = payload
                key = f"tts:rate:{payload['sub']}:1min"
            except Exception:
                key = f"tts:rate:ip:{_client_ip(request)}:1min"
        else:
            key = f"tts:rate:ip:{_client_ip(request)}:1min"

        # 登录接口独立更严限流（P2-8）：全局限流 30 次/分对撞库/爆破而言
        # 窗口过大，业界惯例登录类接口收紧到 5-10 次/分。
        # 账号维度锁定（失败递增延迟）是有意的未实现项，见面试/02。
        max_override = 10 if request.url.path == "/api/auth/login" else None

        await rate_limiter.check(key, max_override=max_override)

    response = await call_next(request)
    return response


app.include_router(auth_router)
app.include_router(tts_router)
app.include_router(voices_router)
app.include_router(capabilities_router)
app.include_router(courseware_router)

# /media 不再直接挂 StaticFiles（P2-5）：改走带 HMAC 签名与过期时间的
# 鉴权路由（app/api/media.py），防止 URL 泄露后被永久访问。
# 生产 nginx 的 /media/ 本就反代到本服务，应用层校验对生产同样生效。
Path(settings.MEDIA_ROOT).mkdir(parents=True, exist_ok=True)
from app.api.media import router as media_router  # noqa: E402

app.include_router(media_router)


@app.get("/api/health")
async def health():
    return {"status": "ok"}
