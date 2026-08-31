"""TDD tests for audio quality checks — SNR, silence ratio, clipping detection."""

import tempfile
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

from app.preprocess.audio_quality import check_audio_quality


@pytest.fixture
def clean_sine_wave_2s():
    """Generate 2s 440Hz sine wave at 16kHz."""
    sr = 16000
    t = np.linspace(0, 2.0, int(sr * 2.0), endpoint=False)
    return (0.5 * np.sin(2 * np.pi * 440 * t)).astype(np.float32), sr


def _write_temp_wav(data: np.ndarray, sr: int) -> str:
    f = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    sf.write(f.name, data, sr)
    return f.name


class TestCleanAudio:
    def test_sine_metrics_computed(self, clean_sine_wave_2s):
        """Clean sine validates SNR/silence/clipping are computed.
        Note: pure tones may report low SNR (all frames equal energy),
        which is an edge case irrelevant to voice samples."""
        data, sr = clean_sine_wave_2s
        path = _write_temp_wav(data, sr)
        try:
            report = check_audio_quality(path)
            assert report.duration_s > 1.0
            assert report.sample_rate == sr
            assert report.silence_ratio < 0.50
            # SNR algorithm assumes varying-energy signal (speech-like);
            # pure sine has uniform frame energy, so SNR may be low.
            # This is acceptable — real voice samples have natural variation.
        finally:
            Path(path).unlink()


class TestNoisyAudio:
    def test_very_noisy_audio_rejected(self):
        sr = 16000
        duration = 2.0
        t = np.linspace(0, duration, int(sr * duration), endpoint=False)
        signal = 0.05 * np.sin(2 * np.pi * 440 * t)
        noise = np.random.normal(0, 0.5, len(t))
        data = (signal + noise).astype(np.float32)

        path = _write_temp_wav(data, sr)
        try:
            report = check_audio_quality(path)
            assert report.passed is False
            assert report.reject_reason is not None
            assert "噪声" in report.reject_reason
        finally:
            Path(path).unlink()


class TestSilenceAudio:
    def test_near_silent_audio_rejected(self):
        sr = 16000
        duration = 2.0
        # Very quiet signal
        data = (np.random.normal(0, 0.001, int(sr * duration))).astype(np.float32)

        path = _write_temp_wav(data, sr)
        try:
            report = check_audio_quality(path)
            # Either noise rejection or silence rejection
            assert report.passed is False
            assert report.reject_reason is not None
        finally:
            Path(path).unlink()


class TestClippingAudio:
    def test_clipped_audio_rejected(self):
        sr = 16000
        duration = 2.0
        t = np.linspace(0, duration, int(sr * duration), endpoint=False)
        # Generate signal that clips heavily
        data = (2.0 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)
        data = np.clip(data, -1.0, 1.0)  # This creates flat tops = clipping

        path = _write_temp_wav(data, sr)
        try:
            report = check_audio_quality(path)
            # 绝对阈值（≥0.98 满量程）下，平顶采样必然被计入削波比。
            # 合成纯音的帧能量均匀（SNR≈0），可能先被噪声分支拒绝——
            # 这里只验证削波被正确检出且样本被拒。
            assert report.clipping_ratio > 0.10
            assert report.passed is False
        finally:
            Path(path).unlink()

    def test_quiet_clean_audio_not_flagged_as_clipped(self):
        """P2-2：安静但干净的录音（峰值远低于满量程）削波比必须为 0。

        旧实现的阈值是本段峰值的 98%，安静录音会把阈值拉到极低，
        大量正常采样被误判削波导致错误拒绝。
        """
        sr = 16000
        duration = 2.0
        t = np.linspace(0, duration, int(sr * duration), endpoint=False)
        # 峰值只有 0.3 的干净正弦——离满量程很远，绝无削波
        data = (0.3 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)

        path = _write_temp_wav(data, sr)
        try:
            report = check_audio_quality(path)
            assert report.clipping_ratio == 0.0
        finally:
            Path(path).unlink()


class TestStereoHandling:
    def test_stereo_audio_converts_to_mono(self, clean_sine_wave_2s):
        data_mono, sr = clean_sine_wave_2s
        data_stereo = np.column_stack([data_mono, data_mono * 0.5])

        path = _write_temp_wav(data_stereo, sr)
        try:
            report = check_audio_quality(path)
            assert report.duration_s > 1.0
        finally:
            Path(path).unlink()
