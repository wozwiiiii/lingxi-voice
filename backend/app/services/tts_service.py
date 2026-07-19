import asyncio
import hashlib
import random
import time
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.task import SynthesisTask
from app.preprocess.llm_pipeline import llm_pipeline
from app.providers.base import SynthesisParams
from app.providers.provider_chain import get_active_provider_async
from app.schemas.tts import TTSRequest, TTSResponse
from app.utils.redis_client import get_redis
from app.utils.storage import storage


async def synthesize_tts(
    db: AsyncSession,
    user_id: str | None,
    request: TTSRequest,
) -> TTSResponse:
    # 1. LLM preprocess
    processed_text = await llm_pipeline.process(request.text)

    # 2. Cache check
    cache_key_data = (
        f"{processed_text}|{request.voice_id}|{request.speed}|"
        f"{request.emotion}|{request.style}|{request.language}"
    )
    cache_hash = hashlib.sha256(cache_key_data.encode()).hexdigest()
    redis = await get_redis()

    cached_path = await redis.get(f"tts:result:{cache_hash}")
    if cached_path:
        task = SynthesisTask(
            user_id=uuid.UUID(user_id) if user_id else None,
            voice_id=uuid.UUID(request.voice_id),
            type="tts", input_text=request.text,
            llm_processed_text=processed_text,
            params=request.model_dump(), status="completed",
            output_audio_path=cached_path,
            output_format=request.output_format,
            cached=True,
        )
        db.add(task)
        await db.flush()
        return TTSResponse(
            task_id=str(task.id), status="completed",
            audio_url=f"/media/{cached_path}", cached=True,
        )

    # 3. Cache stampede protection
    lock_key = f"tts:lock:{cache_hash}"
    locked = await redis.set(lock_key, "1", nx=True, ex=5)
    if not locked:
        for _ in range(10):
            await asyncio.sleep(0.05)
            cached_path = await redis.get(f"tts:result:{cache_hash}")
            if cached_path:
                task = SynthesisTask(
                    user_id=uuid.UUID(user_id) if user_id else None,
                    voice_id=uuid.UUID(request.voice_id),
                    type="tts", input_text=request.text,
                    llm_processed_text=processed_text,
                    params=request.model_dump(), status="completed",
                    output_audio_path=cached_path,
                    output_format=request.output_format,
                    cached=True,
                )
                db.add(task)
                return TTSResponse(
                    task_id=str(task.id), status="completed",
                    audio_url=f"/media/{cached_path}", cached=True,
                )

    # 4. Call provider
    try:
        provider = await get_active_provider_async()
        params = SynthesisParams(
            speed=request.speed, pitch=request.pitch,
            volume=request.volume, emotion=request.emotion,
            style=request.style, language=request.language,
            instruction=request.instruction,
        )
        start = time.monotonic()
        result = await provider.synthesize(processed_text, request.voice_id, params)
        duration_ms = int((time.monotonic() - start) * 1000)

        ext = result.format or request.output_format
        audio_path = await storage.save(result.audio_data, "audio", ext)

        ttl = 86400 + random.randint(0, 7200)
        await redis.setex(f"tts:result:{cache_hash}", ttl, audio_path)
        await redis.delete(lock_key)

        task = SynthesisTask(
            user_id=uuid.UUID(user_id) if user_id else None,
            voice_id=uuid.UUID(request.voice_id),
            type="tts", input_text=request.text,
            llm_processed_text=processed_text,
            params=request.model_dump(), status="completed",
            output_audio_path=audio_path,
            output_format=request.output_format,
            provider_used=provider.name, duration_ms=duration_ms,
        )
        db.add(task)
        await db.flush()

        return TTSResponse(
            task_id=str(task.id), status="completed",
            audio_url=f"/media/{audio_path}",
            provider_used=provider.name, duration_ms=duration_ms,
            processed_text=processed_text if processed_text != request.text else None,
        )
    except Exception:
        await redis.delete(lock_key)
        raise
