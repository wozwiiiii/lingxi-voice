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
        select(Voice).where(Voice.is_public.is_(True)).limit(1)
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
    """Seed 12 preset courseware projects. Idempotent.

    覆盖学科（语文/英语/数学/物理/历史/科学）× 学段（K12/高校/职场），
    每个预设带实际 slide 文本（original_text），让新用户打开即可预览、
    点击即合成，降低上手门槛。
    """
    presets = [
        {
            "title": "古诗词鉴赏",
            "description": "李白《静夜思》朗诵与赏析",
            "slides": [
                "静夜思。床前明月光，疑是地上霜。",
                "举头望明月，低头思故乡。",
                "诗人李白借明月寄托思乡之情。",
            ],
        },
        {
            "title": "English Lesson",
            "description": "Basic English conversation practice",
            "slides": [
                "Hello! How are you today?",
                "I am fine, thank you. And you?",
                "Let's practice English conversation together.",
            ],
        },
        {
            "title": "物理实验课",
            "description": "牛顿第二定律实验讲解",
            "slides": [
                "牛顿第二定律指出：物体的加速度与合外力成正比，与质量成反比。",
                "公式：F 等于 m 乘以 a。",
                "实验中用小车和砝码验证力与加速度的关系。",
            ],
        },
        {
            "title": "历史故事会",
            "description": "三国演义·草船借箭",
            "slides": [
                "草船借箭的故事发生在赤壁之战前夕。",
                "诸葛亮利用大雾天气，用草船向曹操借箭。",
                "这个故事展现了智谋胜过武力的道理。",
            ],
        },
        {
            "title": "企业培训模板",
            "description": "新员工入职培训标准课件",
            "slides": [
                "欢迎加入团队，今天我们来了解公司文化。",
                "公司的核心价值观是：客户第一，团队协作。",
                "接下来介绍公司的组织架构与部门职责。",
            ],
        },
        {
            "title": "数学启蒙",
            "description": "小学数学基础：加减乘除",
            "slides": [
                "今天学习加法：二加三等于五。",
                "减法是加法的逆运算：五减二等于三。",
                "乘法口诀：二三得六。",
            ],
        },
        {
            "title": "科学小实验",
            "description": "小学科学：水的三态变化",
            "slides": [
                "水有三种状态：固态、液态、气态。",
                "冰加热会融化成水，水加热会蒸发成水蒸气。",
                "这就是水的三态变化。",
            ],
        },
        {
            "title": "大学英语听力",
            "description": "高校英语：日常听力练习",
            "slides": [
                "Listen to the conversation and answer the questions.",
                "Excuse me, could you tell me how to get to the library?",
                "Sure, go straight and turn left at the corner.",
            ],
        },
        {
            "title": "化学基础",
            "description": "高中化学：化学式与元素",
            "slides": [
                "水的化学式是 H₂O，由氢和氧组成。",
                "硫酸的化学式是 H₂SO₄，是一种强酸。",
                "氯化钠是食盐的主要成分，化学式 NaCl。",
            ],
        },
        {
            "title": "生物课堂",
            "description": "初中生物：细胞的基本结构",
            "slides": [
                "细胞是生命活动的基本单位。",
                "细胞由细胞膜、细胞质和细胞核组成。",
                "细胞膜控制物质进出细胞。",
            ],
        },
        {
            "title": "演讲与口才",
            "description": "职场通用：演讲技巧入门",
            "slides": [
                "好的演讲从一个清晰的开场开始。",
                "用故事和例子让观点更生动。",
                "结尾要简洁有力，给听众留下深刻印象。",
            ],
        },
        {
            "title": "地理知识",
            "description": "初中地理：中国地形概况",
            "slides": [
                "中国地势西高东低，呈三级阶梯分布。",
                "第一级阶梯是青藏高原，平均海拔四千米以上。",
                "第二级阶梯包括内蒙古高原、黄土高原等。",
            ],
        },
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
            slides_count=len(preset["slides"]),
            status="completed",
        )
        db.add(project)
        await db.flush()
        for idx, text in enumerate(preset["slides"]):
            db.add(
                CoursewareSlide(
                    project_id=project.id,
                    slide_index=idx,
                    original_text=text,
                    status="completed",
                )
            )
    await db.flush()
