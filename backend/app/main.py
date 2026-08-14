# Security: enable defusedxml BEFORE any lxml import (python-pptx uses lxml internally)
import defusedxml.lxml  # noqa: F401 — side-effect: patches lxml globally

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.auth import router as auth_router
from app.api.capabilities import router as capabilities_router
from app.api.courseware import router as courseware_router
from app.api.tts import router as tts_router
from app.api.voices import router as voices_router
from app.config import settings

from contextlib import asynccontextmanager


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: validate secrets. Shutdown: no-op."""
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
    bucket. The first X-Forwarded-For entry is the original client.
    """
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
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
                key = f"tts:rate:{payload['sub']}:1min"
            except Exception:
                key = f"tts:rate:ip:{_client_ip(request)}:1min"
        else:
            key = f"tts:rate:ip:{_client_ip(request)}:1min"

        await rate_limiter.check(key)

    response = await call_next(request)
    return response


app.include_router(auth_router)
app.include_router(tts_router)
app.include_router(voices_router)
app.include_router(capabilities_router)
app.include_router(courseware_router)

# 挂载 /media 静态目录，让合成/克隆的音频文件可直接通过 FastAPI 访问。
# 生产环境由 nginx 的 location /media/ 直接服务，此处保证本地开发（仅 backend+frontend）也能播放。
Path(settings.MEDIA_ROOT).mkdir(parents=True, exist_ok=True)
app.mount("/media", StaticFiles(directory=settings.MEDIA_ROOT), name="media")


@app.get("/api/health")
async def health():
    return {"status": "ok"}
