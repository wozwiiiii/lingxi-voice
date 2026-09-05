import asyncio
import hashlib
import random
import time
import uuid

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.task import SynthesisTask
from app.models.voice import Voice
from app.preprocess.llm_pipeline import llm_pipeline
from app.providers.base import SynthesisParams
from app.providers.errors import ProviderUnavailableError
from app.providers.provider_chain import (
    get_active_provider_async,
    get_circuit_for_provider,
)
from app.schemas.tts import TTSRequest, TTSResponse
from app.api.media import sign_media_url
from app.utils.audio import probe_duration_ms
from app.utils.metrics import TTS_CHARACTERS_TOTAL, observe_tts
from app.utils.redis_client import get_redis
from app.utils.storage import storage

# 缓存锁等待上限：等不到结果时快速失败，而不是 fall-through 击穿缓存
LOCK_WAIT_TIMEOUT_S = 5.0
LOCK_POLL_INTERVAL_S = 0.1


def _build_task(
    user_id: str | None,
    request: TTSRequest,
    voice_pk: uuid.UUID,
    processed_text: str,
    audio_path: str,
    *,
    cached: bool,
    provider_name: str | None = None,
    duration_ms: int | None = None,
) -> SynthesisTask:
    return SynthesisTask(
        user_id=uuid.UUID(user_id) if user_id else None,
        voice_id=voice_pk,
        type="tts", input_text=request.text,
        llm_processed_text=processed_text,
        params=request.model_dump(), status="completed",
        output_audio_path=audio_path,
        output_format=request.output_format,
        cached=cached,
        provider_used=provider_name, duration_ms=duration_ms,
    )


async def _resolve_voice(db: AsyncSession, voice_id: str) -> Voice:
    """校验 voice 存在性并返回记录。不存在/格式非法 → 404（问题 9：
    避免 FK 违约导致的 500）。"""
    try:
        voice_pk = uuid.UUID(voice_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Voice not found")
    result = await db.execute(select(Voice).where(Voice.id == voice_pk))
    voice = result.scalar_one_or_none()
    if voice is None:
        raise HTTPException(status_code=404, detail="Voice not found")
    return voice


async def synthesize_tts(
    db: AsyncSession,
    user_id: str | None,
    request: TTSRequest,
) -> TTSResponse:
    # 0. 校验 voice 存在（先于一切昂贵操作）
    voice = await _resolve_voice(db, request.voice_id)

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
        task = _build_task(
            user_id, request, voice.id, processed_text, cached_path, cached=True
        )
        db.add(task)
        await db.flush()
        return TTSResponse(
            task_id=str(task.id), status="completed",
            audio_url=sign_media_url(cached_path), cached=True,
        )

    # 3. Cache stampede protection：锁值用随机 token 标识所有权，
    #    释放时只删自己的锁；等待超时后快速失败而非继续合成（问题 6）
    lock_key = f"tts:lock:{cache_hash}"
    lock_token = uuid.uuid4().hex
    locked = await redis.set(lock_key, lock_token, nx=True, ex=30)
    if not locked:
        deadline = time.monotonic() + LOCK_WAIT_TIMEOUT_S
        while time.monotonic() < deadline:
            await asyncio.sleep(LOCK_POLL_INTERVAL_S)
            cached_path = await redis.get(f"tts:result:{cache_hash}")
            if cached_path:
                task = _build_task(
                    user_id, request, voice.id, processed_text, cached_path,
                    cached=True,
                )
                db.add(task)
                await db.flush()
                return TTSResponse(
                    task_id=str(task.id), status="completed",
                    audio_url=sign_media_url(cached_path), cached=True,
                )
        raise HTTPException(
            status_code=503, detail="相同内容的合成正在进行中，请稍后重试"
        )

    # 4. Call provider
    try:
        try:
            provider = await get_active_provider_async()
        except RuntimeError as e:
            raise HTTPException(status_code=503, detail="所有语音服务暂时不可用，请稍后重试") from e
        params = SynthesisParams(
            speed=request.speed, pitch=request.pitch,
            volume=request.volume, emotion=request.emotion,
            style=request.style, language=request.language,
            instruction=request.instruction,
        )
        try:
            async with observe_tts(provider.name) as outcome:
                result = await provider.synthesize(processed_text, request.voice_id, params)
                outcome["success"] = True
            TTS_CHARACTERS_TOTAL.labels(provider.name).inc(len(processed_text))
        except ValueError as e:
            # F1 修复：provider 的 402/429/5xx 全部以 ValueError 子类抛出，
            # 原先这里直接 503 返回、从不记熔断失败——最常见的失效（上游
            # 限流/宕机）反而永远不会触发熔断，熔断器形同虚设。
            # ContentError（用户内容问题）不是供应商的锅，不计入。
            if isinstance(e, ProviderUnavailableError):
                circuit = get_circuit_for_provider(provider.name)
                if circuit:
                    await circuit.record_failure()
            raise HTTPException(status_code=503, detail=str(e)) from e
        except Exception as e:
            # 供应商异常 → 记录失败，让熔断器在连续失败后打开（问题 2）
            circuit = get_circuit_for_provider(provider.name)
            if circuit:
                await circuit.record_failure()
            raise HTTPException(status_code=502, detail="语音合成服务暂时不可用，请稍后重试") from e

        circuit = get_circuit_for_provider(provider.name)
        if circuit:
            await circuit.record_success()

        ext = result.format or request.output_format
        audio_path = await storage.save(result.audio_data, "audio", ext)

        # P2-1：duration_ms 存真实音频时长（ffprobe 探测落盘文件），而非
        # provider HTTP 往返耗时。ffprobe 不可用/数据无效时回退 0（未知）。
        # subprocess 阻塞调用，卸载到线程池避免卡住事件循环。
        abs_path = await storage.get_path(audio_path)
        duration_ms = await asyncio.to_thread(probe_duration_ms, abs_path) or 0

        ttl = 86400 + random.randint(0, 7200)
        await redis.setex(f"tts:result:{cache_hash}", ttl, audio_path)
        # 反向索引（P2-6）：文件删除时可据此清理指向它的缓存键，
        # 否则缓存命中会返回已删除路径 → /media 404。
        # audio_path 每次合成都生成新 UUID 文件名，与缓存哈希严格 1:1，
        # 用带 TTL 的字符串键即可（无需集合）。
        await redis.setex(f"tts:refs:{audio_path}", ttl, cache_hash)

        task = _build_task(
            user_id, request, voice.id, processed_text, audio_path,
            cached=False, provider_name=provider.name, duration_ms=duration_ms,
        )
        db.add(task)
        await db.flush()

        return TTSResponse(
            task_id=str(task.id), status="completed",
            audio_url=sign_media_url(audio_path),
            provider_used=provider.name, duration_ms=duration_ms,
            processed_text=processed_text if processed_text != request.text else None,
        )
    finally:
        # 只删自己持有的锁（值匹配），避免误删其他请求的锁
        try:
            current = await redis.get(lock_key)
            if current == lock_token:
                await redis.delete(lock_key)
        except Exception:
            pass  # Redis 抖动不应影响主流程；锁有 TTL 兜底
