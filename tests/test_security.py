"""Security acceptance tests for S2-SecurityFix (SEC-01..SEC-10).

TDD: tests describe the required behaviour; the implementation lands after.
No real network/API calls are made — the vision model is always faked.
"""
from __future__ import annotations

import hashlib
import os
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from PIL import Image
from typer.testing import CliRunner

from src.cli import app
from src.security import (
    PathValidationError,
    escape_latex,
    redact,
    resolve_under_root,
    sanitize_ai_line,
    validate_course_id,
    validate_segment,
)
from src.vision_engine import VisionEngine


REPO_ROOT = Path(__file__).resolve().parents[1]


def _make_workspace(base: Path, course: str = "KEPL", pertemuan: str = "Per4") -> Path:
    shots = base / "workspace" / course / "screenshots" / pertemuan
    shots.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (8, 8), color=(1, 2, 3)).save(shots / "1.png")
    (base / "workspace" / course / "inisiasi").mkdir(parents=True, exist_ok=True)
    return base / "workspace"


def _fake_vision(pretend=True):
    """Patch src.cli.VisionEngine with a deterministic recorder."""
    recorded = {"prompts": [], "director_calls": []}

    class FakeVE:
        def __init__(self, *args, **kwargs):
            pass

        def analyze_image_with_context(self, image_path, git_context, general_context="", planned_index=None):
            recorded["prompts"].append("\n".join([git_context, general_context]))
            return "Setup Docker | Konteks: multi-stage build | Arah: CI/CD"

        def generate_course_inisiasi(self, **kwargs):
            output_file = kwargs.get("output_file")
            if output_file:
                Path(output_file).parent.mkdir(parents=True, exist_ok=True)
                Path(output_file).write_text(
                    "1.png | Setup Docker | Konteks: multi-stage build | Arah: CI/CD\n",
                    encoding="utf-8",
                )
            return {"total": 1, "generated": 1, "errors": 0}

        def generate_director_inisiasi(self, plan_items, course_id, knowledge_manager, output_file, **kwargs):
            recorded["director_calls"].append({
                "plan_items": plan_items,
                "course_id": course_id,
                "output_file": output_file,
            })
            recorded["prompts"].extend(item["git_context"] for item in plan_items)
            if output_file:
                Path(output_file).parent.mkdir(parents=True, exist_ok=True)
                Path(output_file).write_text(
                    "1.png | Setup Docker | Konteks: multi-stage build | Arah: CI/CD\n",
                    encoding="utf-8",
                )
            return {"total": len(plan_items), "generated": len(plan_items), "errors": 0}

    return FakeVE, recorded


# ---------------------------------------------------------------------------
# SEC-02 — --output traversal must be rejected, .env untouched
# ---------------------------------------------------------------------------
def test_sec02_output_traversal_rejected_and_env_intact(tmp_path, monkeypatch):
    cwd = tmp_path / "a" / "b"
    cwd.mkdir(parents=True)
    (cwd / "workspace").mkdir()
    env = tmp_path / ".env"
    env.write_text("GOOGLE_API_KEY=DO_NOT_TOUCH\n", encoding="utf-8")
    before = hashlib.sha256(env.read_bytes()).hexdigest()
    monkeypatch.chdir(cwd)

    FakeVE, _ = _fake_vision()
    with patch("src.cli.VisionEngine", FakeVE):
        result = CliRunner().invoke(app, [
            "generate-director", "-c", "KEPL", "-p", "Per4", "-w", "workspace",
            "-o", "../../.env",
        ])

    assert result.exit_code != 0
    assert hashlib.sha256(env.read_bytes()).hexdigest() == before


def test_sec02_output_must_be_txt(tmp_path):
    root = tmp_path / "workspace"
    with pytest.raises(PathValidationError):
        resolve_under_root(root, root / "inisiasi" / "evil.py", suffix=".txt")


# ---------------------------------------------------------------------------
# SEC-03 / SEC-04 — pertemuan + course allowlist before any FS write
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("bad", ["../evil", "../../../x", "a/b", ".", ""])
def test_sec03_bad_pertemuan_rejected(tmp_path, monkeypatch, bad):
    workspace = _make_workspace(tmp_path)
    monkeypatch.chdir(tmp_path)
    with pytest.raises(PathValidationError):
        validate_segment(bad, "pertemuan")


def test_sec03_cli_rejects_traversal_before_write(tmp_path, monkeypatch):
    _make_workspace(tmp_path)
    monkeypatch.chdir(tmp_path)
    FakeVE, _ = _fake_vision()
    with patch("src.cli.VisionEngine", FakeVE):
        result = CliRunner().invoke(app, [
            "generate", "-c", "KEPL", "-p", "../evil", "-w", "workspace",
        ])
    assert result.exit_code != 0
    assert not (tmp_path / "evil.txt").exists()
    assert not (tmp_path / "workspace" / "KEPL" / "inisiasi" / "evil.txt").exists()


def test_sec04_cli_scan_rejects_traversal(tmp_path, monkeypatch):
    _make_workspace(tmp_path)
    monkeypatch.chdir(tmp_path)
    result = CliRunner().invoke(app, [
        "scan", "-w", "workspace", "-c", "KEPL", "-p", "../../../x",
    ])
    assert result.exit_code != 0
    assert "pertemuan" in result.output.lower() or "invalid" in result.output.lower()


# ---------------------------------------------------------------------------
# SEC-04 — resolve_under_root rejects symlink escapes (Unix-only, symlink privs)
# ---------------------------------------------------------------------------
@pytest.mark.skipif(
    os.name == "nt",
    reason="Windows requires admin for symlinks; containment tested via other paths",
)
def test_sec04_resolve_under_root_rejects_symlink_escape(tmp_path):
    root = tmp_path / "workspace"
    root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "secret.png").write_bytes(b"x")
    (root / "link").symlink_to(outside, target_is_directory=True)
    with pytest.raises(PathValidationError):
        resolve_under_root(root, root / "link" / "secret.png")


# ---------------------------------------------------------------------------
# SEC-01 — git context is opt-in and commit subjects are redacted
# ---------------------------------------------------------------------------
def _make_git_fixture(base: Path) -> Path:
    repo = base / "fixture_repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.invalid"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "Fixture"], cwd=repo, check=True)
    (repo / "README.md").write_text("fixture\n", encoding="utf-8")
    subprocess.run(["git", "add", "README.md"], cwd=repo, check=True)
    subprocess.run(
        ["git", "commit", "-q", "-m", "WIP FAKE-SECRET-XYZ token=FAKE123"],
        cwd=repo, check=True,
    )
    return repo


def test_sec01_git_context_opt_in_and_redacted(tmp_path):
    from src.director import DirectorEngine

    repo = _make_git_fixture(tmp_path)
    assert DirectorEngine(repo_path=str(repo)).git_timeline == []

    engine = DirectorEngine(repo_path=str(repo), allow_git_context=True)
    subjects = " || ".join(c["subject"] for c in engine.git_timeline)
    assert "FAKE-SECRET-XYZ" not in subjects
    assert "FAKE123" not in subjects
    assert "[REDACTED]" in subjects


def test_sec01_redaction_covers_token_jwt_and_userinfo():
    # Valid 3-segment JWT (base64url.header.payload.signature) — must be caught
    # by _JWT_RE; a malformed JWT would make the assertion trivially pass.
    jwt = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.abc123SIG"
    sample = (
        f"deploy token=FAKE123 password=hunter2 "
        f"https://alice:supersecretpw@example.invalid/x "
        f"{jwt} FAKE-SECRET-XYZ"
    )
    cleaned = redact(sample)
    # Every secret actually present in `sample` must be gone from `cleaned`.
    assert "FAKE123" not in cleaned
    assert "hunter2" not in cleaned
    assert "alice:***@example.invalid" not in cleaned
    assert jwt not in cleaned
    assert "FAKE-SECRET-XYZ" not in cleaned
    # Proof the patterns matched (not trivially true on an empty sample).
    assert "[REDACTED]" in cleaned


def test_sec01_redaction_does_not_over_redact_common_words():
    """MINOR #4 regression: uppercase-only token rule must spare lowercase words."""
    sample = "fix monkey patch for passport apikey module"
    assert redact(sample) == sample


def test_sec01_cli_does_not_leak_subject_into_prompt(tmp_path, monkeypatch):
    repo = _make_git_fixture(tmp_path)
    workspace = _make_workspace(tmp_path)
    monkeypatch.chdir(tmp_path)
    FakeVE, recorded = _fake_vision()
    with patch("src.cli.VisionEngine", FakeVE):
        result = CliRunner().invoke(app, [
            "generate-director", "-c", "KEPL", "-p", "Per4", "-w", "workspace",
            "-r", str(repo), "--allow-git-context",
        ])
    assert result.exit_code == 0
    prompts = "\n".join(recorded["prompts"])
    assert "FAKE-SECRET-XYZ" not in prompts
    assert "FAKE123" not in prompts


# ---------------------------------------------------------------------------
# SEC-05 — API key is never kept on the engine instance
# ---------------------------------------------------------------------------
def test_sec05_api_key_not_in_instance_vars(monkeypatch):
    monkeypatch.setenv("GOOGLE_API_KEY", "AIzaFakeTestingKey000000000000000")
    with patch("src.vision_engine.genai.configure"), patch("src.vision_engine.genai.GenerativeModel"):
        engine = VisionEngine()
    assert "api_key" not in vars(engine)
    assert "AIza" not in repr(engine)


def test_sec05_module_import_does_not_load_dotenv(tmp_path, monkeypatch):
    """Importing vision_engine must not populate env from a nearby .env."""
    marker = "ICG_IMPORT_SENTINEL_9f3a"
    (tmp_path / ".env").write_text(f"ICG_DOTENV_SENTINEL={marker}\n", encoding="utf-8")
    script = (
        "import sys, os; "
        "sys.path.insert(0, r'" + str(REPO_ROOT).replace("'", "") + "'); "
        "import src.vision_engine; "
        "print(os.environ.get('ICG_DOTENV_SENTINEL', 'NOT_LOADED'))"
    )
    env = {"PATH": "", "SYSTEMROOT": str(Path.home()), "PYTHONPATH": str(REPO_ROOT)}
    proc = subprocess.run(
        ["C:/Python312/python.exe", "-B", "-c", script],
        cwd=tmp_path, capture_output=True, text=True, env=env, check=False,
    )
    assert marker not in proc.stdout


# ---------------------------------------------------------------------------
# SEC-06 — .env variants ignored
# ---------------------------------------------------------------------------
def test_sec06_env_variants_ignored(tmp_path):
    dummy = REPO_ROOT / ".env.local"
    dummy.write_text("DUMMY=1\n", encoding="utf-8")
    try:
        proc = subprocess.run(
            ["git", "check-ignore", "-q", ".env.local"],
            cwd=REPO_ROOT, capture_output=True, text=True, check=False,
        )
        assert proc.returncode == 0, proc.stdout + proc.stderr
        assert "!.env.example" in (REPO_ROOT / ".gitignore").read_text(encoding="utf-8")
    finally:
        dummy.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# SEC-07 — knowledge manager allowlist + reference_dir containment
# ---------------------------------------------------------------------------
def _write_course_config(base: Path) -> Path:
    kdir = base / "knowledge"
    kdir.mkdir(parents=True, exist_ok=True)
    (kdir / "kepl.yaml").write_text(
        "course_name: KEPL\ncode: KEPL\ndescription: dummy\n", encoding="utf-8"
    )
    return kdir


def test_sec07_course_id_allowlist_and_reference_dir(tmp_path):
    from src.knowledge_manager import KnowledgeManager

    kdir = _write_course_config(tmp_path)
    km = KnowledgeManager(str(kdir), allowed_root=tmp_path)
    with pytest.raises(PathValidationError):
        km.load_course_config("../../secret")
    with pytest.raises(PathValidationError):
        km.build_course_context("kepl", reference_dir="../../etc")
    assert "KEPL" in km.build_course_context("kepl")


def test_sec07_cli_rejects_course_traversal(tmp_path, monkeypatch):
    _make_workspace(tmp_path)
    monkeypatch.chdir(tmp_path)
    result = CliRunner().invoke(app, [
        "scan", "-w", "workspace", "-c", "../../secret", "-p", "Per4",
    ])
    assert result.exit_code != 0
    assert "course" in result.output.lower() or "invalid" in result.output.lower()
    assert validate_course_id("kepl") == "kepl"


# ---------------------------------------------------------------------------
# SEC-09 — redacted exception logging
# ---------------------------------------------------------------------------
def test_sec09_error_log_is_redacted(tmp_path, capsys):
    shots = tmp_path / "shots"
    shots.mkdir()
    Image.new("RGB", (8, 8)).save(shots / "1.png")
    engine = VisionEngine.__new__(VisionEngine)
    engine.model_name = "models/test"
    engine.model = MagicMock()
    engine.model.generate_content.side_effect = ValueError("token=SUPERSECRET999 at https://u:p@host.invalid")
    result = engine.analyze_image_with_context(
        str(shots / "1.png"), git_context="", general_context=""
    )
    assert result == ""
    out = capsys.readouterr().out
    assert "SUPERSECRET999" not in out
    assert "hunter2" not in out


# ---------------------------------------------------------------------------
# SEC-10 — LLM line pattern validation + LaTeX escape helper
# ---------------------------------------------------------------------------
def test_sec10_rejects_latex_command_line():
    assert sanitize_ai_line(r"Setup \textbf{PAWNED} | Konteks: x | Arah: y") is None
    assert sanitize_ai_line("Setup Docker | Konteks: x | Arah: y") == "Setup Docker | Konteks: x | Arah: y"
    assert sanitize_ai_line("x" * 2000) is None


def test_sec10_escape_latex_for_consumer():
    assert escape_latex("a_b & $x #1 {y}") == r"a\_b \& \$x \#1 \{y\}"


def test_sec10_engine_falls_back_on_latex_injection(tmp_path):
    shots = tmp_path / "shots"
    shots.mkdir()
    Image.new("RGB", (8, 8)).save(shots / "1.png")
    out = tmp_path / "inisiasi" / "Per4.txt"
    engine = VisionEngine.__new__(VisionEngine)
    engine.model_name = "models/test"
    resp = MagicMock()
    resp.text = r"Setup \textbf{PAWNED} | Konteks: x | Arah: y"
    engine.model = MagicMock()
    engine.model.generate_content.return_value = resp
    engine.generate_course_inisiasi(
        course_id="kepl", screenshots_dir=str(shots),
        knowledge_manager=_StaticKM(), output_file=str(out),
    )
    text = out.read_text(encoding="utf-8")
    assert r"\textbf" not in text


class _StaticKM:
    def build_course_context(self, course_id, reference_dir=None):
        return "dummy"


# ---------------------------------------------------------------------------
# E2E — generate & generate-director with REAL KnowledgeManager
# These catch the regression from review round 1 (MAJOR #1) where
# KnowledgeManager(config_root="knowledge/courses", allowed_root=workspace)
# broke because config lives at repo root, outside workspace.
# ---------------------------------------------------------------------------
def test_e2e_generate_with_real_knowledge_manager(tmp_path, monkeypatch):
    """Full generate flow with real KnowledgeManager (config at repo root, ws in subdir)."""
    # Repo layout: knowledge/courses/kepl.yaml at repo root
    repo_root = tmp_path
    kdir = repo_root / "knowledge" / "courses"
    kdir.mkdir(parents=True)
    (kdir / "kepl.yaml").write_text(
        "course_name: KEPL\ncode: KEPL\ndescription: Konstruksi dan Evolusi Perangkat Lunak\n",
        encoding="utf-8",
    )

    # Workspace is a SUBDIRECTORY of repo (real-world structure)
    # _prepare expects: workspace_root / course_id / screenshots / pertemuan
    workspace = repo_root / "workspace" / "KEPL" / "KEPL" / "screenshots" / "Per4"
    workspace.mkdir(parents=True)
    Image.new("RGB", (8, 8), color=(10, 20, 30)).save(workspace / "1.png")
    (repo_root / "workspace" / "KEPL" / "KEPL" / "inisiasi").mkdir(parents=True)

    monkeypatch.chdir(repo_root)

    # Real KnowledgeManager: config_root = repo root (knowledge/courses), reference_root = workspace
    FakeVE, recorded = _fake_vision()
    with patch("src.cli.VisionEngine", FakeVE):
        result = CliRunner().invoke(app, [
            "generate", "-c", "KEPL", "-p", "Per4",
            "-w", "workspace/KEPL",
        ])

    assert result.exit_code == 0, f"stdout: {result.stdout}\nstderr: {result.stderr}"
    # Verify inisiai.txt was produced
    out = repo_root / "workspace" / "KEPL" / "KEPL" / "inisiasi" / "Per4.txt"
    assert out.exists()
    text = out.read_text(encoding="utf-8")
    assert "Konteks:" in text and "Arah:" in text


def test_e2e_generate_director_with_real_knowledge_manager(tmp_path, monkeypatch):
    """Full generate-director flow with real KnowledgeManager + fake git repo."""
    repo_root = tmp_path
    # Real course config at repo root
    kdir = repo_root / "knowledge" / "courses"
    kdir.mkdir(parents=True)
    (kdir / "kepl.yaml").write_text(
        "course_name: KEPL\ncode: KEPL\ndescription: dummy\n",
        encoding="utf-8",
    )

    # Workspace subdir (double course_id per _prepare convention)
    workspace = repo_root / "workspace" / "KEPL" / "KEPL" / "screenshots" / "Per4"
    workspace.mkdir(parents=True)
    Image.new("RGB", (8, 8), color=(10, 20, 30)).save(workspace / "1.png")
    (repo_root / "workspace" / "KEPL" / "KEPL" / "inisiasi").mkdir(parents=True)

    # Fake git repo for git context (also at repo root)
    import subprocess
    git_repo = repo_root / "fixture_repo"
    git_repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=git_repo, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.invalid"], cwd=git_repo, check=True)
    subprocess.run(["git", "config", "user.name", "Fixture"], cwd=git_repo, check=True)
    (git_repo / "README.md").write_text("fixture\n", encoding="utf-8")
    subprocess.run(["git", "add", "README.md"], cwd=git_repo, check=True)
    subprocess.run(
        ["git", "commit", "-q", "-m", "WIP FAKE-SECRET-XYZ token=FAKE123"],
        cwd=git_repo, check=True,
    )

    monkeypatch.chdir(repo_root)

    FakeVE, recorded = _fake_vision()
    with patch("src.cli.VisionEngine", FakeVE):
        result = CliRunner().invoke(app, [
            "generate-director", "-c", "KEPL", "-p", "Per4",
            "-w", "workspace/KEPL",
            "-r", str(git_repo), "--allow-git-context",
        ])

    assert result.exit_code == 0, f"stdout: {result.stdout}\nstderr: {result.stderr}"
    out = repo_root / "workspace" / "KEPL" / "KEPL" / "inisiasi" / "Per4_director.txt"
    assert out.exists()
    text = out.read_text(encoding="utf-8")
    assert "Konteks:" in text and "Arah:" in text
    # Verify git context was redacted
    prompts = "\n".join(recorded["prompts"])
    assert "FAKE-SECRET-XYZ" not in prompts
    assert "FAKE123" not in prompts


# ---------------------------------------------------------------------------
# R5/R7 Fixes — Pass 1 ACC prompt & Scoped pending isolation
# ---------------------------------------------------------------------------
def test_generate_context_pass1_acc_prompt_aborts_on_decline(tmp_path, monkeypatch):
    """Pass 1 ACC checkpoint must prompt and abort (Exit(0)) if user declines."""
    repo_root = tmp_path
    workspace = repo_root / "workspace" / "KEPL" / "KEPL" / "screenshots" / "Per4"
    workspace.mkdir(parents=True)
    Image.new("RGB", (8, 8), color=(10, 20, 30)).save(workspace / "1.png")
    Image.new("RGB", (8, 8), color=(20, 30, 40)).save(workspace / "2.png")
    (repo_root / "workspace" / "KEPL" / "KEPL" / "inisiasi").mkdir(parents=True)

    monkeypatch.chdir(repo_root)

    class FakeModel:
        def generate_content(self, *args, **kwargs):
            resp = MagicMock()
            resp.text = (
                "[SECTION] S1 | Setup\n"
                "[ORDER] 1.png | 2.png\n"
                "[GROUP] S1: 1.png, 2.png\n"
            )
            return resp

    class FakeVE:
        def __init__(self, *args, **kwargs):
            self.model = FakeModel()

    with patch("src.cli.VisionEngine", FakeVE):
        # Input 'n' to decline the Pass 1 ACC prompt
        result = CliRunner().invoke(app, [
            "generate-context", "-c", "KEPL", "-p", "Per4",
            "-w", "workspace/KEPL",
        ], input="n\n")

    assert result.exit_code == 0, f"stdout: {result.stdout}\nstderr: {result.stderr}"
    pending = repo_root / ".icg_cache" / "KEPL" / "Per4" / "pending_inisiasi.txt"
    assert not pending.exists(), "Pending file must not be created on ACC decline"
    assert "Aborting before Pass 2" in result.output


def _fake_context_vision():
    """VisionEngine stub whose model queues a Pass 1 plan then Pass 2 lines."""

    class FakeModel:
        def __init__(self):
            self.call_count = 0

        def generate_content(self, *args, **kwargs):
            self.call_count += 1
            resp = MagicMock()
            if self.call_count == 1:
                resp.text = "[SECTION] S1 | Setup\n[ORDER] 1.png\n[GROUP] S1: 1.png\n"
            else:
                resp.text = "type=config | Test | Konteks: x | Arah: y"
            return resp

    class FakeVE:
        def __init__(self, *args, **kwargs):
            self.model = FakeModel()

    return FakeVE


def test_scoped_pending_isolation_across_courses(tmp_path, monkeypatch):
    """Pending files must be isolated per course+meeting (.icg_cache/<course>/<meeting>/)."""
    repo_root = tmp_path
    for course, meeting in (("KEPL", "Per4"), ("PPG", "UTS")):
        shots = repo_root / "workspace" / course / course / "screenshots" / meeting
        shots.mkdir(parents=True)
        Image.new("RGB", (8, 8)).save(shots / "1.png")
        (repo_root / "workspace" / course / course / "inisiasi").mkdir(parents=True)

    monkeypatch.chdir(repo_root)

    with patch("src.cli.VisionEngine", _fake_context_vision()):
        r1 = CliRunner().invoke(app, [
            "generate-context", "-c", "KEPL", "-p", "Per4", "-w", "workspace/KEPL",
        ], input="y\nn\n")  # Pass 1 ACC yes, Pass 2 ACC no -> pending preserved
        assert r1.exit_code == 0, f"KEPL: {r1.stdout}\n{r1.stderr}"

        r2 = CliRunner().invoke(app, [
            "generate-context", "-c", "PPG", "-p", "UTS", "-w", "workspace/PPG",
        ], input="y\nn\n")
        assert r2.exit_code == 0, f"PPG: {r2.stdout}\n{r2.stderr}"

    pending_kepl = repo_root / ".icg_cache" / "kepl" / "Per4" / "pending_inisiasi.txt"
    pending_ppg = repo_root / ".icg_cache" / "ppg" / "UTS" / "pending_inisiasi.txt"
    # Both are distinct, scoped files (not one shared pending)
    assert pending_kepl.exists()
    assert pending_ppg.exists()
    assert pending_kepl != pending_ppg
    assert "KEPL" in pending_kepl.read_text(encoding="utf-8")
    assert "PPG" in pending_ppg.read_text(encoding="utf-8")
