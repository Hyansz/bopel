# LAPORAN STRUKTUR, ALUR KERJA & PROGRES — BOPEL Automation Toolkit

> Terakhir diupdate: 2026-11-03 (sesi: **Recovery & Architectural Cleanup: `core/caption.py`, ModuleNotFoundError Fix, Startup Smoke Test**)
> Riwayat detail per sesi digabung di bawah ini.

## Session Report — 2026-11-03 (Recovery & UI 404 Fix)

### Ringkasan
- Melakukan backup workspace ke `C:\robot\bopel_backup_2_2026-11-03_13-42-46`.
- Mengaudit inventaris file `web/`: `app.js`, `style.css`, dan `index.html`.
- Mengonfirmasi bahwa file `web/index.html` diperlukan oleh pywebview agar server lokal tidak mengembalikan 404 Not Found.
- Memverifikasi Screenshot Iklan (MVP 3) sesuai spesifikasi: jalur utama tanpa Ctrl+A/C identitas dan tanpa aktivasi window lain, snapshot hwnd, `core.caption.py`, marker `SCREENSHOT_IKLAN_TOKO`, `LABEL_DI_GAMBAR=False`, `CHART_CROP=(0.000, 0.113, 1.000, 0.876)`.
- Seluruh test suite (Python & Node), `py_compile`, dan startup smoke test lulus tanpa error.

### Status Testing
- Python test suites (`test_*.py`): PASS.
- Node check (`node --check web/app.js`): OK (exit 0).
- Startup smoke test: PASS.

---

## Session Report — 2026-11-03 (Recovery & Architectural Cleanup)

### Ringkasan
- Memperbaiki `ModuleNotFoundError: No module named 'screenshot_iklan'` pada `app.py` dengan memperbaiki arsitektur import (melarang `app.py` mengimport script tool di root).
- Memindahkan fungsi helper caption ke `core/caption.py`. `app.py` dan `screenshot_iklan.py` kini sama-sama mengimpor `bangun_teks_caption` dari `core.caption`.
- Memulihkan dan menyempurnakan `screenshot_iklan.py` beserta unit test & full-chain simulation test (`test_screenshot_iklan.py`, 37/37 tests PASS).
- Memulihkan `test_fetch_state_timing.js` dan memverifikasi seluruh test suite Node & Python PASS (`PYTHONUTF8=1`).
- Menjalankan startup smoke test (`import app` sukses via subprocess, `app.py` start dan berjalan stabil tanpa crash selama 10+ detik).

### Perbaikan Arsitektur & Aturan
- `app.py` (UI/bridge) dibersihkan dari import script tool root (`screenshot_iklan`, `shopee_fetch`, `scan`, `check`).
- Shared helper `bangun_teks_caption` ditempatkan di `core/caption.py`.

### Status Testing
- Python test suites (`test_*.py`): Semua file PASS.
- Py_compile: Semua file `.py` sukses.
- Node check (`node --check web/app.js`): OK (exit 0).
- Startup smoke test: `app.py` running stable.

---

## Session Report — 2026-11-03 (MVP 3: Screenshot Iklan & Bugfix)

### Ringkasan
- Memperbaiki bug `TypeError: _open_store_url() takes 4 positional arguments but 5 were given` di `screenshot_iklan.py` (signature `_open_store_url` belum disesuaikan untuk menerima parameter `used_hwnds` yang dikirim dari `_capture_store`).
- Menambahkan **tes rantai penuh (full-chain simulation test)** di `test_screenshot_iklan.py` yang menjalankan `main()` untuk 3 toko palsu dengan mock batas terluar (`launch_url_in_profile`, `_chrome_windows`, `ensure_foreground`, `win32gui`, `pyautogui`, `ImageGrab`, `Config.stores`, dll.).
- Menambahkan **tes tanda tangan murni (signature test)** menggunakan `inspect.signature` untuk memastikan parameter `used_hwnds` wajib ada pada `_open_store_url` dan mencegah regresi sejenis.
- Memverifikasi seluruh 12 test suite PASS (37/37 tests untuk `test_screenshot_iklan.py`, 4/4 untuk `test_copy_image.py`, 13/13 untuk `test_chrome_launch.py`, serta seluruh test suite lainnya exit 0).
- Py_compile semua file `.py` sukses, `node --check web/app.js` sukses (exit 0), dan `app.py` berhasil di-import.

### Root Cause Bug `TypeError`
- Pada penambahan pelacakan `used_hwnds` untuk mencegah window-hopping antar toko pada jalur utama, pemanggilan `_open_store_url(shortcut, name, akun, url, used_hwnds)` mengirimkan 5 argumen, namun definisi fungsi `_open_store_url` tertinggal 4 argumen. Selain itu, pengujian sebelumnya belum mencakup eksekusi rantai penuh `main()` sehingga lolos dari unit test.

### File yang Diubah
- `screenshot_iklan.py`: Sinkronisasi signature `_open_store_url` menerima `used_hwnds: set[int]`.
- `test_screenshot_iklan.py`: Penambahan tes tanda tangan (`inspect.signature`) dan simulasi rantai penuh `main()` (jalur utama 3 toko & jalur fallback).
- `LAPORAN_PROYEK.md`: Pencatatan sesi.

### Status Testing
- Semua 12 file test PASS (`PYTHONUTF8=1`).
- Py_compile sukses.
- Node check sukses.

---

### Ringkasan
- Menghapus mode Bulanan (`scan_bulanan.py`, `_test_bulanan_multiitem.py`, `_verify_c_bulanan.py`) sesuai permintaan MVP. Inventory Scanner kini hanya memiliki 2 mode: **Scan Kode Pesanan** (sebelumnya Scan Kecil) dan **Scan Detail**.
- Merename "Scan Kecil" menjadi "Scan Kode Pesanan" di `config.yaml` dan dokumentasi.
- Menambahkan **pengaman salah-mode** di `scan.py` (via env var `BOPEL_SCAN_MODE` dari `app.py` / `ToolLauncher`):
  - Mode **Scan Detail** tetapi clipboard TIDAK berisi tabel Excel mutasi Shopee (kolom 'No. Pesanan') → berhenti (`exit 1`) dengan pesan panduan.
  - Mode **Scan Kode Pesanan** tetapi clipboard berisi tabel Excel mutasi → berhenti (`exit 1`) dengan pesan panduan.
- Memperbarui unit test (`test_retur_scan.py`, `test_resume_flag.py`, `test_notfound_tanggal.py`, `test_tanggal_pelunasan.py`) agar menargetkan `scan.py` semata tanpa ketergantungan pada `scan_bulanan.py`.
- **File Data Bulanan User**: File `hasil_scan_bulanan.xlsx` (24.198 bytes), `hasil_scan_bulanan_1.xlsx` (29.363 bytes), dan `checkpoint_scan_bulanan.xlsx` (6.299 bytes) **TIDAK dihapus** (tetap utuh di disk). User dapat memutuskan apakah ingin menghapusnya nanti atau mempertahankannya sebagai arsip.

### File yang Dihapus / Diubah
- **Dihapus**: `scan_bulanan.py`, `_test_bulanan_multiitem.py`, `_verify_c_bulanan.py`.
- **Diubah**: `config.yaml`, `scan.py`, `core/launcher.py`, `app.py`, `web/app.js`, `test_retur_scan.py` (dulu `test_retur_bulanan.py`), `test_resume_flag.py`, `test_notfound_tanggal.py`, `test_tanggal_pelunasan.py`, `docs/CONFIG_SCHEMA.md`, `LAPORAN_PROYEK.md`.

### Status Testing
- Semua 12 test file lulus: **13/13**, **4/4**, **32/32**, dll. Total pass.
- Py compile semua `.py` sukses tanpa error.
- `node --check web/app.js` sukses.

---

## 1. STRUKTUR PROYEK

```
C:\robot\bopel\
│
├── app.py                     # ENTRY POINT AKTIF — pywebview window + class Api (bridge Python↔JS)
├── start.bat                  # Launcher Windows: chcp 65001 + auto-relaunch Windows Terminal → app.py
├── start_debug.bat            # Varian start dengan konsol/debug
├── config.yaml                # SATU SUMBER KEBENARAN: tools, modes, stores
├── requirements.txt           # Dependency di-pin (pyyaml, psutil, pywebview, pyautogui, pyperclip, pywin32, playwright, PIL, ...)
├── AGENTS.md                  # Aturan kerja permanen untuk AI agent (termasuk prinsip ponytail)
├── opencode.json              # Konfigurasi opencode + plugin ponytail
├── LAPORAN_PROYEK.md          # Dokumen konsolidasi proyek (file tunggal laporan)
│
├── core/                      # Modul inti — UI-agnostic, dipakai app.py maupun tool
│   ├── config.py              # Config singleton + validasi config.yaml (ConfigError)
│   ├── launcher.py            # ToolLauncher/ToolRunner: subprocess hidden, reader thread, stop/kill, extra_env
│   ├── logger.py              # AppLogger: rotating log → logs/app.log
│   ├── observ.py              # Screenshot kegagalan (budget 5/run), metrik, tunggu_grid_respon
│   ├── parsing.py             # Parsing MURNI clipboard grid + deteksi/catatan retur Shopee
│   ├── system.py              # Info sistem: CPU, RAM, Python, OS
│   ├── validasi.py            # GERBANG WAJIB validasi clipboard (fail-safe) — jangan disederhanakan
│   └── window.py              # Auto window-activation Windows (win32gui) pengganti alt-tab
│
├── web/                       # SPA untuk pywebview
│   ├── index.html             # Shell: sidebar, 4 section, panel tool
│   ├── style.css              # Design system (token, layout, komponen)
│   ├── app.js                 # Semua state UI + pemanggilan window.pywebview.api.*
│   └── fonts/                 # Inter, JetBrains Mono, Space Grotesk (lokal, tanpa CDN)
│
├── Tool otomatisasi (root, dijalankan sebagai subprocess):
│   ├── check.py               # Checklist pesanan + validasi harga Shopee vs app
│   ├── scan.py                # Scan status pembayaran/faktur + validasi Excel (2 mode: Scan Kode Pesanan & Scan Detail)
│   ├── shopee_fetch.py        # Auto-fetch income Shopee via Playwright + Chrome profile toko
│   ├── screenshot_iklan.py    # Screenshot chart dashboard iklan per toko & rentang tanggal
│   ├── calibrate_chart_crop.py# Tool sekali-pakai kalibrasi crop chart (tidak di config.yaml)
│   └── cek_kode.py            # Util cek kode pesanan
│
├── test_*.py                  # Test/self-check (tanpa framework berat)
├── _verify_*.py               # Harness E2E UI (window asli / DOM)
├── _test_*.py                 # Harness simulasi tool (mock I/O)
│
├── docs/                      # CONFIG_SCHEMA.md, DESIGN_SYSTEM.md, PYWEBVIEW_BUILD.md
├── logs/
│   ├── app.log                # Log runtime (rotating)
│   ├── metrics.json           # 1 baris JSON per run (metrik)
│   ├── .active_store.json     # State toko + rentang tanggal terakhir
│   ├── screenshots/           # Screenshot observability + hasil Screenshot Iklan
│   └── historical_backup/     # Backup output lama (tidak disentuh)
│
├── hooks/                     # Plugin hooks (ponytail)
└── hasil_scan*.xlsx           # OUTPUT produksi — JANGAN dihapus/ditimpa manual
```

---

## 2. ARSITEKTUR & ALUR KERJA (FLOW)

### 2.1 Lapisan & Prinsip
- **Isolasi proses** — tool jalan di subprocess terisolasi (`CREATE_NO_WINDOW + SW_HIDE`, `PYTHONUTF8=1`).
- **Satu sumber konfigurasi** — `config.yaml` via `core/config.py`.
- **UI-agnostic core** — `core/launcher.py` bebas dari Textual/pywebview.
- **Fail-safe di trust boundary** — validasi input clipboard sebelum dipakai.
- **Single UI (pywebview)** — berbasis `app.py` dan SPA `web/`.

### 2.2 Alur Tool Utama
- **`check.py`**: Checklist pesanan + validasi harga Shopee vs app.
- **`scan.py`**: Inventory scanner (2 mode: **Scan Kode Pesanan** & **Scan Detail**) dengan checkpoint resume opt-in (`--resume`) dan pengaman salah-mode clipboard.
- **`shopee_fetch.py`**: Auto-fetch income Shopee via Chrome profile toko (0 `.fill()` / `.type()`, read-only login polling, passive window wait pada jalur utama, trim tabel income).
- **`screenshot_iklan.py`**: Screenshot chart dashboard iklan per toko & rentang tanggal (direct Chrome profile launch via `.lnk` parsing + fallback keystroke + foreground validation).

---

## 3. PENGUJIAN & TEST SUITE

| File Test | Status / Count |
|---|---|
| `test_chrome_launch.py` | 13/13 PASS |
| `test_copy_image.py` | 4/4 PASS |
| `test_gabungkan_baris_terpecah.py` | PASS (exit 0) |
| `test_notfound_tanggal.py` | PASS (exit 0) |
| `test_resume_flag.py` | PASS (exit 0) |
| `test_retur_scan.py` | PASS (exit 0) |
| `test_scan_parse.py` | PASS (exit 0) |
| `test_screenshot_iklan.py` | 32/32 PASS |
| `test_shopee_fetch.py` | PASS (exit 0) |
| `test_tanggal_pelunasan.py` | PASS (exit 0) |
| `test_web_daterange.py` | PASS (exit 0) |
| `test_webindex_path.py` | PASS (exit 0) |

---

## 4. RIWAYAT SESI & ROOT CAUSE PENTING (2026-08 s/d 2026-11)

### Sesi 2026-11-03 (MVP 2 Hari) — Hapus Mode Bulanan & Pengaman Salah-Mode
- **Pekerjaan**: Menghapus mode Bulanan (`scan_bulanan.py`, tes terkait), merename "Scan Kecil" menjadi "Scan Kode Pesanan", menambahkan pengaman salah-mode berbasis `BOPEL_SCAN_MODE` di `scan.py` & `launcher.py`, dan memperbarui seluruh unit test.
- **File Data Bulanan**: Mempertahankan file `hasil_scan_bulanan*.xlsx` & `checkpoint_scan_bulanan.xlsx` di disk untuk keputusan user.

### Sesi 2026-11-03 (Sesi Sebelumnya) — Penghapusan Textual & E2E Lolos
- Penghapusan total UI Textual lama (`main.py`, `ui/`, `start_tui.bat`, `mcp/bopel_ui_tester`). E2E nyata Screenshot Iklan & Fetch dikonfirmasi user **LOLOS**.

### Sesi 2026-11-02 — Retur `scan.py`
- Porting deteksi retur Excel income ke `scan.py` sehingga retur tanpa faktur tercatat `RETUR`, bukan `TIDAK ADA FAKTUR`.

---

## 5. KNOWN ISSUES & CATATAN PENTING

1. **Tab baru Chrome**: Setiap kali `Start` dijalankan untuk tool toko, Chrome membuka tab baru (tab Shopee/iklan menumpuk). Belum ditangani penutupan tab otomatis.
2. **File Data Bulanan**: `hasil_scan_bulanan.xlsx`, `hasil_scan_bulanan_1.xlsx`, dan `checkpoint_scan_bulanan.xlsx` tetap tersimpan di root proyek sebagai arsip/data historis user.
