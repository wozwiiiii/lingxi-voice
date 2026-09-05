"""Courseware API — upload, edit, synthesize, download, library."""

import io
import uuid as uuid_mod

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.courseware import CoursewareProject, CoursewareSlide
from app.models.user import User
from app.schemas.courseware import (
    BulkSettingsUpdate,
    CoursewareListResponse,
    CoursewareProjectResponse,
    CoursewareSlideResponse,
    SlideUpdate,
    SynthesizeResponse,
)
from app.security.dependencies import get_current_user, get_visitor_or_user
from app.security.quota import QUOTA_KIND_COURSEWARE, check_quota, consume_quota, refund_quota
from app.services.courseware_service import (
    apply_bulk_settings,
    build_zip,
    create_from_upload,
    get_project,
    get_slides,
    update_slide,
)
from app.utils.storage import storage

router = APIRouter(prefix="/api/courseware", tags=["courseware"])


def _check_ownership(project: CoursewareProject | None, user: User | None) -> None:
    """Raise 404 if project doesn't exist or user doesn't own it.
    Public presets (user_id IS NULL) are accessible to everyone (read-only).
    Private projects require the owner or return 404 (prevents ID enumeration).
    """
    if not project:
        raise HTTPException(status_code=404)
    if project.user_id is not None and (user is None or project.user_id != user.id):
        raise HTTPException(status_code=404)


def _check_ownership_write(project: CoursewareProject | None, user: User | None) -> None:
    """Raise 404 unless project exists AND belongs to the authenticated user.

    Unlike read semantics, public presets (user_id IS NULL) can never be
    modified, deleted, or synthesized by anyone (security #6).
    """
    if not project or user is None or project.user_id != user.id:
        raise HTTPException(status_code=404)


async def _purge_tts_cache(redis, audio_path: str) -> None:
    """删除指向某音频文件的 TTS 结果缓存键（P2-6）。

    tts_service 写缓存时维护了反向索引 tts:refs:{path} → 缓存哈希
    （path 与哈希严格 1:1），删除文件时据此清掉 tts:result 键，
    避免缓存命中返回已删除路径。
    """
    refs_key = f"tts:refs:{audio_path}"
    cache_hash = await redis.get(refs_key)
    if cache_hash:
        await redis.delete(f"tts:result:{cache_hash}")
    await redis.delete(refs_key)


@router.post("/upload", response_model=CoursewareProjectResponse, status_code=201)
async def upload_pptx(
    file: UploadFile,
    description: str | None = None,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    valid_mime = "application/vnd.openxmlformats-officedocument.presentationml.presentation"
    if file.content_type != valid_mime:
        if file.content_type == "application/vnd.ms-powerpoint":
            raise HTTPException(
                status_code=400,
                detail="不支持旧版 .ppt 格式，请用 PowerPoint/WPS 另存为 .pptx 后重新上传",
            )
        raise HTTPException(status_code=400, detail="仅支持 .pptx 格式文件")

    content = await file.read()
    if len(content) > 20 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="文件过大(>20MB)")

    if content[:4] != b"PK\x03\x04":
        raise HTTPException(status_code=400, detail="文件不是有效的 PPTX 格式")

    filepath = await storage.save(content, "courseware", ".pptx")
    project = await create_from_upload(
        db, str(user.id), str(await storage.get_path(filepath)),
        file.filename or "untitled.pptx", description,
    )
    return project


@router.get("", response_model=CoursewareListResponse)
async def list_courseware(
    type: str = Query("my", pattern="^(preset|my)$"),
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    if type == "preset":
        stmt = (
            select(CoursewareProject)
            .where(CoursewareProject.user_id.is_(None))
            .order_by(CoursewareProject.created_at)
        )
    else:
        stmt = (
            select(CoursewareProject)
            .where(CoursewareProject.user_id == user.id)
            .order_by(CoursewareProject.created_at.desc())
        )
    result = await db.execute(stmt)
    projects = list(result.scalars().all())
    return CoursewareListResponse(projects=projects, total=len(projects))


@router.get("/{project_id}", response_model=CoursewareProjectResponse)
async def get_courseware_project(
    project_id: str,
    db: AsyncSession = Depends(get_db),
    user_or_visitor=Depends(get_visitor_or_user),
):
    project = await get_project(db, project_id)
    user, _ = user_or_visitor
    _check_ownership(project, user)
    return project


@router.get("/{project_id}/slides", response_model=list[CoursewareSlideResponse])
async def get_courseware_slides(
    project_id: str,
    db: AsyncSession = Depends(get_db),
    user_or_visitor=Depends(get_visitor_or_user),
):
    project = await get_project(db, project_id)
    user, _ = user_or_visitor
    _check_ownership(project, user)
    return await get_slides(db, project_id)


@router.patch("/{project_id}/slides/{slide_index}", response_model=CoursewareSlideResponse)
async def patch_slide(
    project_id: str, slide_index: int, data: SlideUpdate,
    db: AsyncSession = Depends(get_db), user=Depends(get_current_user),
):
    project = await get_project(db, project_id)
    _check_ownership_write(project, user)
    slide = await update_slide(
        db, project_id, slide_index, data.model_dump(exclude_unset=True),
    )
    if not slide:
        raise HTTPException(status_code=404, detail="Slide not found")
    return slide


@router.patch("/{project_id}/settings")
async def patch_bulk_settings(
    project_id: str, data: BulkSettingsUpdate,
    db: AsyncSession = Depends(get_db), user=Depends(get_current_user),
):
    project = await get_project(db, project_id)
    _check_ownership_write(project, user)
    await apply_bulk_settings(db, project_id, data.model_dump(exclude_none=True))
    return {"status": "ok"}


@router.post("/{project_id}/synthesize", response_model=SynthesizeResponse)
async def synthesize_courseware(
    project_id: str,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    project = await get_project(db, project_id)
    _check_ownership_write(project, user)
    # 只允许从 ready/failed 发起（P1-8）：synthesizing 状态下再次提交会叠加
    # 多个 Celery 任务并发处理同一项目——重复消耗云 API 费用 + slide 状态竞写。
    if project.status not in ("ready", "failed"):
        raise HTTPException(
            status_code=409,
            detail=f"课件状态为 {project.status}，无法开始合成",
        )

    # 配额预检（防滥用）：按「待合成页数」计（pending+failed，重试只跑这些页），
    # 而非 slides_count——重复提交不应该重复计费。异步任务的执行方在 worker，
    # 响应里看不到结果，若等合成完成再计数，异步路径将完全绕过配额；
    # 而课件才是烧钱主路径（1 个 100 页课件 ≈ LLM + TTS 共 200 次云调用）。
    # 检查必须在抢锁/改状态之前：超限请求不留下任何副作用。
    pending_count_result = await db.execute(
        select(func.count(CoursewareSlide.id)).where(
            CoursewareSlide.project_id == project.id,
            CoursewareSlide.status.in_(["pending", "failed"]),
        )
    )
    quota_cost = int(pending_count_result.scalar() or 0)
    await check_quota(user, QUOTA_KIND_COURSEWARE, cost=max(quota_cost, 1))

    # 服务端幂等锁（P1-8）：前端防抖不是信任边界。状态检查与提交之间存在
    # 并发窗口，双击/重放的两个请求都会读到 ready——用 Redis SET NX 抢锁，
    # 抢不到即 409。锁由 worker 在 _finalize_project 释放，TTL 3600 兜底
    # （worker 崩溃后锁自然过期，不会永久卡死重试通道）。
    from app.utils.redis_client import get_redis

    redis = await get_redis()
    lock_key = f"courseware:lock:{project.id}"
    got_lock = await redis.set(lock_key, "1", nx=True, ex=3600)
    if not got_lock:
        raise HTTPException(status_code=409, detail="合成任务正在进行中，请勿重复提交")

    previous_status = project.status
    project.status = "synthesizing"
    await db.commit()  # Commit so the Celery task's own session sees the new status

    await consume_quota(user.id, QUOTA_KIND_COURSEWARE, cost=max(quota_cost, 1))

    # 签发一次性 SSE 进度 ticket：存入安全 Redis 库，绑定 user+project，
    # TTL 600s。SSE 端点凭票访问，不再在 URL 中暴露 JWT（问题 12）。
    import uuid as ticket_uuid
    from app.utils.redis_client import get_security_redis

    progress_ticket = ticket_uuid.uuid4().hex
    sec_redis = await get_security_redis()
    await sec_redis.setex(
        f"sse:ticket:{progress_ticket}",
        600,
        f"{user.id}:{project.id}",
    )

    # Submit to Celery instead of synthesizing synchronously in the request
    from app.tasks.courseware_tasks import synthesize_courseware_task
    try:
        synthesize_courseware_task.delay(str(project.id))
    except Exception as e:
        # Task submission failed (e.g. broker down) — roll the status back
        # 只记录日志，不把内部异常原文返回客户端（避免泄露内部路径/依赖信息）
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Synthesis task submission failed for {project_id}: {e}")
        # 清理已签发但不会使用的 ticket、幂等锁与配额预扣（云 API 未被调用）
        await sec_redis.delete(f"sse:ticket:{progress_ticket}")
        await redis.delete(lock_key)
        await refund_quota(user.id, QUOTA_KIND_COURSEWARE, cost=max(quota_cost, 1))
        result = await db.execute(
            select(CoursewareProject).where(CoursewareProject.id == uuid_mod.UUID(project_id))
        )
        project = result.scalar_one_or_none()
        if project:
            project.status = previous_status
            await db.commit()
        raise HTTPException(status_code=500, detail="合成任务提交失败，请稍后重试")

    return SynthesizeResponse(
        project_id=str(project.id),
        status="synthesizing",
        message="合成任务已提交，请通过进度接口查看",
        progress_ticket=progress_ticket,
    )


@router.get("/{project_id}/progress")
async def get_progress(
    project_id: str,
    ticket: str = Query(..., description="合成时签发的一次性进度 ticket"),
    db: AsyncSession = Depends(get_db),
):
    """SSE 进度流：凭 synthesize 时签发的一次性 ticket 访问。

    旧实现把 JWT 放在 query 参数中，会进入 nginx access log、浏览器历史
    与 Referer，属于凭据泄露面。ticket 是项目级一次性凭据，TTL 600s，
    即使泄露也只能查看该项目的合成进度。
    """
    from app.utils.redis_client import get_security_redis

    sec_redis = await get_security_redis()
    ticket_val = await sec_redis.get(f"sse:ticket:{ticket}")
    if not ticket_val:
        raise HTTPException(status_code=401, detail="进度 ticket 无效或已过期")

    try:
        ticket_user_id, ticket_project_id = ticket_val.split(":", 1)
    except ValueError:
        raise HTTPException(status_code=401, detail="进度 ticket 无效")

    # ticket 绑定的项目必须与 URL 中的 project_id 一致
    if ticket_project_id != project_id:
        raise HTTPException(status_code=403, detail="ticket 与项目不匹配")

    project = await get_project(db, project_id)
    # 公共预设（user_id IS NULL）允许所有人读；私有项目需 ticket 签发者拥有
    if project is not None and project.user_id is not None:
        if str(project.user_id) != ticket_user_id:
            raise HTTPException(status_code=403, detail="无权访问该项目")

    from app.utils.redis_client import get_redis
    import json

    channel = f"courseware:progress:{project_id}"

    async def event_stream():
        redis = await get_redis()
        # 先读一次当前进度（可能任务已推进、消息已发出），避免订阅者错过
        # 订阅建立之前已 PUBLISH 的中间进度。
        current = await redis.get(channel)
        if current:
            data = json.loads(current)
            yield f"data: {json.dumps(data)}\n\n"
            if data.get("status") in ("completed", "failed"):
                return

        # 订阅进度 channel：worker 每完成一页 PUBLISH 一次，这里转发为 SSE。
        # 相比旧实现的 1s 轮询，延迟降到接近实时，且 Redis QPS 从「每订阅者
        # 每秒 1 次」降到「每页 1 次」。
        pubsub = redis.pubsub()
        await pubsub.subscribe(channel)
        try:
            async for message in pubsub.listen():
                if message.get("type") != "message":
                    continue
                data = json.loads(message["data"])
                yield f"data: {json.dumps(data)}\n\n"
                if data.get("status") in ("completed", "failed"):
                    break
        finally:
            await pubsub.unsubscribe(channel)
            await pubsub.aclose()

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.get("/{project_id}/download")
async def download_courseware(
    project_id: str,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    project = await get_project(db, project_id)
    _check_ownership(project, user)
    if project.status != "completed":
        raise HTTPException(status_code=409, detail="课件合成尚未完成")

    slides = await get_slides(db, project_id)
    zip_bytes = await build_zip(project, slides)

    # Sanitize filename and RFC 5987 encode for Content-Disposition
    import re
    from urllib.parse import quote
    safe_title = re.sub(r'[^\w\s\-.]', '_', project.title)
    encoded_filename = quote(f"{safe_title}.zip")
    return StreamingResponse(
        io.BytesIO(zip_bytes),
        media_type="application/zip",
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{encoded_filename}",
        },
    )


@router.delete("/{project_id}", status_code=204)
async def delete_courseware(
    project_id: str,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    project = await get_project(db, project_id)
    _check_ownership_write(project, user)

    slides = await get_slides(db, project_id)

    # 先清理指向这些音频的 TTS 缓存（P2-6）：否则同参数文本再次合成会
    # 命中缓存返回已删除路径 → /media 404。文件删除失败也要清缓存。
    from app.utils.redis_client import get_redis

    redis = await get_redis()
    for slide in slides:
        if slide.audio_path:
            await _purge_tts_cache(redis, slide.audio_path)
            try:
                await storage.delete(slide.audio_path)
            except Exception:
                pass
    if project.original_pptx_path:
        try:
            await storage.delete(project.original_pptx_path)
        except Exception:
            pass

    await db.delete(project)
    await db.flush()
