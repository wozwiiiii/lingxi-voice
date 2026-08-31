"""File storage abstraction. M1 uses local disk; S3/MinIO impl reserved for later."""

import asyncio
import uuid
from abc import ABC, abstractmethod
from pathlib import Path

from app.config import settings


class StorageBackend(ABC):
    @abstractmethod
    async def save(self, data: bytes, directory: str, extension: str) -> str: ...
    @abstractmethod
    async def read(self, key: str) -> bytes: ...
    @abstractmethod
    async def get_path(self, key: str) -> str: ...
    @abstractmethod
    async def delete(self, key: str) -> None: ...


def _write_bytes(path: Path, data: bytes) -> None:
    path.write_bytes(data)


def _read_bytes(path: Path) -> bytes:
    return path.read_bytes()


def _delete_if_exists(path: Path) -> None:
    if path.exists():
        path.unlink()


class LocalStorage(StorageBackend):
    def __init__(self, root: str | None = None):
        self.root = Path(root or settings.MEDIA_ROOT)
        self.root.mkdir(parents=True, exist_ok=True)

    async def save(self, data: bytes, directory: str, extension: str) -> str:
        subdir = self.root / directory
        subdir.mkdir(parents=True, exist_ok=True)
        filename = f"{uuid.uuid4().hex}.{extension.lstrip('.')}"
        filepath = subdir / filename
        # 磁盘写入是阻塞调用，卸载到线程避免卡住事件循环
        await asyncio.to_thread(_write_bytes, filepath, data)
        return str(filepath.relative_to(self.root))

    async def read(self, key: str) -> bytes:
        filepath = self.root / key
        return await asyncio.to_thread(_read_bytes, filepath)

    async def get_path(self, key: str) -> str:
        return str(self.root / key)

    async def delete(self, key: str) -> None:
        filepath = self.root / key
        await asyncio.to_thread(_delete_if_exists, filepath)


storage = LocalStorage()
