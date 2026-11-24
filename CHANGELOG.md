# CHANGELOG — ImageContext-Generator

Semua perubahan signifikan didokumentasikan di sini. File ini di-generate otomatis
oleh [git-cliff](https://github.com/orhun/git-cliff) dari Conventional Commits.
Format mengikuti [Keep a Changelog](https://keepachangelog.com/id/1.0.0/),
versi mengikuti [SemVer](https://semver.org/lang/id/).

---
## [0.1.0] — 2026-11-24

### ✨ Baru
- Initial commit with project structure and docs- **director:** Implement holistic narrative planner with git commit timeline alignment (v0.2.0)- **director:** Add organize command to auto-rename/copy raw screenshots into sequential 1.png..N.png- **workspace:** Decouple user workspace via workspace.template dummy placeholders and strict gitignore- **director:** Add output path option, resume capability, and auto-save for Director Mode- **engine:** Renaming + context + security engines with test suite- **release:** Git-cliff auto versioning + release workflow

### 📝 Dokumentasi
- Update PRD and README with holistic narrative planner (director mode) roadmap & clearer env placeholder- Add workspace directory guide and placeholder structure with .gitkeep- Update README with v0.2.0 features, Director Mode CLI commands, and workspace guide

### 📦 Internal
- Add .gitignore for Python, env, OS files- Ignore workspace screenshots & references to keep repo lightweight- Generate complete UTS inisiasi metadata via Director Mode (63 screenshots mapped)- Refine .gitignore to ignore generated inisiasi files and protect confidential PRD- Ignore agent working docs + cross-cite MyLaprak ecosystem

### 🛠️ Diperbaiki
- **vision:** Support direct PIL image ingestion and update default model to gemini-3.1-flash-lite- **vision:** Prioritize visual ground truth over git context and improve regex line formatting- **release:** Accept unprefixed bumped version in tag pattern

