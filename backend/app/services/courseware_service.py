"""Courseware CRUD + synthesis orchestration."""

import io
import json
import logging
import uuid
import zipfile

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.courseware import CoursewareProject, CoursewareSlide
from app.models.voice import Voice
from app.services.pptx_parser import parse_pptx
from app.utils.storage import storage

logger = logging.getLogger(__name__)


async def create_from_upload(
    db: AsyncSession,
    user_id: str,
    filepath: str,
    original_filename: str,
    description: str | None = None,
) -> CoursewareProject:
    # python-pptx 解析是同步 CPU/IO 混合操作，20MB 课件足以卡住事件循环
    # 数百毫秒——卸载到线程池（与 build_zip 的 storage.read 同一策略）
    import asyncio

    result = await asyncio.to_thread(parse_pptx, filepath, original_filename)

    # Auto-assign first available preset voice as default
    default_voice_id = None
    voice_result = await db.execute(
        select(Voice).where(Voice.is_public == True).limit(1)
    )
    voice = voice_result.scalar_one_or_none()
    if voice:
        default_voice_id = voice.id

    project = CoursewareProject(
        user_id=uuid.UUID(user_id),
        title=result.title,
        description=description,
        original_pptx_path=filepath,
        slides_count=result.slides_count,
        status="ready",
        voice_id=default_voice_id,
    )
    db.add(project)
    await db.flush()

    for slide_data in result.slides:
        slide = CoursewareSlide(
            project_id=project.id,
            slide_index=slide_data.index,
            original_text=slide_data.text,
        )
        db.add(slide)

    await db.flush()
    await db.refresh(project)
    return project


async def get_project(db: AsyncSession, project_id: str) -> CoursewareProject | None:
    result = await db.execute(
        select(CoursewareProject).where(CoursewareProject.id == uuid.UUID(project_id))
    )
    return result.scalar_one_or_none()


async def get_slides(db: AsyncSession, project_id: str) -> list[CoursewareSlide]:
    result = await db.execute(
        select(CoursewareSlide)
        .where(CoursewareSlide.project_id == uuid.UUID(project_id))
        .order_by(CoursewareSlide.slide_index)
    )
    return list(result.scalars().all())


async def update_slide(
    db: AsyncSession, project_id: str, slide_index: int, data: dict,
) -> CoursewareSlide | None:
    result = await db.execute(
        select(CoursewareSlide).where(
            CoursewareSlide.project_id == uuid.UUID(project_id),
            CoursewareSlide.slide_index == slide_index,
        )
    )
    slide = result.scalar_one_or_none()
    if not slide:
        return None
    # Apply every key present in the payload, including explicit nulls, so
    # fields (emotion/style/voice_id/...) can be cleared back to None.
    # "Field absent" vs "field explicitly null" is distinguished upstream via
    # exclude_unset=True (see patch_slide).
    for key, value in data.items():
        if hasattr(slide, key):
            setattr(slide, key, value)
    await db.flush()
    await db.refresh(slide)
    return slide


async def apply_bulk_settings(
    db: AsyncSession, project_id: str, data: dict,
) -> None:
    """Apply settings to all slides that don't have individual overrides."""
    filtered = {k: v for k, v in data.items() if v is not None}
    if not filtered:
        return

    stmt = (
        update(CoursewareSlide)
        .where(
            CoursewareSlide.project_id == uuid.UUID(project_id),
            CoursewareSlide.voice_id.is_(None),
        )
        .values(**filtered)
    )
    await db.execute(stmt)

    if data.get("voice_id"):
        await db.execute(
            update(CoursewareProject)
            .where(CoursewareProject.id == uuid.UUID(project_id))
            .values(voice_id=uuid.UUID(data["voice_id"]))
        )
    await db.flush()


async def build_zip(
    project: CoursewareProject, slides: list[CoursewareSlide],
) -> bytes:
    """Build ZIP in memory: manifest.json + per-slide MP3s + original PPTX."""
    manifest = {
        "courseware_id": str(project.id),
        "title": project.title,
        "slides_count": project.slides_count,
        "created_at": project.created_at.isoformat() if project.created_at else "",
        "slides": [],
    }

    # 先用 asyncio.to_thread 并行读取所有音频/课件文件，避免在 ZIP 写入循环中
    # 同步阻塞事件循环，也避免 open() 未用 with 导致的文件句柄泄漏
    import asyncio

    async def _read(path: str) -> bytes:
        return await storage.read(path)

    audio_tasks = []
    audio_indices = []
    for slide in slides:
        if slide.audio_path and slide.status == "completed":
            audio_tasks.append(_read(slide.audio_path))
            audio_indices.append(slide.slide_index)

    pptx_task = None
    if project.original_pptx_path:
        pptx_task = _read(project.original_pptx_path)

    audio_results = await asyncio.gather(*audio_tasks)
    audio_map = dict(zip(audio_indices, audio_results))
    pptx_data = await pptx_task if pptx_task else None

    zf_buffer = io.BytesIO()
    with zipfile.ZipFile(zf_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for slide in slides:
            if slide.audio_path and slide.status == "completed":
                audio_data = audio_map[slide.slide_index]
                audio_name = f"audio/slide_{slide.slide_index:02d}.mp3"
                zf.writestr(audio_name, audio_data)
                manifest["slides"].append({
                    "index": slide.slide_index,
                    "original_text": slide.original_text,
                    "llm_processed_text": slide.llm_processed_text,
                    "audio_file": audio_name,
                    "audio_duration_ms": slide.audio_duration_ms,
                })

        zf.writestr(
            "manifest.json",
            json.dumps(manifest, ensure_ascii=False, indent=2),
        )

        if pptx_data is not None:
            zf.writestr("original.pptx", pptx_data)

    return zf_buffer.getvalue()


async def seed_courseware_presets(db: AsyncSession) -> None:
    """Seed 5 preset courseware projects. Idempotent."""
    presets = [
        {"title": "古诗词鉴赏", "description": "李白《静夜思》朗诵与赏析"},
        {"title": "English Lesson", "description": "Basic English conversation practice"},
        {"title": "物理实验课", "description": "牛顿第二定律实验讲解"},
        {"title": "历史故事会", "description": "三国演义·草船借箭"},
        {"title": "企业培训模板", "description": "新员工入职培训标准课件"},
    ]
    for preset in presets:
        existing = await db.execute(
            select(CoursewareProject).where(
                CoursewareProject.title == preset["title"],
                CoursewareProject.user_id.is_(None),
            )
        )
        if existing.scalar_one_or_none():
            continue
        project = CoursewareProject(
            title=preset["title"],
            description=preset["description"],
            slides_count=0,
            status="completed",
        )
        db.add(project)
    await db.flush()
