"""Courseware API — upload, edit, synthesize, download, library."""

import io
import uuid as uuid_mod

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.courseware import CoursewareProject
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
    Public presets (user_id IS NULL) are accessible to everyone.
    Private projects require the owner or return 404 (prevents ID enumeration).
    """
    if not project:
        raise HTTPException(status_code=404)
    if project.user_id is not None and (user is None or project.user_id != user.id):
        raise HTTPException(status_code=404)


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
    _check_ownership(project, user)
    slide = await update_slide(
        db, project_id, slide_index, data.model_dump(exclude_none=True),
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
    _check_ownership(project, user)
    await apply_bulk_settings(db, project_id, data.model_dump(exclude_none=True))
    return {"status": "ok"}


@router.post("/{project_id}/synthesize", response_model=SynthesizeResponse)
async def synthesize_courseware(
    project_id: str,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    project = await get_project(db, project_id)
    _check_ownership(project, user)
    if project.status not in ("ready", "failed"):
        raise HTTPException(
            status_code=409,
            detail=f"课件状态为 {project.status}，无法开始合成",
        )

    from app.tasks.courseware_tasks import synthesize_courseware_task
    task = synthesize_courseware_task.delay(str(project.id))

    project.status = "synthesizing"
    project.celery_task_id = task.id
    await db.flush()

    return SynthesizeResponse(
        project_id=str(project.id),
        status="synthesizing",
        message="课件合成已开始",
    )


@router.get("/{project_id}/progress")
async def get_progress(
    project_id: str,
    db: AsyncSession = Depends(get_db),
    user_or_visitor=Depends(get_visitor_or_user),
):
    project = await get_project(db, project_id)
    user, _ = user_or_visitor
    _check_ownership(project, user)

    from app.utils.redis_client import get_redis
    import asyncio
    import json

    async def event_stream():
        redis = await get_redis()
        for _ in range(300):
            progress = await redis.get(f"courseware:progress:{project_id}")
            if progress:
                data = json.loads(progress)
                yield f"data: {json.dumps(data)}\n\n"
                if data.get("status") in ("completed", "failed"):
                    break
            await asyncio.sleep(1)

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

    # Sanitize filename: strip all non-printable chars
    import re
    safe_title = re.sub(r'[^\w\s\-.]', '_', project.title)
    return StreamingResponse(
        io.BytesIO(zip_bytes),
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename={safe_title}.zip"},
    )


@router.delete("/{project_id}", status_code=204)
async def delete_courseware(
    project_id: str,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    project = await get_project(db, project_id)
    _check_ownership(project, user)

    slides = await get_slides(db, project_id)
    for slide in slides:
        if slide.audio_path:
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
