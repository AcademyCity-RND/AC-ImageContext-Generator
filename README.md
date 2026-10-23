# 👁️ ImageContext-Generator (ICG)
### *Jaou Shingan Context Synthesizer Engine*

Generator otomatis untuk mengekstrak konteks visual dari serangkaian gambar tangkapan layar praktikum (`1.png` - `x.png`) menjadi berkas metadata `inisiasi.txt` terstruktur, yang siap diumpankan ke tool generator laporan utama.

---

## 📌 Spesifikasi Utama & Master PRD
Dokumentasi lengkap, batasan sistem, diagram alur, dan kontrak format data tersedia di:
👉 **[`PRD.md`](./PRD.md)**

---

## 🚀 Quick Start

### Prasyarat
- Python 3.11+
- Google API Key (Gemini 1.5 Flash Free Tier) → set di `.env` sebagai `GOOGLE_API_KEY`

### Instalasi
```bash
git clone https://github.com/AcademyCity-RND/ImageContext-Generator.git
cd ImageContext-Generator
pip install -r requirements.txt
cp .env.example .env
# Edit .env dan isi GOOGLE_API_KEY
```

### Struktur Workspace (Contoh)
```
workspace/
├── KEPL/
│   ├── screenshots/
│   │   ├── Per1/ (1.png, 2.png, ...)
│   │   ├── Per2/
│   │   └── Per4/ (1.png - 17.png)
│   ├── inisiasi/
│   │   ├── Per1.txt
│   │   └── Per4.txt
│   └── _reference/
│       ├── Pertemuan-02-Manajemen GitHub & Prinsip CI.pdf
│       └── Pertemuan-04-CI-CD untuk Vue.js.pdf
└── PPG/
    ├── screenshots/
    │   └── Per1/ ...
    ├── inisiasi/
    └── _reference/
        └── PPG_Materi_Pertemuan 1.pdf ...
```

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

## 🗺️ Rencana Pengembangan (Roadmap)

### ✅ v0.1.0 — MVP (Selesai)
- [x] Scanner screenshot berurutan (1.png ... x.png)
- [x] Vision Engine dengan Google Gemini 1.5 Flash
- [x] Knowledge Manager (YAML + PDF reference extraction)
- [x] CLI: `scan`, `generate`, `list-courses`
- [x] Course configs: KEPL, PPG
- [x] Tested: KEPL Per4 (17 screenshots → 17 entries)

### 🔄 v0.2.0 — Kualitas & Robustness (Next)
- [ ] **Retry & Backoff** untuk Vision API (handle rate limit/timeout)
- [ ] **Fuzzy PDF-to-Pertemuan Mapping** (auto-match referensi yang nama file-nya tidak cocok persis)
- [ ] **Validation Mode**: bandingkan output dengan `inisiasi.txt` ground truth (Per1-Per3) untuk hitung akurasi
- [ ] **Batch Generate**: satu perintah generate semua pertemuan sekaligus (`generate -c kepl --all`)

### 🎯 v0.3.0 — Multi-Provider & UX
- [ ] Support OpenAI GPT-4o-mini / Anthropic Claude sebagai fallback vision provider
- [ ] Interactive TUI mode (`python -m src.cli interactive`)
- [ ] Export format JSON/Markdown selain plain text
- [ ] Watch mode: auto-generate saat ada screenshot baru ditambah

### 🚀 v1.0.0 — Production Ready
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
