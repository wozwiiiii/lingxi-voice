"""TTSProvider abstract interface and shared types.

All TTS providers (local GPU, cloud API) implement this interface.
This enables the hybrid inference strategy: local for dev, cloud for prod,
with a provider chain and circuit breaker for graceful degradation.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import AsyncIterator

from pydantic import BaseModel


class ProviderCapabilities(BaseModel):
    """What a TTS provider can do. Used by the frontend to show/hide controls."""

    max_text_length: int = 1000
    supported_formats: list[str] = ["wav", "mp3"]
    streaming: bool = True
    emotions: list[str] = []
    styles: list[str] = []
    languages: list[str] = ["zh", "en"]
    instruct_mode: bool = False
    zero_shot_clone: bool = False
    clone_min_duration: float = 5.0
    clone_max_duration: float = 30.0


@dataclass
class SynthesisParams:
    speed: float = 1.0
    pitch: float = 0.0
    volume: float = 1.0
    emotion: str | None = None
    style: str | None = None
    language: str = "zh"
    instruction: str | None = None


@dataclass
class AudioResult:
    audio_data: bytes
    format: str
    duration_ms: int
    sample_rate: int = 24000


@dataclass
class VoiceMetadata:
    voice_id: str
    name: str
    provider: str
    is_cloned: bool = False


class TTSProvider(ABC):
    def __init__(self, capabilities: ProviderCapabilities):
        self.capabilities = capabilities

    @abstractmethod
    async def synthesize(
        self, text: str, voice_id: str, params: SynthesisParams
    ) -> AudioResult: ...

    @abstractmethod
    async def synthesize_stream(
        self, text: str, voice_id: str, params: SynthesisParams
    ) -> AsyncIterator[bytes]: ...

    @abstractmethod
    async def clone_voice(self, audio: bytes, name: str) -> VoiceMetadata: ...

    @abstractmethod
    async def list_preset_voices(self) -> list[VoiceMetadata]: ...

    @abstractmethod
    async def check_health(self) -> bool: ...

    @property
    @abstractmethod
    def name(self) -> str: ...
