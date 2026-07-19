"""Voice clone service — async clone processing with offloaded I/O."""

import asyncio
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import AsyncSessionLocal
from app.models.consent import Consent
from app.models.voice import Voice
from app.preprocess.audio_quality import check_audio_quality
from app.providers.provider_chain import get_active_provider_async
from app.utils.redis_client import get_redis
from app.utils.storage import storage


async def clone_voice_async(
    user_id: str,
    validated_audio_path: str,
    audio_sha256: str,
    name: str,
    description: str | None,
    purpose: str,
) -> dict:
    async with AsyncSessionLocal() as db:
        # 1. Duplicate name check
        existing = await db.execute(
            select(Voice).where(
                Voice.user_id == uuid.UUID(user_id),
                Voice.name == name,
            )
        )
        if existing.scalar_one_or_none():
            return {"status": "duplicate", "message": "声音名称已存在"}

        # 2. Audio quality gate
        abs_path = await storage.get_path(validated_audio_path)
        quality = check_audio_quality(abs_path)
        if not quality.passed:
            return {"status": "failed", "error": quality.reject_reason}

        # 3. Consent record
        consent = Consent(
            user_id=uuid.UUID(user_id),
            audio_sha256=audio_sha256,
            purpose=purpose,
            agreed_at=db.func.now(),
        )
        db.add(consent)
        await db.flush()

        # 4. Clone (audio read offloaded to thread to avoid blocking event loop)
        audio_data = await asyncio.to_thread(lambda: open(abs_path, "rb").read())
        provider = await get_active_provider_async()
        voice_meta = await provider.clone_voice(audio_data, name)

        # 5. Save voice record
        voice = Voice(
            user_id=uuid.UUID(user_id),
            name=name,
            description=description,
            type="cloned",
            is_public=False,
            provider=provider.name,
            provider_metadata={"voice_id": voice_meta.voice_id},
            reference_audio_path=validated_audio_path,
            consent_id=consent.id,
        )
        db.add(voice)
        await db.flush()

        return {
            "status": "completed",
            "voice_id": str(voice.id),
            "voice_meta": {"id": voice_meta.voice_id, "name": voice_meta.name},
        }
