"""Audio quality checks for uploaded voice clone samples.

All checks are deterministic (no ML) — fast, cheap, and serve as a quality
gate before expensive GPU/API calls.
"""

import math
from dataclasses import dataclass

import numpy as np
import soundfile as sf


@dataclass
class AudioQualityReport:
    passed: bool
    snr_db: float
    silence_ratio: float
    clipping_ratio: float
    duration_s: float
    sample_rate: int
    reject_reason: str | None = None


def check_audio_quality(filepath: str) -> AudioQualityReport:
    data, sr = sf.read(filepath)
    if data.ndim > 1:
        data = data.mean(axis=1)

    duration_s = len(data) / sr
    snr = _estimate_snr(data)
    silence_ratio = _estimate_silence_ratio(data, sr)
    clipping_ratio = _estimate_clipping_ratio(data)

    passed = True
    reason = None

    if snr < 10.0:
        passed = False
        reason = f"噪声过高(SNR={snr:.1f}dB)，请在安静环境中重录"
    elif silence_ratio > 0.50:
        passed = False
        reason = f"样本有效语音不足(静音比={silence_ratio:.0%})"
    elif clipping_ratio > 0.10:
        passed = False
        reason = f"录音音量过大导致失真(削波比={clipping_ratio:.0%})"

    return AudioQualityReport(
        passed=passed, snr_db=round(snr, 1),
        silence_ratio=round(silence_ratio, 3),
        clipping_ratio=round(clipping_ratio, 3),
        duration_s=round(duration_s, 2),
        sample_rate=sr, reject_reason=reason,
    )


def _estimate_snr(signal: np.ndarray) -> float:
    rms = np.sqrt(np.mean(signal**2))
    if rms < 1e-10:
        return 0.0
    frame_len = 512
    n_frames = len(signal) // frame_len
    if n_frames < 2:
        return 20.0
    frame_energy = np.array([
        np.mean(np.abs(signal[i * frame_len : (i + 1) * frame_len]))
        for i in range(n_frames)
    ])
    noise_floor = np.percentile(frame_energy, 10)
    if noise_floor < 1e-10:
        return 30.0
    return 20 * math.log10(rms / noise_floor)


def _estimate_silence_ratio(signal: np.ndarray, sr: int) -> float:
    frame_len = int(sr * 0.02)
    n_frames = len(signal) // frame_len
    if n_frames == 0:
        return 1.0
    silent = 0
    for i in range(n_frames):
        frame = signal[i * frame_len : (i + 1) * frame_len]
        if np.max(np.abs(frame)) < 0.02:
            silent += 1
    return silent / n_frames


def _estimate_clipping_ratio(signal: np.ndarray) -> float:
    max_val = np.max(np.abs(signal))
    if max_val < 1e-10:
        return 0.0
    threshold = 0.98 * max_val
    return np.sum(np.abs(signal) >= threshold) / len(signal)
