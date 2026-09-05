"""Audio processing utilities using ffmpeg."""

import json
import subprocess


def get_audio_info(filepath: str) -> dict:
    result = subprocess.run(
        [
            "ffprobe", "-v", "quiet", "-print_format", "json",
            "-show_format", "-show_streams", filepath,
        ],
        capture_output=True, text=True, check=True,
    )
    data = json.loads(result.stdout)
    audio_stream = next(
        (s for s in data.get("streams", []) if s["codec_type"] == "audio"), None
    )
    fmt = data.get("format", {})
    return {
        "duration": float(audio_stream.get("duration", fmt.get("duration", 0))),
        "sample_rate": int(audio_stream.get("sample_rate", 0)),
        "channels": int(audio_stream.get("channels", 0)),
        "codec_name": audio_stream.get("codec_name", ""),
        "format_name": fmt.get("format_name", ""),
    }


def resample_to_16k(input_path: str, output_path: str) -> str:
    subprocess.run(
        [
            "ffmpeg", "-y", "-i", input_path,
            "-ar", "16000", "-ac", "1", "-sample_fmt", "s16", output_path,
        ],
        capture_output=True, check=True,
    )
    return output_path


def normalize_audio(input_path: str, output_path: str) -> str:
    subprocess.run(
        [
            "ffmpeg", "-y", "-i", input_path,
            "-af", "loudnorm=I=-16:TP=-1.5:LRA=11",
            "-ar", "16000", output_path,
        ],
        capture_output=True, check=True,
    )
    return output_path


def get_audio_duration_ms(filepath: str) -> int:
    info = get_audio_info(filepath)
    return int(info["duration"] * 1000)


def probe_duration_ms(filepath: str) -> int | None:
    """安全读取真实音频时长（毫秒）。

    ffprobe 不可用、或文件并非有效音频（如测试中的桩数据）时返回 None，
    调用方回退 0 表示「未知」——绝不回退成接口往返耗时（P2-1：那会把
    HTTP 延迟当成音频时长写进任务记录和下载包 manifest）。
    """
    try:
        return get_audio_duration_ms(filepath)
    except Exception:
        return None


def read_file_header(filepath: str, nbytes: int = 4) -> bytes:
    with open(filepath, "rb") as f:
        return f.read(nbytes)
