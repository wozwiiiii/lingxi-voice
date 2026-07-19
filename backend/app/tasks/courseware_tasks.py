"""Celery tasks for courseware batch synthesis with Semaphore concurrency."""

import asyncio
import json
import logging
import os
import uuid

from celery import shared_task
from sqlalchemy import select, func

from app.config import settings
from app.database import AsyncSessionLocal
from app.models.courseware import CoursewareProject, CoursewareSlide
from app.models.task import SynthesisTask
from app.preprocess.llm_pipeline import llm_pipeline
from app.providers.base import SynthesisParams
from app.providers.provider_chain import get_active_provider_async
from app.utils.redis_client import get_redis
from app.utils.storage import storage

logger = logging.getLogger(__name__)

CONCURRENCY = int(os.getenv("COURSEWARE_SYNTHESIS_CONCURRENCY", "3"))


@shared_task(bind=True, max_retries=1, acks_late=True)
def synthesize_courseware_task(self, project_id: str):
    return asyncio.run(_synthesize(project_id))


async def _synthesize(project_id: str):
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(CoursewareSlide)
            .where(
                CoursewareSlide.project_id == uuid.UUID(project_id),
                CoursewareSlide.status.in_(["pending", "failed"]),
            )
            .order_by(CoursewareSlide.slide_index)
        )
        slides = list(result.scalars().all())

        if not slides:
            await _update_project_status(db, project_id, "completed")
            return

        semaphore = asyncio.Semaphore(CONCURRENCY)

        async def process_one(slide: CoursewareSlide) -> None:
            async with semaphore:
                try:
                    await _synthesize_slide(db, slide)
                except Exception as e:
                    slide.status = "failed"
                    logger.error(f"Slide {slide.slide_index} failed: {e}")
                await db.flush()
                await _push_progress(project_id)

        await asyncio.gather(*[process_one(s) for s in slides], return_exceptions=True)

        # Re-check all slides
        result = await db.execute(
            select(CoursewareSlide).where(
                CoursewareSlide.project_id == uuid.UUID(project_id)
            )
        )
        all_slides = result.scalars().all()
        failed_count = sum(1 for s in all_slides if s.status == "failed")

        if failed_count == 0:
            await _update_project_status(db, project_id, "completed")
        elif failed_count == len(all_slides):
            await _update_project_status(db, project_id, "failed")
        else:
            await _update_project_status(db, project_id, "completed")


async def _synthesize_slide(db, slide: CoursewareSlide):
    text = slide.edited_text or slide.original_text
    if not text:
        slide.status = "completed"
        return

    processed = await llm_pipeline.process(text)

    voice_id = slide.voice_id
    if not voice_id:
        result = await db.execute(
            select(CoursewareProject).where(
                CoursewareProject.id == slide.project_id
            )
        )
        project = result.scalar_one_or_none()
        voice_id = project.voice_id if project else None
    if not voice_id:
        raise ValueError(f"Slide {slide.slide_index}: no voice assigned")

    params = SynthesisParams(
        speed=slide.speed, emotion=slide.emotion,
        style=slide.style, instruction=slide.instruction,
    )

    provider = await get_active_provider_async()
    result = await provider.synthesize(processed, str(voice_id), params)

    audio_path = await storage.save(result.audio_data, "audio", "mp3")

    slide.llm_processed_text = processed
    slide.audio_path = audio_path
    slide.audio_duration_ms = result.duration_ms
    slide.status = "completed"

    task = SynthesisTask(
        user_id=None,
        voice_id=voice_id, type="tts", input_text=text,
        llm_processed_text=processed,
        params={"speed": slide.speed}, status="completed",
        output_audio_path=audio_path, output_format="mp3",
        provider_used=provider.name, duration_ms=result.duration_ms,
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


async def _update_project_status(db, project_id: str, status: str):
    result = await db.execute(
        select(CoursewareProject).where(
            CoursewareProject.id == uuid.UUID(project_id)
        )
    )
    project = result.scalar_one_or_none()
    if project:
        project.status = status
        await db.flush()


@shared_task
def cleanup_orphan_courseware():
    """Celery Beat task: delete courseware projects abandoned for 7+ days."""
    return asyncio.run(_cleanup_orphans())


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
            await db.flush()
            logger.info(f"Cleaned up {len(orphans)} orphan courseware projects")
