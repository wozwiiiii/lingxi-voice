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
import time
import uuid
from pathlib import Path

from celery import shared_task
from sqlalchemy import func, select

from app.config import settings
from app.database import AsyncSessionLocal, engine
from app.models.courseware import CoursewareProject, CoursewareSlide
from app.models.task import SynthesisTask
from app.preprocess.llm_pipeline import llm_pipeline
from app.providers.base import SynthesisParams
from app.providers.errors import ContentError
from app.providers.provider_chain import (
    get_active_provider_async,
    get_circuit_for_provider,
)
from app.utils.audio import probe_duration_ms
from app.utils.error_codes import SlideErrorCode, classify_exc
from app.utils.metrics import COURSEWARE_SLIDE_TOTAL
from app.utils.redis_client import get_redis
from app.utils.storage import storage

logger = logging.getLogger(__name__)


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


def _mark_failed(slide: CoursewareSlide, code: SlideErrorCode, message: str) -> None:
    """标记页失败并写入错误分类。

    error_code 让前端能区分「重试有用」（provider_unavailable/timeout）和
    「重试没用」（content_error）；message 截断到 500 字符，防止上游异常
    的完整堆栈撑爆数据库行。
    """
    slide.status = "failed"
    slide.error_code = code.value
    slide.error_message = message[:500]


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

    semaphore = asyncio.Semaphore(settings.COURSEWARE_SYNTHESIS_CONCURRENCY)
    # 软墙 deadline：整个任务的时长上限。刻意不用 Celery 的 time_limit——
    # hard kill 会绕过 finally 导致状态不收敛，且 acks_late=True 时 hard kill
    # 不计入 max_retries，任务会被无限重投、反复烧云 API 费用。
    deadline = time.monotonic() + settings.COURSEWARE_TASK_TOTAL_TIMEOUT_S

    async def process_one(slide_id: uuid.UUID) -> None:
        async with semaphore:
            # 每页独立 session + 立即提交：
            # ① 避免并发共享 AsyncSession；② 让进度查询能读到已完成状态
            async with AsyncSessionLocal() as slide_db:
                slide = await slide_db.get(CoursewareSlide, slide_id)
                if slide is None:
                    return
                if time.monotonic() > deadline:
                    # 总时长超限：必须标记失败而不是静默跳过。留 pending 会让
                    # 项目卡在 synthesizing，而重试接口只放行 ready/failed。
                    _mark_failed(
                        slide, SlideErrorCode.TIMEOUT, "任务总时长超限，本页未执行"
                    )
                    await slide_db.commit()
                    return
                try:
                    await asyncio.wait_for(
                        _synthesize_slide(slide_db, slide),
                        timeout=settings.COURSEWARE_SLIDE_TIMEOUT_S,
                    )
                except asyncio.CancelledError:
                    # 取消不是失败：不改写 slide，留 pending 供下次重试。
                    # 必须原样上抛——CancelledError 是 BaseException，下面
                    # 的 except Exception 抓不到它，此处显式声明意图。
                    raise
                except asyncio.TimeoutError:
                    # 不 rollback：rollback 会让 slide 进入 expired 态，此后
                    # 设值会在同步上下文触发 greenlet 错误。这里没有需要
                    # 丢弃的部分修改——失败即整页失败，直接覆盖状态即可。
                    _mark_failed(slide, SlideErrorCode.TIMEOUT, "单页合成超时")
                    COURSEWARE_SLIDE_TOTAL.labels("timeout").inc()
                    logger.error("Slide %s synthesis timed out", slide.slide_index)
                except Exception as e:
                    _mark_failed(slide, classify_exc(e), str(e))
                    COURSEWARE_SLIDE_TOTAL.labels("failed").inc()
                    logger.error(f"Slide synthesis failed: {e}")
                else:
                    COURSEWARE_SLIDE_TOTAL.labels("completed").inc()
                await slide_db.commit()
            # 进度推送是旁路，失败绝不能冒泡：原实现把它放在 try 之外，
            # Redis 一抖动就会跳过 _finalize_project，让项目永久停在
            # synthesizing、锁挂满 3600s。
            await _push_progress_safe(project_id)

    try:
        results = await asyncio.gather(
            *[process_one(sid) for sid, _ in pending], return_exceptions=True
        )
        for r in results:
            if isinstance(r, BaseException):
                logger.error("Slide coroutine raised %s: %s", type(r).__name__, r)
    finally:
        # 2. 汇总最终状态。
        # finally 是收敛的最后一道防线：gather 的 return_exceptions 只兜住
        # 单页抛出的异常，超时、内存错误等逃出 gather 的路径靠这里保证
        # 项目状态与幂等锁一定被处理。
        await _finalize_project(project_id)


async def _finalize_project(project_id: str):
    """统计全部 slide 状态，更新 project 状态，推送最终进度、释放幂等锁。

    整个函数对异常免疫：收敛逻辑自身失败也必须释放幂等锁，否则项目会被
    锁到 3600s TTL 期满，期间状态停在 synthesizing，重试接口（只放行
    ready/failed）一律拒绝——用户彻底失去自救手段。
    """
    completed = total = 0
    final_status = "failed"
    try:
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(CoursewareSlide.status, CoursewareSlide.error_code).where(
                    CoursewareSlide.project_id == uuid.UUID(project_id)
                )
            )
            rows = result.all()
            statuses = [row[0] for row in rows]
            slide_error_codes = [row[1] for row in rows if row[1]]
            total = len(statuses)
            completed = statuses.count("completed")
            failed_count = statuses.count("failed")
            remaining = total - completed - failed_count
            # 沿用原有语义：全部页完成才算 completed，部分失败仍算 completed
            # ——下载接口只放行 completed，改判定会让 29/30 页成功的课件无法
            # 下载（见 P0 方案 F2）。
            # 唯一新增：仍有未处理页（任务被取消或中断）时判 failed，否则项目
            # 既不能重试、又会产出一个缺页的 zip。
            if total > 0 and failed_count == total:
                final_status = "failed"
            elif remaining > 0:
                final_status = "failed"
            else:
                final_status = "completed"

            proj_result = await db.execute(
                select(CoursewareProject).where(
                    CoursewareProject.id == uuid.UUID(project_id)
                )
            )
            project = proj_result.scalar_one_or_none()
            if project:
                project.status = final_status
                if final_status == "completed":
                    # 成功时清掉历史错误，避免上次失败的痕迹残留到本次
                    project.error_code = None
                    project.error_message = None
                else:
                    # 聚合规则：只要存在一页「可重试」错误，项目就标记为可重试
                    # ——用户关心的是"再点一次有没有用"，不是错误的技术细节。
                    retryable = {
                        SlideErrorCode.PROVIDER_UNAVAILABLE.value,
                        SlideErrorCode.TIMEOUT.value,
                    }
                    if any(c in retryable for c in slide_error_codes):
                        project.error_code = SlideErrorCode.PROVIDER_UNAVAILABLE.value
                    elif slide_error_codes:
                        project.error_code = SlideErrorCode.CONTENT_ERROR.value
                    else:
                        project.error_code = None
                    project.error_message = f"{failed_count}/{total} 页合成失败"
            await db.commit()

        # Push final progress to Redis so SSE clients can terminate
        await _emit_progress(
            project_id,
            {"current": completed, "total": total, "status": final_status},
        )
    except Exception:
        logger.exception("finalize project %s failed", project_id)
    finally:
        # 释放 API 层签发的合成幂等锁（P1-8）：允许用户在完成后再次发起合成
        try:
            release = await get_redis()
            await release.delete(f"courseware:lock:{project_id}")
        except Exception:
            logger.warning(
                "release courseware lock failed for %s", project_id, exc_info=True
            )


async def _synthesize_slide(db, slide: CoursewareSlide):
    text = slide.edited_text or slide.original_text
    if not text:
        slide.status = "completed"
        return

    processed = await llm_pipeline.process(text)

    # 项目一次查出：voice_id 兜底与 user_id 透传都需要，避免查两次
    proj_result = await db.execute(
        select(CoursewareProject).where(CoursewareProject.id == slide.project_id)
    )
    project = proj_result.scalar_one_or_none()

    voice_id = slide.voice_id or (project.voice_id if project else None)
    # Fallback: use first available preset voice
    if not voice_id:
        from app.models.voice import Voice
        result = await db.execute(
            select(Voice).where(Voice.is_public.is_(True)).limit(1)
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
    except Exception as e:
        # 熔断计数按语义分类（与 tts_service 的 F1 修复保持一致）：
        # 供应商不可用/超时才计入，ContentError 是用户内容的锅——
        # 若也计入，30 页里 5 页文本不合法就能把熔断打开，其他用户陪葬。
        if not isinstance(e, ContentError):
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
        # 透传项目归属用户（原硬编码 None）：让 synthesis_tasks 的用量统计
        # 和按用户聚合的运营查询能覆盖课件链路。预设课件 user_id 为 NULL，
        # 保持为 None 是正确语义。
        user_id=project.user_id if project else None,
        voice_id=voice_id, type="tts", input_text=text,
        llm_processed_text=processed,
        params={"speed": slide.speed}, status="completed",
        output_audio_path=audio_path, output_format="mp3",
        provider_used=provider.name, duration_ms=real_duration_ms,
    )
    db.add(task)
    await db.flush()
    slide.synthesis_task_id = task.id


async def _emit_progress(project_id: str, payload: dict) -> None:
    """发布进度：SET（供订阅者先读当前值）+ PUBLISH（推送给在订阅者）。

    channel 与 key 同名（courseware:progress:{project_id}）——SET 让它可被
    「先读后订阅」读取，PUBLISH 让订阅者近乎实时收到。两者缺一不可：
    只 PUBLISH 会让订阅建立前已完成的页丢失；只 SET 则退化成轮询。
    """
    channel = f"courseware:progress:{project_id}"
    body = json.dumps(payload)
    redis = await get_redis()
    await redis.set(channel, body, ex=7200)
    await redis.publish(channel, body)


async def _push_progress(project_id: str) -> None:
    async with AsyncSessionLocal() as db:
        # 单次 group_by 取代原先两次独立 COUNT：两次查询之间存在窗口，
        # 并发页提交时 total 与 completed 可能来自不同快照，导致进度回退。
        rows = (
            await db.execute(
                select(CoursewareSlide.status, func.count(CoursewareSlide.id))
                .where(CoursewareSlide.project_id == uuid.UUID(project_id))
                .group_by(CoursewareSlide.status)
            )
        ).all()
        counts = {status: n for status, n in rows}
        total = sum(counts.values())
        completed = counts.get("completed", 0)

    await _emit_progress(
        project_id,
        {"current": completed, "total": total, "status": "synthesizing"},
    )


async def _push_progress_safe(project_id: str) -> None:
    """进度推送的旁路包装：任何异常都只记日志，绝不向上传播。

    进度是纯展示数据，丢一次最多让前端进度条停一下；但若让它冒泡，
    会连带跳过外层 finally 之外的收敛逻辑，把「卡一下」变成「永久卡死」。
    """
    try:
        await _push_progress(project_id)
    except Exception:
        logger.warning("push progress failed for project %s", project_id, exc_info=True)


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


@shared_task
def cleanup_orphan_audio():
    """Celery Beat task: 清理 media/audio/ 下无引用且超 30 天的音频文件。

    音频的引用来源有三处，必须同时比对：
    1. SynthesisTask.output_audio_path（单次 TTS 与课件页合成都会写）
    2. CoursewareSlide.audio_path（课件页）
    3. Redis 缓存反向索引 tts:refs:{audio_path}（TTS 结果缓存，TTL 1 天）
    只删「无任何 DB 引用、且 mtime 超过 30 天」的文件，避免误删仍在用的音频。
    """
    return asyncio.run(_run_with_cleanup(_cleanup_audio()))


async def _cleanup_audio():
    from datetime import datetime, timedelta, timezone

    cutoff = datetime.now(timezone.utc) - timedelta(days=30)

    # 收集所有被引用的音频相对路径（DB）
    referenced: set[str] = set()
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(SynthesisTask.output_audio_path).where(
                SynthesisTask.output_audio_path.is_not(None)
            )
        )
        for row in result.all():
            if row[0]:
                referenced.add(row[0])
        result = await db.execute(
            select(CoursewareSlide.audio_path).where(
                CoursewareSlide.audio_path.is_not(None)
            )
        )
        for row in result.all():
            if row[0]:
                referenced.add(row[0])

    # 收集 Redis 缓存引用（tts:refs:{path} 反向索引）
    redis = await get_redis()
    try:
        ref_keys = await redis.keys("tts:refs:*")
        for k in ref_keys:
            # key 形如 tts:refs:audio/xxx.mp3
            referenced.add(k.removeprefix("tts:refs:"))
    except Exception:
        logger.warning("audio cleanup: failed to read redis refs, skipping cache refs")

    # 枚举 audio 目录，删无引用且超龄的文件
    audio_files = await storage.list("audio")
    deleted = 0
    for rel_path in audio_files:
        if rel_path in referenced:
            continue
        try:
            abs_path = Path(await storage.get_path(rel_path))
            mtime = datetime.fromtimestamp(abs_path.stat().st_mtime, tz=timezone.utc)
            if mtime < cutoff:
                await storage.delete(rel_path)
                deleted += 1
        except Exception:
            logger.warning(f"audio cleanup: skip {rel_path}", exc_info=True)

    if deleted:
        logger.info(f"Cleaned up {deleted} orphan audio files")


@shared_task
def converge_stuck_projects():
    """Celery Beat task: 收敛卡死在 synthesizing 状态的项目。

    正常路径下 _finalize_project 会把项目收敛到 completed/failed 并释放幂等锁，
    但 worker 进程崩溃 / 被 kill 时该收尾不会执行——项目永久停在 synthesizing、
    锁挂满 3600s、前端 409 无法重试。本任务扫描超过阈值的 synthesizing 项目，
    标记为 failed 并释放锁，让状态可收敛。
    """
    return asyncio.run(_run_with_cleanup(_converge_stuck()))


async def _converge_stuck():
    from datetime import datetime, timedelta, timezone

    # 阈值 2 小时：远超单页 120s + 总时长软墙 1800s 的正常上限，正常任务
    # 早已结束；只有 worker 崩溃留下的僵死状态才会超过这个阈值。
    cutoff = datetime.now(timezone.utc) - timedelta(hours=2)
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(CoursewareProject).where(
                CoursewareProject.status == "synthesizing",
                CoursewareProject.updated_at < cutoff,
            )
        )
        stuck = result.scalars().all()
        for project in stuck:
            project.status = "failed"
            project.error_code = SlideErrorCode.TIMEOUT.value
            project.error_message = "合成任务中断，已自动标记失败"
        if stuck:
            await db.commit()

    redis = await get_redis()
    for project in stuck:
        try:
            await redis.delete(f"courseware:lock:{project.id}")
        except Exception:
            logger.warning(f"release lock failed for {project.id}", exc_info=True)
        logger.info(f"Converged stuck project {project.id} to failed")

    if stuck:
        logger.info(f"Converged {len(stuck)} stuck projects")
