from fastapi import APIRouter, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.tts import TTSRequest, TTSResponse
from app.security.dependencies import get_visitor_or_user
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
    user_id = str(user.id) if user else None
    return await synthesize_tts(db, user_id, data)
