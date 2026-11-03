# LAPORAN STRUKTUR, ALUR KERJA & PROGRES — BOPEL Automation Toolkit

> Terakhir diupdate: 2026-11-03 (sesi: **Penghapusan UI Textual lama, update AGENTS.md, E2E Screenshot Iklan & Fetch Lolos dikonfirmasi user**)
> Riwayat detail per sesi digabung di bawah ini.

## Session Report — 2026-11-03 (Final Phase)

### Ringkasan
Penghapusan total UI Textual lama (`main.py`, folder `ui/`, `start_tui.bat`, dan `mcp/bopel_ui_tester`) setelah migrasi penuh ke pywebview + SPA (`app.py` + `web/`). E2E nyata untuk Screenshot Iklan dan Fetch telah dikonfirmasi user **LOLOS** (tidak ada tab `7"`, tidak pindah profil).

### Root Cause Terbukti
- **Fallback `_wait_store_window`** yang aktif terlalu cepat (>4s) memicu enumerasi `chrome_windows()` dan verifikasi identitas `Ctrl+A/C` pada jalur utama, menyebabkan window switching dan keystroke tidak terduga saat user mengisi password popup.
- **Solusi**: parameter `verify_identity=False` pada jalur utama (`launch_url_in_profile`) membuat proses menunggu window secara pasif tanpa keystroke.

### File yang Diubah / Dihapus
- **Dihapus**: `main.py`, folder `ui/`, `start_tui.bat`, folder `mcp/bopel_ui_tester`, `test_copy_image.py` (dibuat ulang versi murni helper).
- **Diubah**: `shopee_fetch.py`, `test_copy_image.py`, `requirements.txt` (hapus `textual` & `rich`), `AGENTS.md`, `LAPORAN_PROYEK.md`.

### Status Testing
- Semua 12 test file lulus: **13/13**, **4/4**, **32/32**, **104/104** total pass.
- E2E nyata Screenshot Iklan & Fetch: **LOLOS** (dikonfirmasi user).

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
│   ├── launcher.py            # ToolLauncher/ToolRunner: subprocess hidden, reader thread, stop/kill
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
│   ├── scan.py                # Scan status pembayaran/faktur + validasi Excel (2 mode auto-detect)
│   ├── scan_bulanan.py        # Varian bulanan (klon scan.py + delta header/checkpoint/output)
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
│   ├── validasi_bulanan/      # Bukti hasil validasi mode Bulanan
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
- **`scan.py` & `scan_bulanan.py`**: Inventory scanner (2 mode auto-detect) dengan checkpoint resume opt-in (`--resume`).
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
| `test_retur_bulanan.py` | PASS (exit 0) |
| `test_scan_parse.py` | PASS (exit 0) |
| `test_screenshot_iklan.py` | 32/32 PASS |
| `test_shopee_fetch.py` | PASS (exit 0) |
| `test_tanggal_pelunasan.py` | PASS (exit 0) |
| `test_web_daterange.py` | PASS (exit 0) |
| `test_webindex_path.py` | PASS (exit 0) |

---

## 4. RIWAYAT SESI & ROOT CAUSE PENTING (2026-08 s/d 2026-11)

### Sesi 2026-11-03 — Penghapusan Textual & E2E Lolos
- **Pekerjaan**: Penghapusan total UI Textual lama (`main.py`, `ui/`, `start_tui.bat`, `mcp/bopel_ui_tester`). E2E nyata Screenshot Iklan & Fetch dikonfirmasi user **LOLOS** (tidak ada tab `7"`, tidak pindah profil).
- **Fix Fetch**: Menambahkan parameter `verify_identity=False` pada jalur utama `_wait_store_window` agar tidak memicu fallback enumerasi window atau Ctrl+A/C saat user mengisi password popup.

### Sesi 2026-11-02 — Retur `scan_bulanan.py`
- Porting deteksi retur Excel income ke `scan_bulanan.py` sehingga retur tanpa faktur tercatat `RETUR`, bukan `TIDAK ADA FAKTUR`.

### Sesi 2026-10-03 — Resume Opt-in & NameError Fix
- Pindah deklarasi map ke atas blok checkpoint; resume jadi `--resume` (opt-in).

### Sesi 2026-09-12 — Fix NOT FOUND Palsu & Newline Literal
- Penanganan newline internal dalam sel grid via `core/parsing.gabungkan_baris_terpecah()`.

### Sesi 2026-08-19 — Auto-Fetch Shopee & Profile Lock
- Otomasi Chrome profile toko dengan penanganan lockfile dan WM_CLOSE graceful.

### Sesi 2026-08-13 — Keamanan Clipboard & Fail-safe
- 3 lapis pengaman `core/validasi.py` untuk mencegah clipboard tak valid diketik ke aplikasi produksi.

---

## 5. KNOWN ISSUES & CATATAN PENTING

1. **Tab baru Chrome**: Setiap kali `Start` dijalankan untuk tool toko, Chrome membuka tab baru (tab Shopee/iklan menumpuk). Belum ditangani penutupan tab otomatis.
2. **`scan_bulanan.py`**: File ada di disk dan terdaftar di `config.yaml` (mode Bulanan aktif).
