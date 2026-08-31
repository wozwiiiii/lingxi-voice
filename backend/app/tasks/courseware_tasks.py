"""Celery tasks for courseware batch synthesis with Semaphore concurrency.

并发模型（修复共享 Session 问题）：
- 每个 slide 在**独立 AsyncSession** 中合成并立即 commit。
  AsyncSession 不支持并发使用，旧实现把同一个 session 传给 gather
  中的多个协程，会触发 "another operation is in progress" 或状态错乱。
- 进度统计（_push_progress）读取的是已提交数据：旧实现主 session
  直到最后才 commit，READ COMMITTED 下进度查询永远读到 0（SSE 进度恒 0）。
  现在每页 commit 后即可被进度查询看到。
"""

import asyncio
import json
import logging
import os
import uuid

from celery import shared_task
from sqlalchemy import func, select

from app.database import AsyncSessionLocal, engine
from app.models.courseware import CoursewareProject, CoursewareSlide
from app.models.task import SynthesisTask
from app.preprocess.llm_pipeline import llm_pipeline
from app.providers.base import SynthesisParams
from app.providers.provider_chain import (
    get_active_provider_async,
    get_circuit_for_provider,
)
from app.utils.audio import probe_duration_ms
from app.utils.redis_client import get_redis
from app.utils.storage import storage

logger = logging.getLogger(__name__)

CONCURRENCY = int(os.getenv("COURSEWARE_SYNTHESIS_CONCURRENCY", "3"))


@shared_task(bind=True, max_retries=1, acks_late=True)
def synthesize_courseware_task(self, project_id: str):
    return asyncio.run(_run_with_cleanup(_synthesize(project_id)))


async def _run_with_cleanup(coro):
    """任务结束时归还绑定本事件循环的底层连接（P1-7）。

    Celery prefork 每个任务都跑在 asyncio.run() 创建的新事件循环里，而
    engine / redis_client 是模块级单例——连接池中的 asyncpg / redis 连接
    绑定创建时的循环。若不在任务末尾释放，下一个任务在另一个循环上复用
    旧连接会报 "attached to a different loop" / "Event loop is closed"。
    在本循环内 dispose / aclose 后，池在下一个任务的循环上自动重建连接。
    该包装只被 Celery worker 进程执行，API 进程的长生命周期池不受影响。
    """
    from app.utils.redis_client import redis_client as rc

    try:
        return await coro
    finally:
        for name, closer in (("engine", engine.dispose), ("redis", rc.aclose)):
            try:
                await closer()
            except Exception:
                logger.warning(f"{name} cleanup after task failed", exc_info=True)


async def _synthesize(project_id: str):
    # 1. 读取待合成 slide 的 id（短事务，随后关闭）
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(CoursewareSlide.id, CoursewareSlide.slide_index)
            .where(
                CoursewareSlide.project_id == uuid.UUID(project_id),
                CoursewareSlide.status.in_(["pending", "failed"]),
            )
            .order_by(CoursewareSlide.slide_index)
        )
        pending = [(row[0], row[1]) for row in result.all()]

    if not pending:
        await _finalize_project(project_id)
        return

    semaphore = asyncio.Semaphore(CONCURRENCY)

    async def process_one(slide_id: uuid.UUID) -> None:
        async with semaphore:
            # 每页独立 session + 立即提交：
            # ① 避免并发共享 AsyncSession；② 让进度查询能读到已完成状态
            async with AsyncSessionLocal() as slide_db:
                slide = await slide_db.get(CoursewareSlide, slide_id)
                if slide is None:
                    return
                try:
                    await _synthesize_slide(slide_db, slide)
                except Exception as e:
                    slide.status = "failed"
                    logger.error(f"Slide synthesis failed: {e}")
                await slide_db.commit()
            await _push_progress(project_id)

    await asyncio.gather(*[process_one(sid) for sid, _ in pending])

    # 2. 汇总最终状态
    await _finalize_project(project_id)


async def _finalize_project(project_id: str):
    """统计全部 slide 状态，更新 project 状态，推送最终进度。"""
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(CoursewareSlide.status).where(
                CoursewareSlide.project_id == uuid.UUID(project_id)
            )
        )
        statuses = [row[0] for row in result.all()]
        total = len(statuses)
        completed = statuses.count("completed")
        failed_count = statuses.count("failed")
        final_status = "failed" if total > 0 and failed_count == total else "completed"

        proj_result = await db.execute(
            select(CoursewareProject).where(
                CoursewareProject.id == uuid.UUID(project_id)
            )
        )
        project = proj_result.scalar_one_or_none()
        if project:
            project.status = final_status
        await db.commit()

    # Push final progress to Redis so SSE clients can terminate
    redis = await get_redis()
    await redis.set(
        f"courseware:progress:{project_id}",
        json.dumps({"current": completed, "total": total, "status": final_status}),
        ex=7200,
    )
    # 释放 API 层签发的合成幂等锁（P1-8）：允许用户在完成后再次发起合成
    await redis.delete(f"courseware:lock:{project_id}")


async def _synthesize_slide(db, slide: CoursewareSlide):
    text = slide.edited_text or slide.original_text
    if not text:
        slide.status = "completed"
        return

    processed = await llm_pipeline.process(text)

    voice_id = slide.voice_id
    if not voice_id:
        result = await db.execute(
            select(CoursewareProject).where(CoursewareProject.id == slide.project_id)
        )
        project = result.scalar_one_or_none()
        voice_id = project.voice_id if project else None
    # Fallback: use first available preset voice
    if not voice_id:
        from app.models.voice import Voice
        result = await db.execute(
            select(Voice).where(Voice.is_public == True).limit(1)
        )
        fallback = result.scalar_one_or_none()
        if fallback:
            voice_id = fallback.id
    if not voice_id:
        raise ValueError(f"Slide {slide.slide_index}: no voice assigned")

    params = SynthesisParams(
        speed=slide.speed, emotion=slide.emotion,
        style=slide.style, instruction=slide.instruction,
    )

    provider = await get_active_provider_async()
    try:
        result = await provider.synthesize(processed, str(voice_id), params)
    except Exception:
        # 供应商异常 → 记录失败供熔断器判定（与 tts_service 保持一致）
        circuit = get_circuit_for_provider(provider.name)
        if circuit:
            await circuit.record_failure()
        raise
    circuit = get_circuit_for_provider(provider.name)
    if circuit:
        await circuit.record_success()

    audio_path = await storage.save(result.audio_data, "audio", "mp3")

    # P2-1：与 tts_service 一致——探测落盘文件的真实时长，而非 provider
    # HTTP 往返耗时；探测失败回退 0（未知）。
    abs_path = await storage.get_path(audio_path)
    real_duration_ms = await asyncio.to_thread(probe_duration_ms, abs_path) or 0

    slide.llm_processed_text = processed
    slide.audio_path = audio_path
    slide.audio_duration_ms = real_duration_ms
    slide.status = "completed"

    task = SynthesisTask(
        user_id=None,
        voice_id=voice_id, type="tts", input_text=text,
        llm_processed_text=processed,
        params={"speed": slide.speed}, status="completed",
        output_audio_path=audio_path, output_format="mp3",
        provider_used=provider.name, duration_ms=real_duration_ms,
    )
    db.add(task)
    await db.flush()
    slide.synthesis_task_id = task.id


async def _push_progress(project_id: str):
    async with AsyncSessionLocal() as db:
        total_result = await db.execute(
            select(func.count(CoursewareSlide.id)).where(
                CoursewareSlide.project_id == uuid.UUID(project_id)
            )
        )
        total = total_result.scalar() or 0

        completed_result = await db.execute(
            select(func.count(CoursewareSlide.id)).where(
                CoursewareSlide.project_id == uuid.UUID(project_id),
                CoursewareSlide.status == "completed",
            )
        )
        completed = completed_result.scalar() or 0

    redis = await get_redis()
    await redis.set(
        f"courseware:progress:{project_id}",
        json.dumps({"current": completed, "total": total, "status": "synthesizing"}),
        ex=7200,
    )


@shared_task
def cleanup_orphan_courseware():
    """Celery Beat task: delete courseware projects abandoned for 7+ days."""
    return asyncio.run(_run_with_cleanup(_cleanup_orphans()))


async def _cleanup_orphans():
    from datetime import datetime, timedelta, timezone

    cutoff = datetime.now(timezone.utc) - timedelta(days=7)
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(CoursewareProject).where(
                CoursewareProject.status.in_(["pending", "parsing", "ready"]),
                CoursewareProject.created_at < cutoff,
            )
        )
        orphans = result.scalars().all()
        for project in orphans:
            # Delete associated storage
            if project.original_pptx_path:
                try:
                    await storage.delete(project.original_pptx_path)
                except Exception:
                    pass
            # Slides cascade-delete
            await db.delete(project)
        if orphans:
            await db.commit()
            logger.info(f"Cleaned up {len(orphans)} orphan courseware projects")
