# LAPORAN STRUKTUR, ALUR KERJA & PROGRES — BOPEL Automation Toolkit

> Terakhir diupdate: 2026-11-03 (sesi: **Penghapusan mode Bulanan, Rename Scan Kecil -> Scan Kode Pesanan, Pengaman Salah-Mode, Tes Lulus**)
> Riwayat detail per sesi digabung di bawah ini.

## Session Report — 2026-11-03 (MVP 2 Hari: 2 Mode Inventory Scanner)

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
