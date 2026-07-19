"""Voice library service — preset voice seeding."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.voice import Voice
from app.providers.provider_chain import get_active_provider_async


async def seed_preset_voices(db: AsyncSession) -> None:
    """Seed preset voices from the active provider. Idempotent — skips existing."""
    try:
        provider = await get_active_provider_async()
    except RuntimeError:
        return  # No provider available, skip seeding

    preset_metas = await provider.list_preset_voices()
    for meta in preset_metas:
        existing = await db.execute(
            select(Voice).where(
                Voice.provider == meta.provider,
                Voice.name == meta.name,
                Voice.type == "preset",
            )
        )
        if existing.scalar_one_or_none():
            continue
        voice = Voice(
            name=meta.name,
            type="preset",
            is_public=True,
            provider=meta.provider,
            provider_metadata={"voice_id": meta.voice_id},
        )
        db.add(voice)
    await db.flush()
