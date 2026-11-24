"""ICG-ContextGenerate (F2) acceptance tests — TDD RED first.

Covers the full F2 contract from plan.md:
- Pass 1 visual census -> narrative sections + order + pairing
- Pass 2 context generation -> enriched line per image
- Enriched serializer (@section, type=, group=)
- Legacy inisiasi.txt parser (backward compat E6)
- ACC gate + auto-save/resume via .icg_cache/pending_inisiasi.txt

No live network — the vision model is always faked.
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest
from PIL import Image

from src.context_engine import (
    AccRequiredError,
    ContextEngine,
    NarrativePlan,
    parse_inisiasi,
    parse_narrative_plan,
    reconcile_order,
    sanitize_ai_line,
    serialize_enriched_document,
    serialize_enriched_line,
    sort_image_name,
)


# ---------------------------------------------------------------------------
# fixtures / helpers
# ---------------------------------------------------------------------------
def _fake_model(responses: list[str]) -> MagicMock:
    """Vision model whose generate_content returns queued .text responses."""
    model = MagicMock()
    side_effects = []
    for text in responses:
        resp = MagicMock()
        resp.text = text
        side_effects.append(resp)
    model.generate_content.side_effect = side_effects
    return model


def _make_images(directory: Path, names: tuple[str, ...] = ("1.png", "2.png", "9.png", "10.png")):
    directory.mkdir(parents=True, exist_ok=True)
    for name in names:
        Image.new("RGB", (8, 8), color=(20, 40, 60)).save(directory / name)
    return [directory / n for n in names]


PASS1_RESPONSE = """[SECTION] S1 | Konfigurasi Layanan & Orkestrasi Docker
[SECTION] S2 | Observability, Logging & Health Checking
[ORDER] 1.png | 2.png | 9.png | 10.png
[GROUP] S1: 1.png, 2.png
[GROUP] S2: 9.png, 10.png
[PAIR] 9.png:10.png
"""

PASS2_RESPONSES = [
    "type=config | Inisialisasi Monorepo | Konteks: Setup Laravel 11 dan Vue 3 | Arah: CI/CD pipeline",
    "type=code | Dockerfile Builder | Konteks: Dockerfile multi-stage | Arah: optimasi image",
    "type=terminal | Log terstruktur INFO | Konteks: artisan logs menampilkan transaksi | Arah: structured logging",
    "type=gui | Dashboard monitoring | Konteks: container healthy di Docker Desktop | Arah: verifikasi log CLI",
]


# ---------------------------------------------------------------------------
# RED 1 — legacy parser (backward compat, E6)
# ---------------------------------------------------------------------------
def test_parse_inisiasi_reads_manual_freeform_notes():
    text = (
        "# catatan bebas\n"
        "1 deploy.sh\n"
        "2.png | Setup Docker | Konteks: multi-stage | Arah: CI/CD\n"
    )
    doc = parse_inisiasi(text)
    assert doc.mode == "legacy"
    assert len(doc.lines) == 2
    assert doc.lines[0].raw == "1 deploy.sh"
    assert doc.lines[1].filename == "2.png"
    assert doc.lines[1].label == "Setup Docker"


# ---------------------------------------------------------------------------
# RED 2 — enriched parser (dual mode V4 / F2)
# ---------------------------------------------------------------------------
def test_parse_inisiasi_reads_enriched_format():
    text = (
        "# ========================================================\n"
        "[@section] S1 | Konfigurasi Layanan\n"
        "[@section] S2 | Observability\n"
        "1.png | S1 | type=config | group=single | Inisialisasi Monorepo | "
        "Konteks: Setup Laravel | Arah: CI/CD pipeline\n"
        "9.png  | S2 | type=terminal | group=pair:10 | Log INFO | "
        "Konteks: artisan logs | Arah: structured logging\n"
    )
    doc = parse_inisiasi(text)
    assert doc.mode == "enriched"
    assert [s.id for s in doc.sections] == ["S1", "S2"]
    assert doc.sections[0].title == "Konfigurasi Layanan"
    line = doc.lines[0]
    assert line.filename == "1.png"
    assert line.section == "S1"
    assert line.type == "config"
    assert line.group == "single"
    assert line.label == "Inisialisasi Monorepo"
    assert line.konteks == "Setup Laravel"
    assert line.arah == "CI/CD pipeline"
    assert doc.lines[1].group == "pair:10"


# ---------------------------------------------------------------------------
# RED 3 — enriched serializer contract (V17)
# ---------------------------------------------------------------------------
def test_serialize_enriched_line_matches_contract():
    line = parse_inisiasi(
        "1.png | S1 | type=config | group=single | Inisialisasi Monorepo | "
        "Konteks: Setup Laravel | Arah: CI/CD pipeline\n"
    ).lines[0]
    assert serialize_enriched_line(line) == (
        "1.png | S1 | type=config | group=single | Inisialisasi Monorepo | "
        "Konteks: Setup Laravel | Arah: CI/CD pipeline"
    )


def test_serialize_enriched_document_includes_header_and_sections():
    plan = parse_narrative_plan(PASS1_RESPONSE)
    lines = parse_inisiasi(
        "1.png | S1 | type=config | group=single | A | Konteks: a | Arah: b\n"
    ).lines
    doc = serialize_enriched_document(
        lines=lines, sections=plan.sections, course="KEPL", meeting="UTS", total=1, mode="director"
    )
    assert "# INISIASI: KEPL — UTS" in doc
    assert "# ENGINE: image-context v0.3 | MODE: director" in doc
    assert "# TOTAL: 1 gambar" in doc
    assert "[@section] S1 | Konfigurasi Layanan & Orkestrasi Docker" in doc
    assert doc.rstrip().endswith("# ========================================================")


# ---------------------------------------------------------------------------
# RED 4 — natural sort (1, 1a, 2, 9, 10, T1, T1-1)
# ---------------------------------------------------------------------------
def test_sort_image_name_orders_numeric_then_letter_then_task():
    names = ["T1.png", "10.png", "1a.png", "2.png", "1.png", "T1-1.png", "9.png"]
    assert sorted(names, key=sort_image_name) == [
        "1.png", "1a.png", "2.png", "9.png", "10.png", "T1.png", "T1-1.png",
    ]


# ---------------------------------------------------------------------------
# RED 5 — narrative plan parser (Pass 1, V16)
# ---------------------------------------------------------------------------
def test_parse_narrative_plan_extracts_sections_order_and_pairs():
    plan = parse_narrative_plan(PASS1_RESPONSE)
    assert [s.id for s in plan.sections] == ["S1", "S2"]
    assert plan.sections[1].title == "Observability, Logging & Health Checking"
    assert plan.order == ["1.png", "2.png", "9.png", "10.png"]
    assert plan.pairs == {"9.png": "10.png", "10.png": "9.png"}
    assert plan.image_sections == {"1.png": "S1", "2.png": "S1", "9.png": "S2", "10.png": "S2"}


# ---------------------------------------------------------------------------
# RED 6 — Pass 1 visual census sends ALL images in one call (V16)
# ---------------------------------------------------------------------------
def test_pass1_visual_census_sends_all_images_and_module_summary(tmp_path):
    imgs = _make_images(tmp_path / "gambar")
    model = _fake_model([PASS1_RESPONSE])
    engine = ContextEngine(model)
    plan = engine.visual_census(image_paths=imgs, module_summary="Modul Docker: setup, build, health")

    assert len(plan.sections) == 2
    assert model.generate_content.call_count == 1
    # args[0] = [prompt_text, img1, img2, img3, img4]
    args = model.generate_content.call_args.args[0]
    prompt_text = str(args[0])
    assert "Modul Docker" in prompt_text
    assert all(p.name in prompt_text for p in imgs)
    # N images passed as separate elements in the list
    assert len(args) == len(imgs) + 1


# ---------------------------------------------------------------------------
# RED 7 — Pass 2 generates one enriched line per image (E2)
# ---------------------------------------------------------------------------
def test_pass2_generates_one_enriched_line_per_image(tmp_path):
    imgs = _make_images(tmp_path / "gambar")
    plan = parse_narrative_plan(PASS1_RESPONSE)
    model = _fake_model(PASS2_RESPONSES)
    engine = ContextEngine(model)

    lines = engine.generate_context(image_paths=imgs, plan=plan, course_context="Konteks KEPL")

    assert len(lines) == 4
    assert [l.filename for l in lines] == ["1.png", "2.png", "9.png", "10.png"]
    assert [l.section for l in lines] == ["S1", "S1", "S2", "S2"]
    assert [l.type for l in lines] == ["config", "code", "terminal", "gui"]
    assert lines[2].group == "pair:10"
    assert lines[3].group == "pair:9"
    assert lines[0].group == "single"


# ---------------------------------------------------------------------------
# RED 8 — invalid type falls back, never poisons output (SEC-10 spirit)
# ---------------------------------------------------------------------------
def test_pass2_invalid_type_falls_back_to_config(tmp_path):
    imgs = _make_images(tmp_path / "gambar", ("1.png",))
    plan = NarrativePlan(
        sections=[], order=["1.png"], pairs={}, raw_response=""
    )
    model = _fake_model(["type=PAWNED | Label | Konteks: x | Arah: y"])
    engine = ContextEngine(model)
    lines = engine.generate_context(image_paths=imgs, plan=plan, course_context="")
    assert lines[0].type == "config"
    assert lines[0].group == "single"


# ---------------------------------------------------------------------------
# RED 9 — ACC gate: nothing final is written without approval
# ---------------------------------------------------------------------------
def test_commit_requires_acc_approval_before_writing_final(tmp_path):
    pending = tmp_path / ".icg_cache" / "pending_inisiasi.txt"
    final = tmp_path / "inisiasi.txt"
    pending.parent.mkdir(parents=True)
    pending.write_text("1.png | S1 | type=config | group=single | A | Konteks: a | Arah: b\n", encoding="utf-8")

    with pytest.raises(AccRequiredError):
        ContextEngine.commit_pending(pending, final, approved=False)
    assert not final.exists()
    assert pending.exists()


def test_commit_writes_final_after_approval(tmp_path):
    pending = tmp_path / ".icg_cache" / "pending_inisiasi.txt"
    final = tmp_path / "inisiasi.txt"
    pending.parent.mkdir(parents=True)
    pending.write_text("1.png | S1 | type=config | group=single | A | Konteks: a | Arah: b\n", encoding="utf-8")

    ContextEngine.commit_pending(pending, final, approved=True)
    assert final.exists()
    assert "1.png | S1 | type=config" in final.read_text(encoding="utf-8")
    assert not pending.exists()


# ---------------------------------------------------------------------------
# RED 10 — auto-save to pending + resume from partial progress
# ---------------------------------------------------------------------------
def test_generate_pending_autosaves_and_resumes(tmp_path):
    imgs = _make_images(tmp_path / "gambar")
    plan = parse_narrative_plan(PASS1_RESPONSE)
    pending = tmp_path / ".icg_cache" / "pending_inisiasi.txt"

    # First run: model fails after 2 images -> only 2 lines auto-saved
    model = _fake_model(PASS2_RESPONSES[:2])
    engine = ContextEngine(model)
    engine.generate_pending(
        image_paths=imgs,
        plan=plan,
        course_context="",
        pending_path=pending,
        course="KEPL",
        meeting="UTS",
    )
    saved = pending.read_text(encoding="utf-8")
    assert "1.png | S1" in saved
    assert "2.png | S1" in saved
    assert "10.png" not in saved

    # Resume: only remaining 2 calls should be made
    model2 = _fake_model(PASS2_RESPONSES[2:])
    engine2 = ContextEngine(model2)
    engine2.generate_pending(
        image_paths=imgs,
        plan=plan,
        course_context="",
        pending_path=pending,
        course="KEPL",
        meeting="UTS",
    )
    assert model2.generate_content.call_count == 2
    resumed = pending.read_text(encoding="utf-8")
    assert "9.png | S2" in resumed
    assert "10.png | S2" in resumed
    assert resumed.count("| S1 |") == 2  # originals preserved


# ---------------------------------------------------------------------------
# RED 11 — full two-pass pipeline writes enriched pending document
# ---------------------------------------------------------------------------
def test_full_two_pass_pipeline(tmp_path):
    imgs = _make_images(tmp_path / "gambar")
    pending = tmp_path / ".icg_cache" / "pending_inisiasi.txt"
    model = _fake_model([PASS1_RESPONSE] + PASS2_RESPONSES)
    engine = ContextEngine(model)

    plan = engine.visual_census(imgs, module_summary="Modul Docker")
    engine.generate_pending(imgs, plan, course_context="Konteks KEPL", pending_path=pending,
                            course="KEPL", meeting="UTS")

    text = pending.read_text(encoding="utf-8")
    assert "[@section] S1 |" in text
    assert "1.png | S1 | type=config | group=single" in text
    assert "9.png | S2 | type=terminal | group=pair:10" in text
    assert engine.model.generate_content.call_count == 5  # 1 census + 4 context


# ---------------------------------------------------------------------------
# NEW tests for R5/R7 verification gaps (REVIEW_R7_E1_E6.md)
# ---------------------------------------------------------------------------

def test_reconcile_order_flags_missing_and_extra(tmp_path):
    imgs = _make_images(tmp_path / "g", ("1.png", "2.png", "3.png"))
    plan = NarrativePlan(
        sections=[], order=["1.png", "2.png", "9.png"], pairs={}, raw_response=""
    )
    missing, extra = reconcile_order(plan, imgs)
    assert missing == ["3.png"]
    assert extra == ["9.png"]


def test_generate_pending_returns_reconcile_counts_and_warns(tmp_path):
    imgs = _make_images(tmp_path / "g", ("1.png", "2.png", "3.png"))
    plan = NarrativePlan(
        sections=[], order=["1.png", "2.png", "9.png"], pairs={}, raw_response=""
    )
    pending = tmp_path / "cache" / "p.txt"
    model = _fake_model(PASS2_RESPONSES[:2])
    with pytest.warns(UserWarning):
        result = ContextEngine(model).generate_pending(
            imgs, plan, "", pending, "KEPL", "UTS"
        )
    assert result["missing_from_order"] == ["3.png"]
    assert result["extra_in_order"] == ["9.png"]
    assert result["disk_total"] == 3
    assert result["generated"] == 2


def test_pass2_sanitizes_llm_output_and_falls_back_on_latex(tmp_path):
    """sanitize_ai_line must reject LaTeX commands; fallback to default line."""
    imgs = _make_images(tmp_path / "gambar", ("1.png",))
    plan = NarrativePlan(sections=[], order=["1.png"], pairs={}, raw_response="")
    # LaTeX command \textbf{} in label -> should be rejected
    model = _fake_model([r"type=code | Evil \textbf{X} | Konteks: a | Arah: b"])
    lines = ContextEngine(model).generate_context(imgs, plan, "")
    assert lines[0].label == "1.png"  # fallback uses filename as label
    assert lines[0].konteks == ""
    assert lines[0].type == "config"  # DEFAULT_TYPE


def test_pass2_valid_llm_output_is_kept_after_sanitize(tmp_path):
    """Valid LLM output passes sanitizer and is preserved."""
    imgs = _make_images(tmp_path / "gambar", ("1.png",))
    plan = NarrativePlan(sections=[], order=["1.png"], pairs={}, raw_response="")
    model = _fake_model(["type=terminal | ls | Konteks: list files | Arah: inspect"])
    lines = ContextEngine(model).generate_context(imgs, plan, "")
    assert lines[0].label == "ls"
    assert lines[0].type == "terminal"
    assert lines[0].konteks == "list files"


def test_sanitize_ai_line_called_in_generate_context(tmp_path, monkeypatch):
    """_parse_pass2_line must import and call src.security.sanitize_ai_line."""
    imgs = _make_images(tmp_path / "gambar", ("1.png",))
    plan = NarrativePlan(sections=[], order=["1.png"], pairs={}, raw_response="")
    with pytest.MonkeyPatch.context() as mp:
        import src.context_engine as ce
        mp.setattr(ce, "sanitize_ai_line", lambda s: None)  # force fallback
        lines = ContextEngine(_fake_model(["type=code | keep | Konteks: x | Arah: y"])).generate_context(imgs, plan, "")
        assert lines[0].label == "1.png"  # fallback


def test_serialize_enriched_document_mode_includes_git_aligned(tmp_path):
    doc = serialize_enriched_document(
        lines=[], sections=[], course="KEPL", meeting="UTS", total=0, mode="director"
    )
    assert "MODE: director (git-aligned)" in doc


def test_parse_narrative_plan_warns_when_pair_member_missing_from_order():
    text = "[ORDER] 1.png | 2.png\n[PAIR] 9.png:10.png\n"
    with pytest.warns(UserWarning, match="PAIR member"):
        parse_narrative_plan(text)


def test_visual_census_uses_context_manager_for_pil(tmp_path, monkeypatch):
    """Pass 1 visual_census must open images with `with Image.open(...) as img:`."""
    from PIL import ImageFile
    imgs = _make_images(tmp_path / "gambar", ("1.png", "2.png"))
    exits = []
    orig_exit = ImageFile.ImageFile.__exit__
    def tracked(self, *a, **k):
        exits.append(self)
        return orig_exit(self, *a, **k)
    monkeypatch.setattr(ImageFile.ImageFile, "__exit__", tracked)
    model = _fake_model([PASS1_RESPONSE])
    ContextEngine(model).visual_census(imgs, "module")
    assert len(exits) == len(imgs)


def test_generate_context_uses_context_manager_for_pil(tmp_path, monkeypatch):
    """Pass 2 generate_context must open images with `with Image.open(...) as img:`."""
    from PIL import ImageFile
    imgs = _make_images(tmp_path / "gambar", ("1.png", "2.png"))
    plan = NarrativePlan(sections=[], order=["1.png", "2.png"], pairs={}, raw_response="")
    exits = []
    orig_exit = ImageFile.ImageFile.__exit__
    def tracked(self, *a, **k):
        exits.append(self)
        return orig_exit(self, *a, **k)
    monkeypatch.setattr(ImageFile.ImageFile, "__exit__", tracked)
    model = _fake_model(PASS2_RESPONSES[:2])
    ContextEngine(model).generate_context(imgs, plan, "")
    assert len(exits) == len(imgs)
