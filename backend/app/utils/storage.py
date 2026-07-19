"""File storage abstraction. M1 uses local disk; S3/MinIO impl reserved for later."""

import uuid
from abc import ABC, abstractmethod
from pathlib import Path

from app.config import settings


class StorageBackend(ABC):
    @abstractmethod
    async def save(self, data: bytes, directory: str, extension: str) -> str: ...
    @abstractmethod
    async def get_path(self, key: str) -> str: ...
    @abstractmethod
    async def delete(self, key: str) -> None: ...


class LocalStorage(StorageBackend):
    def __init__(self, root: str | None = None):
        self.root = Path(root or settings.MEDIA_ROOT)
        self.root.mkdir(parents=True, exist_ok=True)

    async def save(self, data: bytes, directory: str, extension: str) -> str:
        subdir = self.root / directory
        subdir.mkdir(parents=True, exist_ok=True)
        filename = f"{uuid.uuid4().hex}.{extension.lstrip('.')}"
        filepath = subdir / filename
        filepath.write_bytes(data)
        return str(filepath.relative_to(self.root))

    async def get_path(self, key: str) -> str:
        return str(self.root / key)

    async def delete(self, key: str) -> None:
        filepath = self.root / key
        if filepath.exists():
            filepath.unlink()


storage = LocalStorage()
