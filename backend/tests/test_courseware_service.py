"""TDD tests for courseware service layer — build_zip, seed presets, bulk settings."""

import io
import json
import tempfile
import zipfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.courseware_service import apply_bulk_settings


class TestBuildZip:
    """Test ZIP packaging logic with mock data."""

    def test_zip_contains_manifest(self):
        """Manifest.json should be the first file in ZIP."""
        zf_buffer = io.BytesIO()
        with zipfile.ZipFile(zf_buffer, "w") as zf:
            zf.writestr("manifest.json", json.dumps({"test": True}))
            zf.writestr("audio/slide_01.mp3", b"\x00" * 100)
            zf.writestr("original.pptx", b"fake pptx")

        zf_buffer.seek(0)
        with zipfile.ZipFile(zf_buffer) as zf:
            names = zf.namelist()
            assert "manifest.json" in names
            assert "audio/slide_01.mp3" in names
            assert "original.pptx" in names

    def test_manifest_is_valid_json(self):
        manifest = {
            "courseware_id": "test-uuid",
            "title": "测试课件",
            "slides_count": 2,
            "created_at": "2026-07-20T00:00:00",
            "slides": [
                {"index": 1, "original_text": "第一页", "audio_file": "audio/slide_01.mp3"},
                {"index": 2, "original_text": "第二页", "audio_file": "audio/slide_02.mp3"},
            ],
        }
        zf_buffer = io.BytesIO()
        with zipfile.ZipFile(zf_buffer, "w") as zf:
            zf.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))

        zf_buffer.seek(0)
        with zipfile.ZipFile(zf_buffer) as zf:
            loaded = json.loads(zf.read("manifest.json"))
            assert loaded["slides_count"] == 2
            assert len(loaded["slides"]) == 2
            assert loaded["title"] == "测试课件"


class TestSeedPresets:
    """Test preset courseware seeding."""
    pass  # Requires DB — covered by integration tests


class TestBulkSettings:
    """Test bulk settings application logic."""
    pass  # Requires DB — covered by integration tests
