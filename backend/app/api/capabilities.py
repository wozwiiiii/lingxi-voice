from fastapi import APIRouter

from app.providers.provider_chain import get_all_capabilities

router = APIRouter(prefix="/api", tags=["capabilities"])


@router.get("/capabilities")
async def get_capabilities():
    return {"providers": get_all_capabilities()}
