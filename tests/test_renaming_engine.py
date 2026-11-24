"""Tests for the F1 ICG-Renaming engine (V12–V15).

TDD: each test describes required behaviour and must be seen failing before
the corresponding implementation exists.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from PIL import Image

from src.renaming_engine import (
    ModuleStep,
    RenameMapping,
    RenamingPlan,
    assign_final_names,
    build_renaming_plan,
    dedup_screenshots,
    extract_module_steps,
    extract_steps_from_pdf,
    extract_steps_from_pptx,
    hash_file,
    perceptual_hash,
)


def _make_image(path: Path, color=(10, 20, 30), size=(16, 16)) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", size, color=color).save(path)
    return path


# ---------------------------------------------------------------------------
# RED 1 — PDF/PPTX step extraction returns ordered ModuleStep list
# ---------------------------------------------------------------------------
def test_extract_steps_from_pdf_detects_numbered_steps_and_task_sections(tmp_path):
    """PDF text with '1. Setup' lines and a 'Tugas' section yields ordered steps."""
    import fitz

    pdf_path = tmp_path / "modul.pdf"
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((50, 50), "Pertemuan 5 — Docker")
    page.insert_text((50, 80), "1. Setup Docker")
    page.insert_text((50, 110), "2. Dockerfile Builder")
    page.insert_text((50, 140), "3. Build & Run")
    page.insert_text((50, 170), "Tugas: Deploy ke Railway")
    doc.save(pdf_path)
    doc.close()

    steps = extract_steps_from_pdf(pdf_path)

    assert [s.title for s in steps] == [
        "Setup Docker",
        "Dockerfile Builder",
        "Build & Run",
        "Deploy ke Railway",
    ]
    assert steps[-1].is_task is True
    assert all(isinstance(s, ModuleStep) for s in steps)


def test_extract_steps_from_pptx_uses_slide_titles(tmp_path):
    """PPTX slide titles become an ordered list of steps."""
    from pptx import Presentation

    pptx_path = tmp_path / "modul.pptx"
    prs = Presentation()
    for title in ("Setup Docker", "Dockerfile Builder", "Tugas: Deploy"):
        slide = prs.slides.add_slide(prs.slide_layouts[5])
        slide.shapes.title.text = title
    prs.save(pptx_path)

    steps = extract_steps_from_pptx(pptx_path)

    assert [s.title for s in steps] == ["Setup Docker", "Dockerfile Builder", "Deploy"]
    assert steps[-1].is_task is True


def test_extract_module_steps_dispatches_by_extension(tmp_path):
    """extract_module_steps picks the right extractor for PDF and PPTX."""
    pdf = tmp_path / "a.pdf"
    pptx = tmp_path / "b.pptx"
    pdf.touch()
    pptx.touch()

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr("src.renaming_engine.extract_steps_from_pdf", lambda p: [ModuleStep("PDF", False)])
        mp.setattr("src.renaming_engine.extract_steps_from_pptx", lambda p: [ModuleStep("PPTX", False)])
        assert [s.title for s in extract_module_steps(pdf)] == ["PDF"]
        assert [s.title for s in extract_module_steps(pptx)] == ["PPTX"]


# ---------------------------------------------------------------------------
# RED 2 — dedup by exact hash
# ---------------------------------------------------------------------------
def test_hash_file_returns_sha256_hex(tmp_path):
    p = _make_image(tmp_path / "x.png")
    expected = hashlib.sha256(p.read_bytes()).hexdigest()
    assert hash_file(p) == expected


def test_dedup_removes_exact_hash_duplicates_keeping_first(tmp_path):
    a = _make_image(tmp_path / "a.png", color=(1, 2, 3))
    b = _make_image(tmp_path / "b.png", color=(1, 2, 3))  # byte-identical
    c = _make_image(tmp_path / "c.png", color=(9, 9, 9))

    unique, duplicates = dedup_screenshots([a, b, c])

    assert unique == [a, c]
    assert len(duplicates) == 1
    assert duplicates[0]["kept"] == a
    assert duplicates[0]["removed"] == b
    assert duplicates[0]["reason"] == "hash"


# ---------------------------------------------------------------------------
# RED 3 — dedup by visual similarity (pHash), keeping newest version
# ---------------------------------------------------------------------------
def test_perceptual_hash_is_stable_for_identical_images(tmp_path):
    a = _make_image(tmp_path / "a.png", color=(40, 90, 130))
    b = _make_image(tmp_path / "b.png", color=(40, 90, 130))
    assert perceptual_hash(a) == perceptual_hash(b)


def test_dedup_removes_near_duplicate_by_phash_and_keeps_newer(tmp_path):
    import os
    import time

    older = _make_image(tmp_path / "older.png", color=(40, 90, 130))
    newer = _make_image(tmp_path / "newer.png", color=(40, 90, 130))
    # Make byte content different so hash-dedup does not catch it.
    Image.new("RGB", (17, 17), color=(40, 90, 130)).save(newer)
    now = time.time()
    os.utime(older, (now - 1000, now - 1000))
    os.utime(newer, (now, now))

    unique, duplicates = dedup_screenshots([older, newer], phash_threshold=0)

    assert unique == [newer]
    assert duplicates[0]["reason"] == "phash"
    assert duplicates[0]["kept"] == newer
    assert duplicates[0]["removed"] == older


# ---------------------------------------------------------------------------
# RED 4 — naming scheme (V14/V15)
# ---------------------------------------------------------------------------
def test_assign_names_single_screenshot_per_regular_step():
    steps = [ModuleStep("Setup", False), ModuleStep("Build", False)]
    groups = [(steps[0], ["s1.png"]), (steps[1], ["s2.png"])]

    mappings = assign_final_names(groups)

    assert [(m.final_name, m.step_index) for m in mappings] == [
        ("1.png", 1),
        ("2.png", 2),
    ]


def test_assign_names_multiple_screenshots_use_letter_suffix():
    steps = [ModuleStep("Setup", False)]
    groups = [(steps[0], ["a.png", "b.png", "c.png"])]

    mappings = assign_final_names(groups)

    assert [m.final_name for m in mappings] == ["1a.png", "1b.png", "1c.png"]


def test_assign_names_task_steps_get_t_prefix_and_multi_task_numbering():
    steps = [
        ModuleStep("Setup", False),
        ModuleStep("Tugas Deploy", True),
        ModuleStep("Tugas Deploy Lanjutan", True),
    ]
    groups = [
        (steps[0], ["s1.png"]),
        (steps[1], ["t1.png"]),
        (steps[2], ["t2a.png", "t2b.png"]),
    ]

    mappings = assign_final_names(groups)

    assert [m.final_name for m in mappings] == [
        "1.png",
        "T1.png",
        "T2-1.png",
        "T2-2.png",
    ]


# ---------------------------------------------------------------------------
# RED 5 — build plan with ACC gate (no writes until commit)
# ---------------------------------------------------------------------------
def _classifier_from(steps):
    """Return a deterministic classifier mapping filename -> step title."""
    def classify(path, candidates):
        name = Path(path).stem
        for i, step in enumerate(candidates):
            if name.startswith(step.title.split()[0].lower()):
                return i + 1, 0.99
        return 0, 0.1
    return classify


def test_build_plan_produces_mapping_without_writing_output(tmp_path):
    raw = tmp_path / "gambar_raw"
    ref = tmp_path / "_reference"
    out = tmp_path / "gambar"
    _make_image(raw / "setup.png", color=(10, 20, 30))
    _make_image(raw / "build.png", color=(40, 50, 60))
    pdf = tmp_path / "modul.pdf"
    pdf.write_bytes(b"%PDF-1.4 fake")
    ref.mkdir()

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(
            "src.renaming_engine.extract_module_steps",
            lambda d: [ModuleStep("Setup", False), ModuleStep("Build", False)],
        )
        plan = build_renaming_plan(
            source_dir=raw,
            reference_dir=ref,
            output_dir=out,
            classifier=_classifier_from(None),
        )

    assert isinstance(plan, RenamingPlan)
    assert len(plan.mappings) == 2
    assert {m.final_name for m in plan.mappings} == {"1.png", "2.png"}
    assert not out.exists(), "ACC gate: no output written before commit()"


def test_commit_writes_files_and_report_after_acc(tmp_path):
    raw = tmp_path / "gambar_raw"
    ref = tmp_path / "_reference"
    out = tmp_path / "gambar"
    src = _make_image(raw / "setup.png")
    ref.mkdir()

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(
            "src.renaming_engine.extract_module_steps",
            lambda d: [ModuleStep("Setup", False)],
        )
        plan = build_renaming_plan(
            source_dir=raw,
            reference_dir=ref,
            output_dir=out,
            classifier=lambda p, s: (1, 0.99),
        )
        plan.commit()

    assert (out / "1.png").exists()
    assert (out / "renaming_report.txt").exists()
    assert src.exists(), "source file must not be removed (copy, not rename in-place)"


def test_commit_creates_unmatched_folder_and_copies_unmatched(tmp_path):
    raw = tmp_path / "gambar_raw"
    ref = tmp_path / "_reference"
    out = tmp_path / "gambar"
    matched_src = _make_image(raw / "matched.png", color=(10, 20, 30))
    unmatched_src = _make_image(raw / "unmatched.png", color=(40, 50, 60))
    ref.mkdir()

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(
            "src.renaming_engine.extract_module_steps",
            lambda d: [ModuleStep("Setup", False)],
        )
        plan = build_renaming_plan(
            source_dir=raw,
            reference_dir=ref,
            output_dir=out,
            classifier=lambda p, s: (1, 0.99) if p.name == "matched.png" else (0, 0.1),
        )
        plan.commit()

    assert (out / "1.png").exists()
    assert (out / "unmatched" / "unmatched.png").exists()
    assert unmatched_src.exists(), "source file must not be removed"
    # Report should mention unmatched
    report = (out / "renaming_report.txt").read_text(encoding="utf-8")
    assert "UNMATCHED" in report
    assert "unmatched.png" in report


def test_fallback_without_reference_sorts_by_mtime(tmp_path):
    import os
    import time

    raw = tmp_path / "gambar_raw"
    out = tmp_path / "gambar"
    # Use different colors so they are NOT considered near-duplicates
    first = _make_image(raw / "zzz.png", color=(10, 20, 30))
    second = _make_image(raw / "aaa.png", color=(40, 50, 60))
    now = time.time()
    os.utime(first, (now - 100, now - 100))
    os.utime(second, (now, now))

    plan = build_renaming_plan(
        source_dir=raw,
        reference_dir=None,
        output_dir=out,
        classifier=None,
    )

    assert plan.mode == "mtime-fallback"
    assert [m.final_name for m in plan.mappings] == ["1.png", "2.png"]
    assert plan.mappings[0].source_path == first
    assert plan.mappings[1].source_path == second


def test_fallback_mode_deduplicates_exact_hash_duplicates(tmp_path):
    """Fallback mode must run exact-hash dedup (V13: Dedup hash + visual similarity unconditionally)."""
    raw = tmp_path / "gambar_raw"
    out = tmp_path / "gambar"
    # Two byte-identical images with different names
    a = _make_image(raw / "img_a.png", color=(10, 20, 30))
    b = _make_image(raw / "img_b.png", color=(10, 20, 30))  # exact duplicate
    c = _make_image(raw / "img_c.png", color=(99, 99, 99))  # unique

    plan = build_renaming_plan(
        source_dir=raw,
        reference_dir=None,
        output_dir=out,
        classifier=None,
    )

    # Should only have 2 mappings (one duplicate removed)
    assert len(plan.mappings) == 2
    assert len(plan.duplicates) == 1
    assert plan.duplicates[0]["reason"] == "hash"
    final_names = {m.final_name for m in plan.mappings}
    assert final_names == {"1.png", "2.png"}


def test_fallback_mode_deduplicates_near_duplicates_by_phash(tmp_path):
    """Fallback mode should also run perceptual hash dedup, keeping newest."""
    import os
    import time

    raw = tmp_path / "gambar_raw"
    out = tmp_path / "gambar"

    # Create near-duplicates (same visual content, different byte content)
    older = _make_image(raw / "older.png", color=(40, 90, 130))
    newer = _make_image(raw / "newer.png", color=(40, 90, 130))
    # Make byte content different so hash-dedup doesn't catch it
    Image.new("RGB", (17, 17), color=(40, 90, 130)).save(newer)

    now = time.time()
    os.utime(older, (now - 1000, now - 1000))
    os.utime(newer, (now, now))

    plan = build_renaming_plan(
        source_dir=raw,
        reference_dir=None,
        output_dir=out,
        classifier=None,
    )

    # Should only have 1 mapping (phash dedup removed older)
    assert len(plan.mappings) == 1
    assert plan.mappings[0].source_path == newer
    assert len(plan.duplicates) == 1
    assert plan.duplicates[0]["reason"] == "phash"
    assert plan.duplicates[0]["kept"] == newer
    assert plan.duplicates[0]["removed"] == older


def test_reference_mode_dedup_within_steps_still_works(tmp_path):
    """Regression test: reference mode dedup should still work per-step."""
    raw = tmp_path / "gambar_raw"
    ref = tmp_path / "_reference"
    out = tmp_path / "gambar"

    # Two exact duplicates in same step
    a = _make_image(raw / "step1_a.png", color=(1, 2, 3))
    b = _make_image(raw / "step1_b.png", color=(1, 2, 3))
    # One in another step
    c = _make_image(raw / "step2.png", color=(9, 9, 9))

    ref.mkdir()

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(
            "src.renaming_engine.extract_module_steps",
            lambda d: [ModuleStep("Step 1", False), ModuleStep("Step 2", False)],
        )
        plan = build_renaming_plan(
            source_dir=raw,
            reference_dir=ref,
            output_dir=out,
            classifier=lambda p, s: (1, 0.99) if "step1" in p.name else (2, 0.99) if "step2" in p.name else (0, 0.1),
        )

    # Should have 2 mappings (step1_a and step2), one duplicate removed from step1
    assert len(plan.mappings) == 2
    assert len(plan.duplicates) == 1
    assert plan.duplicates[0]["reason"] == "hash"
    final_names = {m.final_name for m in plan.mappings}
    assert final_names == {"1.png", "2.png"}


def test_natural_sort_in_summary_rows_orders_numerically(tmp_path):
    """ACC table must sort 2.png before 10.png (not lexicographic)."""
    plan = RenamingPlan()
    for name in ["1.png", "2.png", "10.png", "11.png", "3.png"]:
        plan.mappings.append(
            RenameMapping(
                source_path=Path(f"raw_{name}"),
                final_name=name,
                step_index=int(name.split(".")[0]),
                step_title="Test",
            )
        )

    rows = plan.summary_rows()
    final_names = [row[1] for row in rows]

    assert final_names == ["1.png", "2.png", "3.png", "10.png", "11.png"]


def test_render_report_natural_sort(tmp_path):
    """Report mappings must also use natural sort order."""
    plan = RenamingPlan()
    for name in ["1.png", "2.png", "10.png", "3.png"]:
        plan.mappings.append(
            RenameMapping(
                source_path=Path(f"raw_{name}"),
                final_name=name,
                step_index=int(name.split(".")[0]),
                step_title="Test",
            )
        )

    report = plan.render_report()
    # Check that 2.png appears before 10.png
    assert report.index("2.png <-") < report.index("10.png <-")


def test_e2e_cli_rename_fallback_mode_shows_plan_and_aborts(tmp_path, monkeypatch):
    """E2E: CLI rename in fallback mode shows ACC table and aborts on 'n'."""
    import subprocess
    import sys

    # Project root for PYTHONPATH (so subprocess can import src.cli)
    project_root = Path(__file__).resolve().parent.parent

    # Setup: create test images in standard ICG layout
    course = "kepl"
    meeting = "Per4"
    workspace = tmp_path / "workspace"
    screenshots_dir = workspace / course / "screenshots" / meeting
    screenshots_dir.mkdir(parents=True)

    # Create a few test images with different colors
    Image.new("RGB", (100, 100), color=(10, 20, 30)).save(screenshots_dir / "screen1.png")
    Image.new("RGB", (100, 100), color=(40, 50, 60)).save(screenshots_dir / "screen2.png")

    # Run CLI rename command with fallback mode (no reference-dir)
    # Simulate user answering 'n' to ACC prompt
    cmd = [
        sys.executable,
        "-m",
        "src.cli",
        "rename",
        "-c",
        course,
        "-p",
        meeting,
        "-w",
        str(workspace),
    ]

    import os

    env = {**os.environ, "PYTHONPATH": str(project_root)}

    proc = subprocess.run(
        cmd,
        input="n\n",
        text=True,
        capture_output=True,
        cwd=tmp_path,
        env=env,
        timeout=30,
    )

    # Should show ACC table
    assert "Renaming Plan" in proc.stdout
    assert "screen1.png" in proc.stdout
    assert "screen2.png" in proc.stdout
    assert "1.png" in proc.stdout
    assert "2.png" in proc.stdout
    assert "Duplicates removed: 0" in proc.stdout
    assert "Unmatched: 0" in proc.stdout
    # Should show ACC prompt
    assert "Approve and write renamed images" in proc.stdout
    # Should abort (exit code 1)
    assert proc.returncode == 1
    # No output directory should be created
    out_dir = workspace / course / "gambar" / meeting
    assert not out_dir.exists()


def test_e2e_cli_rename_fallback_mode_writes_on_approve(tmp_path, monkeypatch):
    """E2E: CLI rename in fallback mode writes images when user approves."""
    import subprocess
    import sys
    import os

    # Project root for PYTHONPATH (so subprocess can import src.cli)
    project_root = Path(__file__).resolve().parent.parent

    course = "kepl"
    meeting = "Per4"
    workspace = tmp_path / "workspace"
    screenshots_dir = workspace / course / "screenshots" / meeting
    screenshots_dir.mkdir(parents=True)

    Image.new("RGB", (100, 100), color=(10, 20, 30)).save(screenshots_dir / "screen1.png")
    Image.new("RGB", (100, 100), color=(40, 50, 60)).save(screenshots_dir / "screen2.png")

    cmd = [
        sys.executable,
        "-m",
        "src.cli",
        "rename",
        "-c",
        course,
        "-p",
        meeting,
        "-w",
        str(workspace),
    ]

    env = {**os.environ, "PYTHONPATH": str(project_root)}

    # Simulate user answering 'y' to ACC prompt
    proc = subprocess.run(
        cmd,
        input="y\n",
        text=True,
        capture_output=True,
        cwd=tmp_path,
        env=env,
        timeout=30,
    )

    assert proc.returncode == 0
    assert "Renaming complete" in proc.stdout
    out_dir = workspace / course / "gambar" / meeting
    assert out_dir.exists()
    assert (out_dir / "1.png").exists()
    assert (out_dir / "2.png").exists()
    assert (out_dir / "renaming_report.txt").exists()
    # Verify report content
    report = (out_dir / "renaming_report.txt").read_text(encoding="utf-8")
    assert "mtime-fallback" in report
    assert "1.png <-" in report
    assert "2.png <-" in report


# End of test file marker
