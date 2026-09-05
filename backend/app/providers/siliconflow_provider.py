"""SiliconFlow CosyVoice API provider (OpenAI-compatible protocol)."""

import logging
from typing import AsyncIterator

import httpx
from openai import APIStatusError, AsyncOpenAI

from app.config import settings
from app.providers.base import (
    AudioResult,
    ProviderCapabilities,
    SynthesisParams,
    TTSProvider,
    VoiceMetadata,
)
from app.providers.errors import ContentError, ProviderUnavailableError

logger = logging.getLogger(__name__)


async def resolve_provider_voice_id(voice_id: str) -> str:
    """将数据库 Voice UUID 解析为供应商侧真实 voice_id。

    克隆声音在 DB 中以 UUID 存储，供应商侧 id 存于 provider_metadata；
    预设/直传字符串则原样返回。合成与流式合成必须共用此解析，
    否则流式路径传 UUID 会被供应商拒绝。
    """
    import uuid as uuid_mod

    try:
        uid = uuid_mod.UUID(voice_id)
    except (ValueError, AttributeError):
        return voice_id  # 已是供应商侧字符串，原样使用

    from sqlalchemy import select

    from app.database import AsyncSessionLocal
    from app.models.voice import Voice

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Voice).where(Voice.id == uid))
        voice = result.scalar_one_or_none()
        if voice and voice.provider_metadata:
            return voice.provider_metadata.get("voice_id", voice_id)
    return voice_id


class SiliconFlowProvider(TTSProvider):
    def __init__(self) -> None:
        super().__init__(
            ProviderCapabilities(
                max_text_length=1000,
                supported_formats=["mp3", "wav"],
                streaming=True,
                emotions=[
                    "高兴", "悲伤", "愤怒", "惊讶", "中性", "温柔", "严肃", "活泼",
                ],
                styles=[],
                languages=["zh", "en", "ja", "ko"],
                instruct_mode=False,
                zero_shot_clone=True,
                clone_min_duration=3.0,
                clone_max_duration=30.0,
            )
        )
        # timeout 必须显式指定：SDK 默认 600s，上游 hang 住时 worker
        # --concurrency=2 只需两个请求就全站停摆（P0 修复中最危险的单点）。
        # max_retries=1 给瞬时抖动一次自救机会，又不会把故障等待时间翻倍。
        self._client = AsyncOpenAI(
            api_key=settings.SILICONFLOW_API_KEY,
            base_url=settings.SILICONFLOW_BASE_URL,
            timeout=settings.PROVIDER_TIMEOUT_S,
            max_retries=1,
        )

    @property
    def name(self) -> str:
        return "cloud:siliconflow"

    async def synthesize(
        self, text: str, voice_id: str, params: SynthesisParams
    ) -> AudioResult:
        import time

        # Resolve the real API voice ID from DB if voice_id is a UUID
        actual_voice_id = await resolve_provider_voice_id(voice_id)

        start = time.monotonic()
        try:
            response = await self._client.audio.speech.create(
                model="FunAudioLLM/CosyVoice2-0.5B",
                voice=actual_voice_id,
                input=text,
                speed=params.speed,
                response_format="mp3",
                extra_body=(
                    {"emotion": params.emotion, "language": params.language}
                    if params.emotion
                    else {}
                ),
            )
        except APIStatusError as e:
            logger.error(f"SiliconFlow API error: {e.status_code} - {e.body}")
            # 按语义分类：402/429/5xx 是供应商侧问题（可重试、计入熔断），
            # 400 是请求内容问题（不可重试、不污染熔断计数）。
            # 均继承 ValueError，tts_service 的 503 映射行为不变。
            if e.status_code == 402:
                raise ProviderUnavailableError("语音服务账户余额不足，请充值后重试") from e
            elif e.status_code == 400:
                raise ContentError(f"语音合成参数错误: {e.body}") from e
            elif e.status_code == 429:
                raise ProviderUnavailableError("语音服务请求过于频繁，请稍后重试") from e
            else:
                raise ProviderUnavailableError(
                    f"语音服务暂时不可用 (错误码 {e.status_code})，请稍后重试"
                ) from e

        audio_data = response.content
        duration_ms = int((time.monotonic() - start) * 1000)
        return AudioResult(audio_data=audio_data, format="mp3", duration_ms=duration_ms)

    async def synthesize_stream(
        self, text: str, voice_id: str, params: SynthesisParams
    ) -> AsyncIterator[bytes]:
        # 与 synthesize 一致：UUID → 供应商侧真实 voice_id
        actual_voice_id = await resolve_provider_voice_id(voice_id)
        # 原为硬编码 300s，与 PROVIDER_TIMEOUT_S 统一口径，避免两条链路
        # 对"上游多久算挂"得出不同答案
        async with httpx.AsyncClient(timeout=settings.PROVIDER_TIMEOUT_S) as client:
            async with client.stream(
                "POST",
                f"{settings.SILICONFLOW_BASE_URL}/audio/speech",
                headers={
                    "Authorization": f"Bearer {settings.SILICONFLOW_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "FunAudioLLM/CosyVoice2-0.5B",
                    "voice": actual_voice_id,
                    "input": text,
                    "speed": params.speed,
                    "response_format": "pcm",
                    "stream": True,
                },
            ) as resp:
                resp.raise_for_status()
                async for chunk in resp.aiter_bytes():
                    yield chunk

    async def clone_voice(self, audio: bytes, name: str) -> VoiceMetadata:
        from io import BytesIO

        file = BytesIO(audio)
        file.name = "sample.wav"
        uploaded = await self._client.files.create(file=file, purpose="audio")
        return VoiceMetadata(
            voice_id=f"siliconflow_{uploaded.id}",
            name=name,
            provider=self.name,
            is_cloned=True,
        )

    async def list_preset_voices(self) -> list[VoiceMetadata]:
        presets = [
            ("zh_male_qingse", "青涩男声"),
            ("zh_female_wenrou", "温柔女声"),
            ("zh_male_zhubo", "男主播"),
            ("zh_female_zhubo", "女主播"),
            ("en_male_narrator", "English Male"),
            ("en_female_narrator", "English Female"),
        ]
        return [
            VoiceMetadata(voice_id=vid, name=vname, provider=self.name)
            for vid, vname in presets
        ]

    async def check_health(self) -> bool:
        try:
            voices = await self.list_preset_voices()
            return len(voices) > 0
        except Exception:
            return False
