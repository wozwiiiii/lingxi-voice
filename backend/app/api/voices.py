from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.voice import Voice
from app.schemas.voice import VoiceResponse

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
