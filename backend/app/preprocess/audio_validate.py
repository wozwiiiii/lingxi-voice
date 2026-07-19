"""Complete upload validation chain for audio files."""

import hashlib
import uuid
from dataclasses import dataclass

from fastapi import HTTPException, UploadFile, status

from app.config import settings
from app.utils.audio import get_audio_duration_ms, get_audio_info
from app.utils.storage import storage

MAGIC_BYTES = {
    b"RIFF": "wav",
    b"fLaC": "flac",
    b"OggS": "ogg",
}


@dataclass
class ValidatedAudio:
    filepath: str
    sha256: str
    duration_ms: int
    sample_rate: int
    original_filename: str


async def validate_audio_upload(file: UploadFile) -> ValidatedAudio:
    # 1. File size
    content = await file.read()
    file_size_mb = len(content) / (1024 * 1024)
    if file_size_mb > settings.MAX_UPLOAD_SIZE_MB:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"文件过大(>{settings.MAX_UPLOAD_SIZE_MB}MB)",
        )

    # 2. MIME + magic bytes
    content_type = file.content_type or ""
    if not content_type.startswith("audio/"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="仅支持音频文件")

    magic = content[:4]
    is_mp3 = magic[:2] in (b"\xff\xfb", b"\xff\xf3", b"\xff\xf2") or magic.startswith(b"ID3")
    recognized = is_mp3 or any(magic.startswith(k) for k in MAGIC_BYTES)
    if not recognized:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="不支持的音频格式，请上传 WAV 或 MP3 文件",
        )

    # 3. Sanitize filename → store
    ext = ".mp3" if is_mp3 else ".wav"
    tmp_path = await storage.save(content, "uploads", ext)
    abs_path = await storage.get_path(tmp_path)

    # 4. ffprobe validation
    try:
        info = get_audio_info(abs_path)
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="音频文件损坏或无法解析")

    duration_s = info["duration"]
    if duration_s < 3.0 or duration_s > 31.0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"音频时长需在 3-30 秒之间(当前 {duration_s:.1f}s)",
        )

    duration_ms = get_audio_duration_ms(abs_path)

    # 5. SHA256
    sha256 = hashlib.sha256(content).hexdigest()

    return ValidatedAudio(
        filepath=tmp_path, sha256=sha256,
        duration_ms=duration_ms, sample_rate=info["sample_rate"],
        original_filename=file.filename or "unknown",
    )
