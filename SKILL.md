---
name: icg-renaming-engine
description: "Use when implementing F1 ICG Renaming Engine tasks — extracting module steps from PDF/PPTX, vision-based screenshot classification, deduplication via hash/perceptual hash, canonical naming (1.png, 1a.png, T1.png...), and ACC-gated output."
category: software-development
---

# ICG Renaming Engine (F1) — Skill

This skill covers the **ImageContext-Generator Renaming Engine (F1)** — a pipeline that turns a raw folder of lab screenshots into an ordered, deduplicated, canonically named image set (`gambar/`) following the module's step structure from PDF/PPTX references.

## Pipeline Overview

```
extract_module_steps()  →  [ModuleStep, ...]
classify (vision)       →  step index per screenshot
dedup_screenshots()     →  unique files per step + duplicate report
assign_final_names()    →  1.png, 1a.png, T1.png, T2-1.png, ...
RenamingPlan.commit()   →  write gambar/ + renaming_report.txt (ACC gate)
```

**ACC Gate**: Nothing is written until `RenamingPlan.commit()` is called — which must happen **only after user approves the mapping table**.

---

## Data Structures

```python
@dataclass(frozen=True)
class ModuleStep:
    title: str
    is_task: bool = False

@dataclass
class RenameMapping:
    source_path: Path
    final_name: str
    step_index: int
    step_title: str
    confidence: float = 1.0
    matched_by: str = "vision"  # "vision" | "fallback"

@dataclass
class RenamingPlan:
    mappings: list[RenameMapping]
    duplicates: list[dict]
    unmatched: list[Path]
    mode: str = "reference"  # "reference" | "mtime-fallback"
    output_dir: Path
    source_dir: Path
```

---

## Key Functions

### Step Extraction
| Function | Input | Output |
|----------|-------|--------|
| `extract_steps_from_pdf(pdf_path)` | Path to PDF | `list[ModuleStep]` |
| `extract_steps_from_pptx(pptx_path)` | Path to PPTX | `list[ModuleStep]` |
| `extract_module_steps(reference_path)` | File or directory | `list[ModuleStep]` |

- Detects numbered steps (`1.`, `Langkah 1:`, `Step 1.`) and task sections (`Tugas`, `Latihan`, `Exercise`, `Assignment`, `Task`).
- Cleans titles by stripping prefixes.

### Deduplication
```python
dedup_screenshots(
    paths: list[Path],
    phash_threshold: int = 5,
    color_dist_threshold: float = 30.0,
) -> tuple[list[Path], list[dict]]
```
- **Stage 1**: Exact SHA-256 match → keeps first occurrence.
- **Stage 2**: Perceptual hash (dHash, 8×8) with Hamming distance ≤ `phash_threshold`.
  - Keeps newest file (mtime).
  - Guards: skips uniform (solid-color) images with dissimilar colors.
  - Color distance guard at `color_dist_threshold`.

### Naming
```python
assign_final_names(groups: list[tuple[ModuleStep, list[Path]]]) -> list[RenameMapping]
```
| Scenario | Naming Pattern |
|----------|----------------|
| Regular step, 1 shot | `1.png` |
| Regular step, N shots | `1a.png`, `1b.png`, … (`1aa.png` after `1z.png`) |
| Task step, 1 shot | `T1.png` |
| Task step, N shots | `T1-1.png`, `T1-2.png`, … |

### Plan Building (ACC Gate)
```python
build_renaming_plan(
    source_dir,
    reference_dir | None,
    output_dir,
    classifier: ClassifierFn | None = None,
) -> RenamingPlan
```
- With reference + classifier → vision classification, per-step dedup.
- Without → mtime fallback, each image its own step.
- **Nothing written until `plan.commit()`**.

---

## CLI Integration

```bash
python -m src.cli rename \
    --course kepl \
    --pertemuan Per4 \
    --reference-dir workspace/kepl/reference \
    --workspace workspace
```

Options:
- `--reference-dir / -r`: PDF/PPTX directory for step extraction.
- `--output-dir / -o`: Custom output (default: `<workspace>/<COURSE>/gambar/<Pertemuan>`).
- `--source-subdir`: Raw screenshots subfolder (default: `.` — current folder).

---

## Constraints & Rules

1. **ACC is mandatory** — never call `commit()` without explicit user approval.
2. **Git context is advisory only** — never override visual evidence from screenshots.
3. **Backward compatibility** — legacy `inisiasi.txt` (free-form notes) must remain readable by downstream tools (not handled here, but don't break it).
4. **Workspace isolation** — all paths validated via `resolve_under_root()`.
5. **Thresholds** — perceptual hash Hamming ≤ 5 for near-duplicates.
6. **Uniform images** — solid-color images with different hues must NOT be falsely deduped.

---

## Testing (TDD)

Run tests:
```bash
py -3.12 -m pytest tests/test_renaming_engine.py -v
```

Test coverage:
- `test_extract_steps_from_pdf_detects_numbered_steps_and_task_sections`
- `test_extract_steps_from_pptx_uses_slide_titles`
- `test_extract_module_steps_dispatches_by_extension`
- `test_hash_file_returns_sha256_hex`
- `test_dedup_removes_exact_hash_duplicates_keeping_first`
- `test_perceptual_hash_is_stable_for_identical_images`
- `test_dedup_removes_near_duplicate_by_phash_and_keeps_newer`
- `test_assign_names_single_screenshot_per_regular_step`
- `test_assign_names_multiple_screenshots_use_letter_suffix`
- `test_assign_names_task_steps_get_t_prefix_and_multi_task_numbering`
- `test_build_plan_produces_mapping_without_writing_output`
- `test_commit_writes_files_and_report_after_acc`
- `test_fallback_without_reference_sorts_by_mtime`

---

## Integration Points

- **VisionEngine** (`src/vision_engine.py`): Used by CLI classifier for screenshot→step matching.
- **KnowledgeManager** (`src/knowledge_manager.py`): Not directly used, but reference materials may come from its knowledge base.
- **DirectorEngine** (`src/director.py`): Independent pipeline; F1 can run before or after Director Mode.
- **Security** (`src/security.py`): All paths go through `resolve_under_root()`.

---

## Common Pitfalls

| Pitfall | Prevention |
|---------|------------|
| False dedup on solid-color images | Color distance guard + uniform-image check |
| Overwriting source images | `commit()` writes to separate `output_dir` (`gambar/`) |
| Phash threshold too strict/lenient | Default 5; tune per course if needed |
| Classifier hallucinating step index | Prompt restricts to single digit; fallback on parse failure |
| PDF/PPTX extraction missing steps | Fallback to first non-empty line per page/slide |

---

## Future Extensions (not F1)

- Confidence scoring from vision (logprobs / ensemble).
- OCR-based step detection (e.g., "Step 3" in screenshot text).
- Cross-session duplicate tracking (persistent hash DB).
- Interactive ACC review (TUI for mapping table).