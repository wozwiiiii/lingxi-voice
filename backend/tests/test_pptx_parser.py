import zipfile

import pytest
from pathlib import Path

from app.services.pptx_parser import parse_pptx

FIXTURES = Path(__file__).parent / "fixtures"
SAMPLE = FIXTURES / "sample.pptx"


@pytest.fixture(scope="module")
def sample_pptx():
    if not SAMPLE.exists():
        pytest.skip("sample.pptx not generated — run tests/fixtures/generate_sample.py")
    return str(SAMPLE)


class TestPPTXParse:
    def test_parses_slides_count(self, sample_pptx):
        result = parse_pptx(sample_pptx, "test.pptx")
        assert result.slides_count > 0

    def test_extracts_text(self, sample_pptx):
        result = parse_pptx(sample_pptx, "test.pptx")
        assert len(result.slides) > 0
        texts = [s.text for s in result.slides if s.text]
        assert len(texts) > 0

    def test_title_from_filename(self, sample_pptx):
        result = parse_pptx(sample_pptx, "我的课件.pptx")
        assert result.title == "我的课件"

    def test_bad_file_raises(self):
        with pytest.raises(ValueError):
            parse_pptx("/nonexistent/file.pptx")

    def test_slide_indices_are_1_based(self, sample_pptx):
        result = parse_pptx(sample_pptx, "test.pptx")
        for slide in result.slides:
            assert slide.index >= 1


class TestZIPBombDefense:
    def test_rejects_oversized_zip(self, tmp_path):
        bomb = tmp_path / "bomb.pptx"
        with zipfile.ZipFile(bomb, "w") as zf:
            info = zipfile.ZipInfo("huge.bin")
            info.file_size = 200 * 1024 * 1024  # 200MB
            zf.writestr(info, "x" * 100)
            # writestr resets file_size; restore it for the central directory
            info.file_size = 200 * 1024 * 1024
        with pytest.raises(ValueError, match="过大"):
            parse_pptx(str(bomb))
