from fastapi import APIRouter, Depends, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.task import SynthesisTask
from app.schemas.tts import TTSRequest, TTSResponse
from app.security.dependencies import get_current_user, get_visitor_or_user
from app.security.quota import QUOTA_KIND_TTS, check_quota, consume_quota
from app.services.tts_service import synthesize_tts

router = APIRouter(prefix="/api/tts", tags=["tts"])


@router.post("/synthesize", response_model=TTSResponse)
async def synthesize(
    data: TTSRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
    user_or_visitor=Depends(get_visitor_or_user),
):
    user, visitor_token = user_or_visitor
    if visitor_token:
        response.set_cookie(
            "visitor_token", visitor_token,
            max_age=86400, httponly=True, samesite="lax",
        )

    # 配额只对登录用户生效。游客没有 user_id 可计数，无法按账号限额，
    # 依赖限流中间件的 IP 级 30 次/分兜底（quota 模块是防滥用闸门，
    # 不是计费系统——不打算给游客发"体验额度"来引流注册）。
    if user is not None:
        await check_quota(user, QUOTA_KIND_TTS)

    user_id = str(user.id) if user else None
    result = await synthesize_tts(db, user_id, data)

    # 成功后才计数：Redis 无法把外部 HTTP 调用包进事务，预扣+回滚在进程
    # 崩溃/超时路径上不可靠，会产生幽灵扣减；后置计数最坏是失败请求未计费，
    # 由 IP 限流兜底。
    if user is not None:
        await consume_quota(user.id, QUOTA_KIND_TTS, cost=1)

    return result


@router.get("/history")
async def get_history(
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """登录用户的合成历史（最近 20 条），复用 SynthesisTask 表。

    游客无法访问（无 user_id 可关联），前端对游客降级到 localStorage。
    每条音频 URL 走 HMAC 签名（与 synthesize 返回一致），带过期时间。
    """
    from app.api.media import sign_media_url

    result = await db.execute(
        select(SynthesisTask)
        .where(SynthesisTask.user_id == user.id)
        .order_by(SynthesisTask.created_at.desc())
        .limit(20)
    )
    tasks = result.scalars().all()
    return [
        {
            "id": str(t.id),
            "text": t.input_text or "",
            "audio_url": sign_media_url(t.output_audio_path) if t.output_audio_path else None,
            "created_at": t.created_at.isoformat() if t.created_at else None,
            "provider": t.provider_used,
        }
        for t in tasks
    ]
