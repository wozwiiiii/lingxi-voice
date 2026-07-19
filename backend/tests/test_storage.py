"""TDD tests for storage abstraction and audio utilities."""

import tempfile
from pathlib import Path

import pytest

from app.utils.storage import LocalStorage


@pytest.fixture
def storage():
    tmp = tempfile.mkdtemp()
    s = LocalStorage(root=tmp)
    yield s
    # Cleanup
    import shutil
    shutil.rmtree(tmp, ignore_errors=True)


class TestLocalStorage:
    @pytest.mark.asyncio
    async def test_save_returns_relative_path(self, storage):
        data = b"test audio bytes"
        rel_path = await storage.save(data, "audio", "mp3")
        # On Windows, path separators might differ; normalize
        rel_path = rel_path.replace("\\", "/")
        assert "audio/" in rel_path
        assert rel_path.endswith(".mp3")

    @pytest.mark.asyncio
    async def test_save_and_get_path(self, storage):
        data = b"hello world"
        rel_path = await storage.save(data, "uploads", "wav")
        abs_path = await storage.get_path(rel_path)
        assert Path(abs_path).exists()
        assert Path(abs_path).read_bytes() == data

    @pytest.mark.asyncio
    async def test_delete_removes_file(self, storage):
        data = b"to be deleted"
        rel_path = await storage.save(data, "tmp", "mp3")
        abs_path = await storage.get_path(rel_path)
        assert Path(abs_path).exists()

        await storage.delete(rel_path)
        assert not Path(abs_path).exists()

    @pytest.mark.asyncio
    async def test_delete_nonexistent_no_error(self, storage):
        await storage.delete("nonexistent/file.mp3")

    @pytest.mark.asyncio
    async def test_save_creates_subdirectories(self, storage):
        data = b"nested file"
        rel_path = await storage.save(data, "deep/nested/path", "txt")
        abs_path = await storage.get_path(rel_path)
        assert Path(abs_path).exists()

    @pytest.mark.asyncio
    async def test_save_unique_filenames(self, storage):
        """Each save should produce a unique filename."""
        paths = set()
        for _ in range(10):
            p = await storage.save(b"data", "test", "mp3")
            paths.add(p)
        assert len(paths) == 10  # All unique
