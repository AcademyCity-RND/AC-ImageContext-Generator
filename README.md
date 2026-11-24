# 👁️ ImageContext-Generator (ICG)
### *Jaou Shingan Context Synthesizer Engine*

Generator otomatis untuk mengekstrak konteks visual dari serangkaian gambar tangkapan layar praktikum (`1.png` - `x.png`) menjadi berkas metadata `inisiasi.txt` terstruktur, yang siap diumpankan ke tool generator laporan utama.

---

## 🚀 Quick Start

### Prasyarat
- Python 3.11+
- Google API Key (Gemini API Free Tier) → set di `.env` sebagai `GOOGLE_API_KEY`

### Instalasi
```bash
git clone https://github.com/AcademyCity-RND/ImageContext-Generator.git
cd ImageContext-Generator
pip install -r requirements.txt
cp .env.example .env
# Edit .env dan isi GOOGLE_API_KEY
```

### Struktur Workspace & Placeholder

Folder `workspace/` yang berisi data pribadi Anda (gambar, slide dosen, output) **sudah 100% di-ignore oleh Git** sehingga tidak akan pernah ter-push ke repository publik.

Untuk memulai, repositori ini menyediakan template placeholder di `workspace.template/`:
```bash
# Salin folder template menjadi workspace lokal Anda
cp -r workspace.template workspace
```
Atau Anda bisa membuat folder `workspace/` sendiri dengan struktur berikut:

```text
workspace/
├── <KODE_MATKUL>/         # Contoh: KEPL, PPG (bisa ditambah sendiri)
│   ├── screenshots/       # [ROOT 1] Taruh tangkapan layar praktikum per pertemuan (Per1/, UTS/, dsb.)
│   ├── _reference/        # [ROOT 2] Taruh slide kuliah/modul PDF referensi di sini (opsional)
│   └── inisiasi/          # [ROOT 3] Berkas inisiasi.txt hasil analisis AI akan otomatis tersimpan di sini
```

Penjelasan fungsi setiap root direktori di dalam mata kuliah:
1. **`screenshots/`**: Tempat menaruh seluruh gambar bukti praktikum. Anda bisa membuat subfolder per pertemuan (misal `Per1/`, `Per2/`, `UTS/`). File bisa berupa format `1.png` - `N.png` atau format raw bawaan OS (bisa dirapikan otomatis dengan perintah `organize`).
2. **`_reference/`**: Tempat menaruh materi pendukung praktikum (slide presentasi PPTX, panduan modul PDF, kisi-kisi soal). AI Vision akan menyerap konteks materi ini untuk mempertajam analisis gambar.
3. **`inisiasi/`**: Folder output. Tool akan meletakkan hasil sintesis metadata visual (`<Pertemuan>.txt`) di sini, siap diumpankan ke generator dokumen laporan utama.

---

## 🖥️ Cara Penggunaan (CLI)

### 1. Lihat Daftar Matkul Tersedia
```bash
python -m src.cli list-courses
```

### 2. Scan Screenshot di Folder Pertemuan
```bash
python -m src.cli scan -c kepl -p Per4
```

### 3. Generate `inisiasi.txt` dari Screenshot
```bash
python -m src.cli generate -c kepl -p Per4
```
Hasil: `workspace/KEPL/inisiasi/Per4.txt` (17 baris entry untuk 17 screenshot)

---

## 📚 Menambah Matkul Baru (Modular Knowledge Base)

Sistem ini **modular by design** — tambah matkul baru = drop 1 file YAML di `knowledge/courses/`, **tanpa ubah kode inti**.

### Contoh: Tambah Matkul "Sistem Operasi"
Buat file `knowledge/courses/sistem-operasi.yaml`:
```yaml
course_id: "sistem-operasi"
course_name: "Praktikum Sistem Operasi"
code: "SO"
semester: 4
description: "Praktikum SO: process scheduling, memory management, file systems"

analysis_guidelines:
  focus_areas:
    - "Linux process management (ps, top, htop)"
    - "Memory mapping dan virtual memory"
  technical_terms:
    - "PID, PPID, context switch"
    - "page fault, swap, OOM killer"

output_template:
  line_pattern: "{index}. {label} | {context}"
  header: "# ========================================================"
  footer: "# ========================================================"
```

---

## 🧪 Contoh Output `inisiasi.txt` (KEPL Per4)
```text
# ========================================================
1. Dockerfile tahap builder: menggunakan composer:2.7 dan php:8.3-cli-alpine untuk install dependensi
2. Dockerfile tahap runtime: konfigurasi non-root user www-data, HEALTHCHECK /up Laravel 11, EXPOSE 8000
...
17. PaaS dashboard (Railway/Render): daftar service evolusi-api tugas4 (inactive) dan tugas5 (active)
# ========================================================
```

---

### 🗺️ Rencana Pengembangan (Roadmap)

#### ✅ v0.1.0 — MVP (Selesai)
- [x] Scanner screenshot berurutan (1.png ... x.png)
- [x] Vision Engine dengan Google Gemini 1.5 Flash
- [x] Knowledge Manager (YAML + PDF reference extraction)
- [x] CLI: `scan`, `generate`, `list-courses`
- [x] Course configs: KEPL, PPG
- [x] Tested: KEPL Per4 (17 screenshots → 17 entries)

#### ✅ v0.2.0 — Holistic Narrative Planner / Director Mode (Selesai!)
- [x] **Director Mode:** Perencanaan narasi holistik menyelaraskan screenshot dengan alur kerja teknis
- [x] **Repo-Guided Context Matching:** Flag `--repo <path>` mengekstrak riwayat git commit target & mencocokkannya dengan screenshot
- [x] **CLI Commands Baru:**
  - `python -m src.cli plan -c <course> -p <pertemuan> -r <repo>` (Preview narasi & commit mapping)
  - `python -m src.cli organize -c <course> -p <pertemuan> -r <repo>` (Otomatis copy/rename ke format terurut `1.png` - `N.png`)
  - `python -m src.cli generate-director -c <course> -p <pertemuan> -r <repo>` (Generate inisiasi berbasis narasi Git)
- [x] **Direct PIL Streaming:** Integrasi cepat dengan `models/gemini-3.1-flash-lite` tanpa ketergantungan Google File API
- [x] **Tested:** KEPL UTS (63 screenshots terpetakan sempurna ke 49 commit & 14 bukti evaluasi SS-01 s.d. SS-14)

#### 🎯 v0.3.0 — Multi-Provider & UX
- [ ] Support OpenAI GPT-4o-mini / Anthropic Claude sebagai fallback vision provider
- [ ] Interactive TUI mode (`python -m src.cli interactive`)
- [ ] Export format JSON/Markdown selain plain text
- [ ] Watch mode: auto-generate saat ada screenshot baru ditambah

#### 🚀 v1.0.0 — Production Ready
- [ ] Package sebagai PyPI installable (`pip install imagecontext-generator`)
- [ ] GitHub Action workflow untuk CI/test
- [ ] Comprehensive test suite (pytest + golden files)
- [ ] Documentation site (MkDocs/GitBook)

---

## ⚙️ Konfigurasi Environment (`.env`)
```env
GOOGLE_API_KEY=your_gemini_api_key_here
OPENAI_API_KEY=optional_fallback_key
LOG_LEVEL=INFO
```

---

## 🔗 Ekosistem

ICG adalah **front-end compiler** (pixels → `inisiasi.txt`). Output-nya dikonsumsi oleh
**[MyLaprak](https://github.com/Avin1731/MyLaprak)** — back-end compiler (IR → laporan LaTeX).

Alur lengkap: `make-laprak-info → /icg-renaming → /icg-contextgenerate → breakdown-matkul → make-laprak`.
Lihat `plan.md` di Desktop untuk kontrak IR (`inisiasi.txt` enriched: `type`, `group`, `width_hint`, `section`).

Skill ICG juga di-vendor di repo MyLaprak (`skills/icg-renaming/`, `skills/icg-contextgenerate/`).

---

## 🤝 Kontribusi
1. Fork repo ini
2. Buat branch fitur: `git checkout -b feat/nama-fitur`
3. Commit: `git commit -m "feat: deskripsi singkat"`
4. Push & buka Pull Request

---

## 📜 Lisensi
MIT License — bebas dipakai, dimodifikasi, didistribusikan.

---

> Dibangun dengan ♥ oleh **Hilarius Christiano Avin Paliling (Xte-1412)**  
> *Powered by Jaou Shingan — Tyrant's Eye* 👁️✨
