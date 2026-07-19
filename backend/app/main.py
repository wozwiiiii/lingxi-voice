from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.api.auth import router as auth_router
from app.api.capabilities import router as capabilities_router
from app.api.tts import router as tts_router
from app.api.voices import router as voices_router
from app.config import settings

app = FastAPI(title="LingXi Voice API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


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
                key = f"tts:rate:ip:{request.client.host}:1min"
        else:
            key = f"tts:rate:ip:{request.client.host}:1min"

        await rate_limiter.check(key)

    response = await call_next(request)
    return response


app.include_router(auth_router)
app.include_router(tts_router)
app.include_router(voices_router)
app.include_router(capabilities_router)


@app.get("/api/health")
async def health():
    return {"status": "ok"}
