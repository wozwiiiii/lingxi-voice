from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.voice import Voice
from app.preprocess.audio_validate import validate_audio_upload
from app.schemas.clone import CloneResponse
from app.schemas.voice import VoiceResponse
from app.security.dependencies import get_current_user
from app.services.clone_service import clone_voice_async

router = APIRouter(prefix="/api/voices", tags=["voices"])


@router.get("", response_model=list[VoiceResponse])
async def list_voices(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Voice).where(Voice.is_public == True).order_by(Voice.created_at)
    )
    return [VoiceResponse.from_voice(v) for v in result.scalars().all()]


@router.get("/{voice_id}", response_model=VoiceResponse)
async def get_voice(voice_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Voice).where(Voice.id == voice_id))
    voice = result.scalar_one_or_none()
    if not voice:
        raise HTTPException(status_code=404, detail="Voice not found")
    return VoiceResponse.from_voice(voice)


@router.post("/clone", response_model=CloneResponse, status_code=201)
async def clone_voice(
    file: UploadFile = File(...),
    name: str = Form(..., min_length=1, max_length=200),
    purpose: str = Form(..., min_length=5, max_length=500),
    description: str | None = Form(None, max_length=500),
    user=Depends(get_current_user),
):
    """上传参考音频并克隆声音。

    链路：校验音频（大小/格式/时长）→ 质量门（SNR/静音/削波）→
    记录授权（Consent）→ 调用 provider 克隆 → 落库。
    """
    validated = await validate_audio_upload(file)
    result = await clone_voice_async(
        user_id=str(user.id),
        validated_audio_path=validated.filepath,
        audio_sha256=validated.sha256,
        name=name,
        description=description,
        purpose=purpose,
    )
    if result["status"] == "duplicate":
        raise HTTPException(status_code=409, detail=result.get("message", "声音名称已存在"))
    if result["status"] == "failed":
        raise HTTPException(status_code=422, detail=result.get("error", "克隆失败"))
    return CloneResponse(
        status=result["status"],
        voice_id=result.get("voice_id"),
        voice_meta=result.get("voice_meta"),
    )
