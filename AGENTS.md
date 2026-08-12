# AGENTS.md — Aturan Kerja untuk Project BOPEL

Ini adalah instruksi permanen untuk AI agent (opencode) yang bekerja di project ini.
Baca dan ikuti aturan ini di **setiap sesi**, tanpa perlu diminta ulang oleh user.

## Tentang Project

BOPEL Automation Toolkit — aplikasi Textual (Python TUI) untuk menjalankan
tools warehouse (`check.py`, `scan.py`) lewat UI sidebar ala VS Code.

Struktur:
- `main.py` — entry point
- `core/` — config loader, logger, launcher, system info
- `ui/` — app.py, sidebar.py, dashboard.py, panels.py (Textual screens & CSS)
- `config.yaml` — daftar tools yang muncul di sidebar
- `logs/` — log file aplikasi

## Aturan Debugging

1. **Jangan fix satu error lalu berhenti.** Textual sering nampilin error
   satu-satu tiap kali di-run (CSS parsing berhenti di error pertama, crash
   berhenti di exception pertama). Setelah fix satu bug, **baca ulang seluruh
   file terkait** (terutama CSS di `ui/dashboard.py` dan semua `id=` widget
   di `ui/sidebar.py`, `ui/dashboard.py`) untuk cari pola bug yang sama,
   bukan cuma baris yang barusan error.

2. **Textual CSS bukan CSS browser.** Textual cuma support subset properti
   tertentu (lihat dokumentasi Textual CSS). Properti umum yang **TIDAK ada**
   di Textual dan sering salah dipakai: `text-transform`, `gap` (pakai
   `grid-gutter`), `box-shadow`, `flex`, `transition`. Sebelum nulis CSS baru,
   cek dulu apakah properti itu valid di Textual.

3. **Widget `id=` punya aturan ketat.** Id di Textual cuma boleh huruf,
   angka, underscore, hyphen — **tidak boleh titik (`.`)** dan tidak boleh
   diawali angka. Kalau id dibuat dari nama file (`check.py`, `scan.py`),
   **selalu sanitize** (contoh: ganti `.` jadi `-`) dan simpan mapping
   id→nama-asli kalau perlu dipakai balik di logic.

4. **Test end-to-end sebelum lapor selesai.** Jalankan aplikasinya
   (`start.bat` atau `python main.py`) sampai tidak crash dan minimal splash
   screen + dashboard bisa muncul, sebelum bilang "sudah fix".

5. **Kalau nemu bug yang sama classnya di lebih dari satu tempat**, fix semua
   sekaligus, jangan tunggu di-report satu-satu oleh user.

## Format Laporan Wajib Setiap Sesi

Setiap kali selesai mengerjakan sesuatu (debugging, fitur baru, refactor),
**tulis/update file `logs/session_report.md`** dengan format ini
(bahasa Indonesia, ringkas, poin-poin):

```markdown
# Session Report — <tanggal & jam>

## Ringkasan
<1-2 kalimat: apa yang dikerjakan sesi ini>

## File yang Diubah
- `path/file.py` — <apa yang diubah dan kenapa>
- `path/file.py` — <apa yang diubah dan kenapa>

## Root Cause Bug (kalau ada bug yang difix)
- Error: `<pesan error asli, singkat>`
- Penyebab: <penjelasan teknis kenapa error muncul>
- Fix: <apa yang diubah untuk memperbaiki>

## Status Testing
- [x] / [ ] Aplikasi jalan tanpa crash (`start.bat`)
- [x] / [ ] Fitur X sudah dicoba dan berfungsi
- [ ] Belum dites: <sebutkan kalau ada>

## Known Issues / Belum Selesai
- <apa yang masih perlu dikerjakan atau berpotensi bug>

## Catatan untuk Sesi Berikutnya
- <hal yang perlu diperhatikan AI/dev berikutnya>
```

**Jangan overwrite laporan sesi sebelumnya** — tambahkan entry baru di atas
(paling baru di atas), supaya `session_report.md` jadi riwayat semua sesi.

## Kenapa Ini Penting

User membawa laporan ini ke sesi lain (termasuk ke AI lain) untuk melanjutkan
kerjaan tanpa AI itu perlu membaca ulang seluruh codebase dari nol. Laporan
yang jelas dan jujur (termasuk yang belum kelar / belum dites) jauh lebih
berguna daripada laporan yang keliatan lengkap tapi menyembunyikan masalah.
