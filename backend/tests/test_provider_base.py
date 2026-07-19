"""TDD tests for TTSProvider base types — ProviderCapabilities, SynthesisParams."""

import pytest

from app.providers.base import (
    AudioResult,
    ProviderCapabilities,
    SynthesisParams,
    VoiceMetadata,
)


class TestProviderCapabilities:
    def test_default_values(self):
        caps = ProviderCapabilities()
        assert caps.max_text_length == 1000
        assert caps.streaming is True
        assert caps.zero_shot_clone is False
        assert caps.instruct_mode is False
        assert "zh" in caps.languages
        assert "en" in caps.languages

    def test_custom_values(self):
        caps = ProviderCapabilities(
            max_text_length=2000,
            streaming=True,
            emotions=["高兴", "悲伤"],
            languages=["zh", "ja"],
            zero_shot_clone=True,
        )
        assert caps.max_text_length == 2000
        assert len(caps.emotions) == 2
        assert "ja" in caps.languages
        assert caps.zero_shot_clone is True


class TestSynthesisParams:
    def test_default_params(self):
        params = SynthesisParams()
        assert params.speed == 1.0
        assert params.pitch == 0.0
        assert params.volume == 1.0
        assert params.emotion is None
        assert params.style is None
        assert params.language == "zh"

    def test_custom_params(self):
        params = SynthesisParams(speed=1.5, emotion="高兴", language="en")
        assert params.speed == 1.5
        assert params.emotion == "高兴"
        assert params.language == "en"


class TestAudioResult:
    def test_audio_result_fields(self):
        result = AudioResult(
            audio_data=b"\x00\x01\x02",
            format="wav",
            duration_ms=1500,
        )
        assert result.format == "wav"
        assert result.duration_ms == 1500
        assert result.sample_rate == 24000


class TestVoiceMetadata:
    def test_voice_metadata_fields(self):
        meta = VoiceMetadata(
            voice_id="zh_male_001",
            name="标准男声",
            provider="cloud:siliconflow",
            is_cloned=False,
        )
        assert meta.voice_id == "zh_male_001"
        assert meta.is_cloned is False
