"""Local CosyVoice2 provider — sends HTTP requests to the inference service."""

from typing import AsyncIterator

import httpx

from app.config import settings
from app.providers.base import (
    AudioResult,
    ProviderCapabilities,
    SynthesisParams,
    TTSProvider,
    VoiceMetadata,
)


class LocalCosyVoiceProvider(TTSProvider):
    def __init__(self) -> None:
        super().__init__(
            ProviderCapabilities(
                max_text_length=2000,
                streaming=True,
                emotions=[
                    "高兴", "悲伤", "愤怒", "惊讶", "恐惧", "厌恶", "中性",
                    "兴奋", "温柔", "严肃", "活泼", "低沉", "明亮", "急促",
                    "缓慢", "清晰",
                ],
                styles=[
                    "新闻播报", "故事讲述", "客服对话", "教学讲解", "广播主持",
                    "轻柔细语", "激情演讲", "自然聊天", "朗诵诗歌", "角色扮演",
                    "日常问候",
                ],
                languages=["zh", "en", "ja", "ko", "yue"],
                instruct_mode=True,
                zero_shot_clone=True,
            )
        )

    @property
    def name(self) -> str:
        return "local:cosyvoice2"

    async def synthesize(
        self, text: str, voice_id: str, params: SynthesisParams
    ) -> AudioResult:
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(
                f"{settings.INFERENCE_SERVICE_URL}/synthesize",
                json={
                    "text": text,
                    "voice_id": voice_id,
                    "speed": params.speed,
                    "emotion": params.emotion,
                    "style": params.style,
                    "instruction": params.instruction,
                    "stream": False,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            return AudioResult(
                audio_data=resp.content,
                format=data.get("format", "wav"),
                duration_ms=data.get("duration_ms", 0),
            )

    async def synthesize_stream(
        self, text: str, voice_id: str, params: SynthesisParams
    ) -> AsyncIterator[bytes]:
        async with httpx.AsyncClient(timeout=300) as client:
            async with client.stream(
                "POST",
                f"{settings.INFERENCE_SERVICE_URL}/synthesize",
                json={
                    "text": text,
                    "voice_id": voice_id,
                    "speed": params.speed,
                    "emotion": params.emotion,
                    "style": params.style,
                    "instruction": params.instruction,
                    "stream": True,
                },
            ) as response:
                response.raise_for_status()
                async for chunk in response.aiter_bytes():
                    yield chunk

    async def clone_voice(self, audio: bytes, name: str) -> VoiceMetadata:
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(
                f"{settings.INFERENCE_SERVICE_URL}/clone/extract",
                files={"audio": ("sample.wav", audio, "audio/wav")},
                data={"name": name},
            )
            resp.raise_for_status()
            data = resp.json()
            return VoiceMetadata(
                voice_id=data["voice_id"],
                name=name,
                provider=self.name,
                is_cloned=True,
            )

    async def list_preset_voices(self) -> list[VoiceMetadata]:
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{settings.INFERENCE_SERVICE_URL}/voices")
            resp.raise_for_status()
            return [
                VoiceMetadata(
                    voice_id=v["id"],
                    name=v["name"],
                    provider=self.name,
                    is_cloned=False,
                )
                for v in resp.json()["voices"]
            ]

    async def check_health(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(f"{settings.INFERENCE_SERVICE_URL}/health")
                return resp.status_code == 200
        except Exception:
            return False
