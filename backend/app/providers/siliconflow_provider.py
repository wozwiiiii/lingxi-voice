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

logger = logging.getLogger(__name__)


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
        self._client = AsyncOpenAI(
            api_key=settings.SILICONFLOW_API_KEY,
            base_url=settings.SILICONFLOW_BASE_URL,
        )

    @property
    def name(self) -> str:
        return "cloud:siliconflow"

    async def synthesize(
        self, text: str, voice_id: str, params: SynthesisParams
    ) -> AudioResult:
        import time
        import uuid as uuid_mod

        # Resolve the real API voice ID from DB if voice_id is a UUID
        actual_voice_id = voice_id
        try:
            uid = uuid_mod.UUID(voice_id)
            from app.database import AsyncSessionLocal
            from app.models.voice import Voice
            from sqlalchemy import select
            async with AsyncSessionLocal() as db:
                result = await db.execute(select(Voice).where(Voice.id == uid))
                voice = result.scalar_one_or_none()
                if voice and voice.provider_metadata:
                    actual_voice_id = voice.provider_metadata.get("voice_id", voice_id)
        except (ValueError, AttributeError):
            pass  # voice_id is already a plain string, use as-is

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
            if e.status_code == 402:
                raise ValueError("语音服务账户余额不足，请充值后重试") from e
            elif e.status_code == 400:
                raise ValueError(f"语音合成参数错误: {e.body}") from e
            elif e.status_code == 429:
                raise ValueError("语音服务请求过于频繁，请稍后重试") from e
            else:
                raise ValueError(f"语音服务暂时不可用 (错误码 {e.status_code})，请稍后重试") from e

        audio_data = response.content
        duration_ms = int((time.monotonic() - start) * 1000)
        return AudioResult(audio_data=audio_data, format="mp3", duration_ms=duration_ms)

    async def synthesize_stream(
        self, text: str, voice_id: str, params: SynthesisParams
    ) -> AsyncIterator[bytes]:
        async with httpx.AsyncClient(timeout=300) as client:
            async with client.stream(
                "POST",
                f"{settings.SILICONFLOW_BASE_URL}/audio/speech",
                headers={
                    "Authorization": f"Bearer {settings.SILICONFLOW_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "FunAudioLLM/CosyVoice2-0.5B",
                    "voice": voice_id,
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
