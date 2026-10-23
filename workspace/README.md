# 📂 Workspace Guide (Panduan Struktur Direktori)

Direktori ini adalah ruang kerja lokal untuk memproses screenshot praktikum menjadi berkas metadata `inisiasi.txt`. Semua file screenshot asli, materi referensi mata kuliah (PDF/PPTX), serta berkas inisiasi yang dihasilkan **bersifat privat dan telah di-ignore oleh Git**.

---

## 🗂️ Struktur Folder Standar

```text
workspace/
├── <COURSE_ID>/                      # Kode mata kuliah (misal: KEPL, PPG)
│   ├── screenshots/                  # Tempat menyimpan tangkapan layar praktikum
│   │   ├── Per1/                     # Subfolder per pertemuan/tugas
│   │   │   ├── 1.png
│   │   │   └── ...
│   │   └── UTS/                      # Contoh: screenshot evaluasi UTS
│   │       ├── 1.png
│   │       └── ...
│   ├── _reference/                   # Berkas referensi praktikum (Opsional)
│   │   ├── modul-praktikum.pdf
│   │   └── slide-materi.pptx
│   └── inisiasi/                     # Output metadata inisiasi hasil generate AI
│       └── Per4.txt                  # Berkas inisiasi untuk downstream generator
```

---

## 📌 Cara Menggunakan

### 1. Menaruh File Screenshot
* Taruh gambar tangkapan layar di dalam:  
  `workspace/<COURSE>/screenshots/<PERTEMUAN>/`
* **Format nama file**:
  * **Urut**: `1.png`, `2.png`, `...`
  * **Atau Raw / Bawaan OS**: `Screenshot 2026-xx-xx.png`.  
    *(Gunakan fitur `python -m src.cli organize` dari Director Mode untuk otomatis merapikan & menyusun ulang file mentah menjadi `1.png` - `N.png` berdasarkan timeline Git!)*

### 2. Menaruh File Referensi (Opsional)
* Jika memiliki slide presentasi dosen, modul PDF praktikum, atau kisi-kisi soal, masukkan ke:  
  `workspace/<COURSE>/_reference/`
* AI akan membaca konteks materi dari folder ini untuk memperkaya analisis visual gambar.

### 3. Mengambil Hasil Generate Inisiasi
* Berkas metadata yang siap dipakai oleh generator laporan downstream akan otomatis tersimpan di:  
  `workspace/<COURSE>/inisiasi/<PERTEMUAN>.txt`

---

## ⚡ Perintah Cepat

```bash
# 1. Pindai daftar screenshot di suatu pertemuan
python -m src.cli scan -c kepl -p Per4

# 2. Preview rencana alur narasi berdasarkan git commit repo target
python -m src.cli plan -c kepl -p UTS -r /path/ke/repo/project

# 3. Otomatis rapikan screenshot raw ke format berurutan (1.png - N.png)
python -m src.cli organize -c kepl -p UTS -r /path/ke/repo/project

# 4. Generate inisiasi.txt cerdas dengan Director Mode
python -m src.cli generate-director -c kepl -p UTS -r /path/ke/repo/project
```
