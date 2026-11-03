# LAPORAN STRUKTUR, ALUR KERJA & PROGRES — BOPEL Automation Toolkit

> Terakhir diupdate: 2026-11-03 (sesi: **Fix Chrome store opening, window activation guard, shlex split regex, fallback_jalan parity, test suite 11/11 PASS, konsolidasi laporan & cleanup**)
> Riwayat detail per sesi digabung di bawah ini.

## Session Report — 2026-11-03

### Ringkasan
Fix Chrome store opening issues (Ctrl+L selecting suggestions), window activation guard, shlex split regex, fallback_jalan parity in shopee_fetch, test suites passing, report consolidation into LAPORAN_PROYEK.md, and codebase cleanup.

### Root Cause Bug yang Difix
- (a) `shlex.split(posix=False)` memecah argumen `--profile-directory="Profile 7"` karena tanda kutip ganda menyisakan karakter `7"`, menyebabkan Chrome membuka profil cacat/tab `7"`.
- (b) `activate_window()` mengembalikan `True` meskipun `SetForegroundWindow` ditolak oleh Windows foreground lock restriction.
- (c) Jalur `Ctrl+L` di address bar Chrome bisa menyeleksi saran omnibox / dropdown pencarian alih-alih URL yang disiapkan.

### Status Testing
- [x] Test suite 11/11 file PASS (`PYTHONUTF8=1`)
- [ ] E2E nyata dengan Chrome toko (butuh izin user dan penutupan tab `7"` lama)

---

## 1. STRUKTUR PROYEK

```
C:\robot\bopel\
│
├── app.py                     # ENTRY POINT AKTIF — pywebview window + class Api (bridge Python↔JS)
├── start.bat                  # Launcher Windows: chcp 65001 + auto-relaunch Windows Terminal → app.py
├── start_debug.bat            # Varian start dengan konsol/debug
├── main.py                    # Entry point UI Textual lama (fallback, masih jalan)
├── start_tui.bat              # Launcher UI Textual lama
├── config.yaml                # SATU SUMBER KEBENARAN: tools, modes, stores
├── requirements.txt           # Dependency di-pin
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
├── ui/                        # UI Textual LAMA (fallback, dipertahankan sampai migrasi terverifikasi)
│   ├── app.py                 # BopelApp: routing screen + launcher messages
│   ├── dashboard.py           # Semua Screen + CSS Textual
│   ├── sidebar.py             # Sidebar gaya VS Code
│   ├── panels.py              # InfoPanel, LogPanel, HelpPanel
│   ├── messages.py            # Message classes Textual
│   └── theme.py               # Token warna
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
│   └── cek_kode.py            # Util cek kode pesanan (jika ada)
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
├── mcp/bopel_ui_tester/       # MCP server uji UI Textual headless (Bagian A)
│
└── hasil_scan*.xlsx           # OUTPUT produksi — JANGAN dihapus/ditimpa manual
```

---

## 2. ARSITEKTUR & ALUR KERJA (FLOW)

### 2.1 Lapisan & Prinsip
- **Isolasi proses** — tool jalan di subprocess terisolasi (`CREATE_NO_WINDOW + SW_HIDE`, `PYTHONUTF8=1`).
- **Satu sumber konfigurasi** — `config.yaml` via `core/config.py`.
- **UI-agnostic core** — `core/launcher.py` bebas dari Textual/pywebview.
- **Fail-safe di trust boundary** — validasi input clipboard sebelum dipakai.

### 2.2 Alur Tool Utama
- **`check.py`**: Checklist pesanan + validasi harga Shopee vs app.
- **`scan.py` & `scan_bulanan.py`**: Inventory scanner (2 mode auto-detect: besar via Excel, kecil via daftar kode) dengan checkpoint resume opt-in (`--resume`).
- **`shopee_fetch.py`**: Auto-fetch income Shopee via Playwright + Chrome profile toko (0 `.fill()` / `.type()`, read-only login polling, trim tabel income).
- **`screenshot_iklan.py`**: Screenshot chart dashboard iklan per toko & rentang tanggal (direct Chrome profile launch via `.lnk` parsing + fallback keystroke + foreground validation).

---

## 3. PENGUJIAN & TEST SUITE (11/11 PASS)

| File Test | Status |
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

### Sesi 2026-11-02 — Retur `scan_bulanan.py`
- Masalah: mode Bulanan mencatat retur sebagai `TIDAK ADA FAKTUR` karena blok deteksi retur Excel income hanya ada di `scan.py`.
- Root cause: modul bulanan tidak menyertakan sinkronisasi titik deteksi retur.
- Fix: port titik deteksi retur ke `scan_bulanan.py` dan penambahan test AST (`test_retur_bulanan.py`).

### Sesi 2026-10-03 — Resume Opt-in & NameError Fix
- Masalah: `NameError: tanggal_dilepas_map` karena auto-resume checkpoint dieksekusi sebelum map diinisialisasi.
- Root cause: urutan eksekusi variabel state vs pengecekan checkpoint.
- Fix: pindah deklarasi map ke atas blok checkpoint; resume jadi `--resume` (opt-in).

### Sesi 2026-09-12 — Fix NOT FOUND Palsu & Newline Literal
- Masalah: sel grid berisi newline literal memecah 1 baris logis jadi 2 baris, menyebabkan false Not Found.
- Root cause: parsing baris tabel grid tidak memperhitungkan newline internal.
- Fix: `core/parsing.gabungkan_baris_terpecah()` + `cari_baris_memo_terpecah()`.

### Sesi 2026-08-19 — Auto-Fetch Shopee & Profile Lock
- Masalah: Chrome profile terkunci (lockfile/SingletonLock) dan error `--profile-directory`.
- Root cause: proses Chrome sebelumnya masih menahan lock profil toko.
- Fix: `_press()` graceful WM_CLOSE, tunggu lockfile hilang, launch persisten context tanpa konflik.

### Sesi 2026-08-13 — Keamanan Clipboard & Fail-safe
- Masalah: teks acak di clipboard dapat tertulis ke search box aplikasi warehouse produksi.
- Root cause: kurangnya validasi di trust boundary input clipboard.
- Fix: 3 lapis pengaman di `core/validasi.py` (`validasi_daftar_kode`, `cegah_ketik_tidak_aman`, preview + jeda).

---

## 5. KNOWN ISSUES & CATATAN PENTING

1. **E2E nyata belum dites**: Belum dijalankan dengan window Chrome produksi asli (membutuhkan izin user).
2. **Tab baru Chrome**: Setiap kali `Start` dijalankan untuk tool toko, Chrome membuka tab baru (tab Shopee/iklan menumpuk). Belum ditangani penutupan tab otomatis.
3. **Persiapan sebelum E2E**: User harus menutup semua tab `7"` lama di Chrome sebelum menjalankan E2E nyata agar tidak terjadi konflik profil/tab.
4. **`scan_bulanan.py`**: File ada di disk dan terdaftar di `config.yaml` (mode Bulanan aktif).
