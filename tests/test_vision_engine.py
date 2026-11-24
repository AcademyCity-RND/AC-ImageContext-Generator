"""Tests for VisionEngine.generate_course_inisiasi (Fase 0 — V10/V11).

TDD: each test describes the required behaviour; implementation comes after
the test is seen failing.
"""
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from PIL import Image

from src.vision_engine import VisionEngine


class FakeKnowledgeManager:
    """Records how build_course_context was called — no PDF/API work."""

    def __init__(self, context="KONTEKS KEPL DUMMY"):
        self.context = context
        self.calls = []

    def build_course_context(self, course_id, reference_dir=None):
        self.calls.append({"course_id": course_id, "reference_dir": reference_dir})
        return self.context


def _make_engine(response_text="Setup Docker | Konteks: Dockerfile multi-stage | Arah: CI/CD pipeline"):
    """Build a VisionEngine with a deterministic fake model (no real API)."""
    engine = VisionEngine.__new__(VisionEngine)
    engine.api_key = "***"
    engine.model_name = "models/test"
    fake_response = MagicMock()
    fake_response.text = response_text
    engine.model = MagicMock()
    engine.model.generate_content.return_value = fake_response
    return engine


def _make_screenshots(directory, names=("1", "2", "3")):
    directory.mkdir(parents=True, exist_ok=True)
    paths = []
    for name in names:
        path = directory / f"{name}.png"
        Image.new("RGB", (8, 8), color=(10, 20, 30)).save(path)
        paths.append(path)
    return paths


# ---------------------------------------------------------------------------
# RED 1 — method exists and produces one output line per screenshot
# ---------------------------------------------------------------------------
def test_generate_course_inisiasi_creates_one_line_per_screenshot(tmp_path):
    shots = tmp_path / "screenshots"
    _make_screenshots(shots)
    out = tmp_path / "inisiasi" / "Per4.txt"

    engine = _make_engine()
    result = engine.generate_course_inisiasi(
        course_id="kepl",
        screenshots_dir=str(shots),
        knowledge_manager=FakeKnowledgeManager(),
        output_file=str(out),
    )

    assert result == {"total": 3, "generated": 3, "errors": 0}
    text = out.read_text(encoding="utf-8")
    for idx in (1, 2, 3):
        assert f"{idx}.png | Setup Docker" in text


# ---------------------------------------------------------------------------
# RED 2 — reference_dir is passed through to build_course_context (V11)
# ---------------------------------------------------------------------------
def test_generate_course_inisiasi_passes_reference_dir_to_context(tmp_path):
    shots = tmp_path / "screenshots"
    _make_screenshots(shots, names=("1",))
    ref_dir = tmp_path / "_reference"
    ref_dir.mkdir()
    km = FakeKnowledgeManager()

    engine = _make_engine()
    engine.generate_course_inisiasi(
        course_id="kepl",
        screenshots_dir=str(shots),
        knowledge_manager=km,
        output_file=str(tmp_path / "inisiasi" / "Per4.txt"),
        reference_dir=str(ref_dir),
    )

    assert len(km.calls) == 1
    assert km.calls[0]["course_id"] == "kepl"
    assert km.calls[0]["reference_dir"] == str(ref_dir)


# ---------------------------------------------------------------------------
# RED 3 — resume skips screenshots already present in the output file
# ---------------------------------------------------------------------------
def test_generate_course_inisiasi_skips_cached_entries_on_resume(tmp_path):
    shots = tmp_path / "screenshots"
    _make_screenshots(shots)
    out = tmp_path / "inisiasi" / "Per4.txt"
    out.parent.mkdir(parents=True)
    out.write_text("# old header\n1.png | cached line | Konteks: lama | Arah: lama\n", encoding="utf-8")

    engine = _make_engine()
    result = engine.generate_course_inisiasi(
        course_id="kepl",
        screenshots_dir=str(shots),
        knowledge_manager=FakeKnowledgeManager(),
        output_file=str(out),
    )

    assert result == {"total": 3, "generated": 3, "errors": 0}
    assert engine.model.generate_content.call_count == 2
    text = out.read_text(encoding="utf-8")
    assert "1.png | cached line" in text
    assert "2.png | Setup Docker" in text
    assert "3.png | Setup Docker" in text


# ---------------------------------------------------------------------------
# RED 4 — empty folder is handled without crashing
# ---------------------------------------------------------------------------
def test_generate_course_inisiasi_handles_empty_folder(tmp_path):
    shots = tmp_path / "screenshots"
    shots.mkdir()
    out = tmp_path / "inisiasi" / "Per4.txt"

    engine = _make_engine()
    result = engine.generate_course_inisiasi(
        course_id="kepl",
        screenshots_dir=str(shots),
        knowledge_manager=FakeKnowledgeManager(),
        output_file=str(out),
    )

    assert result == {"total": 0, "generated": 0, "errors": 0}
    assert not out.exists()


# ---------------------------------------------------------------------------
# RED 5 — V11 DoD: auto-discover workspace/<COURSE>/_reference
# ---------------------------------------------------------------------------
def test_generate_course_inisiasi_autodiscovers_reference_dir(tmp_path):
    shots = tmp_path / "KEPL" / "screenshots" / "Per4"
    _make_screenshots(shots)
    ref = tmp_path / "KEPL" / "_reference"
    ref.mkdir(parents=True)
    out = tmp_path / "KEPL" / "inisiasi" / "Per4.txt"

    km = FakeKnowledgeManager()
    engine = _make_engine()
    engine.generate_course_inisiasi(
        course_id="kepl",
        screenshots_dir=str(shots),
        knowledge_manager=km,
        output_file=str(out),
    )

    assert km.calls[0]["reference_dir"] == str(ref)


def test_generate_course_inisiasi_no_fake_reference_when_missing(tmp_path):
    shots = tmp_path / "KEPL" / "screenshots" / "Per4"
    _make_screenshots(shots)
    out = tmp_path / "KEPL" / "inisiasi" / "Per4.txt"

    km = FakeKnowledgeManager()
    engine = _make_engine()
    engine.generate_course_inisiasi(
        course_id="kepl",
        screenshots_dir=str(shots),
        knowledge_manager=km,
        output_file=str(out),
    )

    assert km.calls[0]["reference_dir"] is None
