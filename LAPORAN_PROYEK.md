# LAPORAN STRUKTUR, ALUR KERJA & PROGRES — BOPEL Automation Toolkit

> Terakhir diupdate: 2026-08-12
> Riwayat detail per sesi ada di `logs/session_report.md` (paling baru di atas).

---

## 1. STRUKTUR PROYEK

```
C:\robot\bopel\
│
├── main.py               # Entry point Textual app (python main.py / start.bat)
├── start.bat             # Launcher Windows: chcp 65001, auto-relaunch ke Windows Terminal
├── config.yaml           # SUMBER konfigurasi tools di sidebar (nambah tool = edit file ini)
├── requirements.txt      # textual, rich, pyyaml, psutil
├── AGENTS.md             # Aturan kerja permanen untuk AI agent
├── LAPORAN_PROYEK.md     # File ini
│
├── core/                 # Modul inti (bukan UI, bukan tool)
│   ├── config.py         # Config loader/singleton dari config.yaml (105 baris)
│   ├── launcher.py       # ToolLauncher: subprocess Popen, reader thread, stop/kill (206 baris)
│   ├── logger.py         # AppLogger: rotating file log -> logs/app.log (59 baris)
│   └── system.py         # Info sistem: CPU, RAM, Python, waktu, nama terminal (49 baris)
│
├── ui/                   # Lapisan Textual
│   ├── app.py            # BopelApp: routing menu -> screen, launcher messages (100 baris)
│   ├── dashboard.py      # Semua Screen + CSS app (456 baris) — Splash, Dashboard, Tool, Log, Settings
│   ├── sidebar.py        # Sidebar VS Code-style, daftar tools dari config.yaml (104 baris)
│   └── panels.py         # InfoPanel, LogPanel, HelpPanel (104 baris)
│
├── tools (di folder root, dijalankan sebagai subprocess terpisah):
│   ├── check.py          # Checklist Automation (599 baris) — validasi harga Shopee vs app
│   ├── scan.py           # Inventory Scanner (1209 baris) — scan status pembayaran + validasi Excel
│   └── scan_bulanan.py   # Varian bulanan (927 baris) — TIDAK lagi di sidebar (hidden di config.yaml)
│
├── logs/
│   ├── app.log           # Log runtime aplikasi (rotating, 5MB x 3 backup)
│   └── session_report.md # Riwayat laporan semua sesi kerja (16+ sesi, 686 baris)
│
└── hasil_scan*.xlsx      # OUTPUT data scan (jangan dihapus)
```

### Arsitektur (ringkas)
- **TUI (Textual)** memisahkan diri dari **tools otomatisasi (pyautogui)** — tools jalan di subprocess terisolasi, jadi tombol Stop benar-benar mematikan proses, bukan cuma UI.
- **1 sumber kebenaran konfigurasi**: `config.yaml`. Sidebar di-generate dari `tools:` di file itu.
- **Tools tidak terdaftar di file konfigurasi manapun** — launcher resolve script langsung dari folder root proyek.

---

## 2. ALUR KERJA (WORKFLOW)

### 2.1 Jalankan aplikasi
```
double-click start.bat
   → chcp 65001 (UTF-8)
   → auto-relaunch ke Windows Terminal (kalau belum)
   → python main.py
        → Config.load() (config.yaml)
        → Splash screen → auto-transition → Dashboard
```

### 2.2 Navigasi UI
- **Sidebar kiri** (ala VS Code): daftar tools dari config.yaml + menu Logs & Settings.
- **Panah ↑/↓** = cycling fokus antar tombol menu sidebar (BINDINGS priority).
- **?** = toggle HelpPanel di tiap screen. **q** = quit.
- Dashboard menampilkan System Info (CPU, RAM, Python, waktu real-time).

### 2.3 Menjalankan tool (alur launcher)
```
Klik tombol tool di sidebar
   → MenuSelected -> BopelApp._open_tool_screen() -> ToolScreen
   → Klik Start -> ToolLauncher.start()
        → resolve_script (harus ada di root)
        → subprocess.Popen([python, -u, script], stdout=PIPE)
        → reader thread post ToolOutput line-by-line ke UI (streaming)
        → proses selesai -> ToolFinished (success = exit code 0)
   → Klik Stop -> proc.terminate() → proc.kill() kalau timeout
   → Output juga di-append ke _global_log (LogScreen)
```

### 2.4 Alur kerja tools otomatisasi (check.py / scan.py)
```
1. User copy data pesanan dari aplikasi Shopee (clipboard)
2. Script pakai pyautogui untuk interaksi GUI aplikasi warehouse target:
     - search kode pesanan di kotak search
     - safe_copy() (validasi clipboard dengan sentinel anti data basi)
     - baca baris grid (Ctrl+A / per-baris), parse harga/status/retur
3. Validasi: harga aplikasi vs harga Excel (mode skala besar)
     - Mode kecil: tanpa Excel, validasi antar-baris
     - Gabung baris duplikat (GABUNG_ROW_DUPLIKAT) kalau 1 kode muncul >1 baris
4. Output:
     - Log/ringkasan di CMD (streaming ke UI)
     - Excel: hasil_scan.xlsx / hasil_scan_bulanan.xlsx (+ sheet Rekap Harga)
     - Checkpoint (load/resume kalau scan terputus)
```

### 2.5 Debugging (aturan AGENTS.md)
1. Jangan berhenti setelah 1 error — Textual menampilkan error satu-satu per run; baca ulang file terkait untuk pola bug yang sama.
2. Textual CSS ≠ CSS browser (tidak ada `gap`, `flex`, `transition`, `box-shadow`).
3. Widget `id=` harus disanitize (tidak boleh titik/diawali angka).
4. Test end-to-end dulu baru lapor selesai.
5. Bug sekelas difix di semua tempat sekaligus.

---

## 3. PROGRES YANG SUDAH DILAKUKAN

### Ringkasan status: ✅ UI + launcher + logika scan stabil (headless test semua PASS)
### ⏳ Satu-satunya yang belum: **test manual end-to-end scan.py dengan pyautogui + aplikasi warehouse asli**

### 3.1 Timeline sesi (terbaru → terlama)

| Tanggal | Pekerjaan | Status |
|---|---|---|
| 2026-08-04 10:34 | `scan.py`: harga Excel jadi acuan utama validasi duplikat; flag "TERDETEKSI DATA DUPLIKASI" + statistik 🚨 + kolom `JumlahCocokExcel` (checkpoint 14 kolom) | ✅ 25/25 unit test, smoke tests PASS |
| 2026-08-04 09:15 | `scan.py`: gabung row duplikat (`pilih_baris_primary`, DOUBLE FAKTUR/CEK MANUAL di kolom REVISI, toggle `GABUNG_ROW_DUPLIKAT`) | ✅ 25/25 unit test, smoke PASS |
| 2026-08-04 08:20 | Verifikasi headless menyeluruh UI + launcher + Stop button (cmd) | ✅ |
| 2026-08-03 11:23 | `scan.py`: fix false NOT FOUND (race condition) — retry + `RE_SEARCH_KONFIRMASI`, delay dinaikkan | ✅ (manual belum) |
| 2026-07-31 17:20 | `scan_bulanan.py`: hapus penjumlahan harga multi-item → `pilih_baris_primary` (faktur dobel) | ✅ simulasi 3 kode OK |
| 2026-07-31 16:10 | `scan_bulanan.py`: fix SELISIH palsu 2x lipat (`hitung_harga_order`, dedupe berbasis Excel) | ✅ 7/7 unit test |
| 2026-07-31 15:30 | Hapus blank row pemisah grup SALES di `scan.py` & `scan_bulanan.py` (bug sekelas difix di 2 tempat) | ✅ |
| 2026-07-31 15:00 | `scan_bulanan.py`: logic kode pesanan ganda (multi-item) | ✅ 12/12 unit test |
| 2026-07-31 14:20 | Sembunyikan "Scan Bulanan" dari sidebar (edit config.yaml saja) | ✅ |
| 2026-07-31 14:00 | Cleanup: hapus `menu.py` (redundan), hapus `__pycache__` | ✅ |
| 2026-07-31 13:30 | Root cause "menu baru tidak muncul": sidebar digenerate dari config.yaml, bukan menu.py | ✅ |
| 2026-07-29 00:00 | Border `tall` → `round` di dashboard.py & panels.py | ✅ (visual perlu cek manual) |
| 2026-07-28 23:30 | Fix teks button tengah → `content-align: left middle` (Textual ≠ CSS browser) | ✅ |
| 2026-07-28 23:00 | Align sidebar title/subtitle kiri | ✅ |
| 2026-07-28 22:15 | Fix judul duplikat dashboard + gabung label sidebar | ✅ |
| 2026-07-28 21:30 | Fix "Press any key..." nyangkut → tambah `cls` di start.bat | ✅ |
| 2026-07-28 20:00 | Sidebar BINDINGS ↑/↓ + start.bat UTF-8 + auto-relaunch Windows Terminal | ✅ |
| 2026-07-25 10:00 | `scan.py`: fitur rekap total harga (CMD + sheet "Rekap Harga") | ✅ (manual belum) |
| 2026-07-23 16:00 | Fix layout menumpuk vertikal → Horizontal `.main-row` di semua screen | ✅ |
| 2026-07-23 15:30 | Fix crash `_app_header()` (query `.header-time` → `#header-time`) + audit menyeluruh | ✅ |
| 2026-07-23 14:00 | Launcher rewrite: `exec_module` → `subprocess.Popen` + fix race condition `proc.poll()` | ✅ 4/4 unit test |
| 2026-07-23 12:00 | Debugging menyeluruh: fix `query_one(".header-time")` crash, audit ID & CSS | ✅ |

### 3.2 Fitur kunci yang sudah ada
- **UI**: Splash → Dashboard (System Info live), sidebar navigable keyboard, HelpPanel, LogScreen, SettingsScreen, custom header (bukan Header bawaan).
- **Launcher**: subprocess terisolasi, streaming output, Stop = terminate+kill, double-start prevention, missing script → error message (bukan crash).
- **scan.py**: safe_copy anti-clipboard-basi, 2-fase find_data_row anti false NOT FOUND, gabung baris duplikat dengan prioritas harga Excel, alert duplikasi tervalidasi, checkpoint backward-compatible (9→11→13→14 kolom), rekap harga, fallback mode kecil tanpa Excel.
- **scan_bulanan.py**: pilih baris Sudah untuk faktur dobel (tanpa penjumlahan), multi-item dengan MAX_ITEM_PER_ORDER=15 (logika lama, nonaktif dari sidebar).
- **check.py**: checklist pesanan + validasi harga, alert ⚠️ DUPLIKAT VALID.

### 3.3 Known Issues / Yang belum selesai
1. **Test manual end-to-end scan.py asli** (pyautogui + aplikasi warehouse) — belum pernah dilakukan dari semua sesi. Skenario uji sudah disiapkan di laporan sesi 2026-08-04 10:34 (kode 3-baris, verifikasi Sudah + REVISI DOUBLE FAKTUR/CEK MANUAL).
2. Order GENUINE multi-item dengan harga beda akan di-cap CEK MANUAL (aman, tapi butuh konfirmasi kalau kasus ini muncul di data real).
3. Checkpoint lama (9/11 kolom) bisa di-load, tapi field baru (`JumlahCocokExcel`) = 0 untuk item lama.
4. Visual layout (border round, alignment) belum pernah diverifikasi manual oleh user (dari sesi 07-29/07-28).

### 3.4 Rekomendasi sesi berikutnya
- Prioritas #1: test manual scan.py di environment pyautogui — pastikan kode split faktur jadi **Sudah** + kolom REVISI "DOUBLE FAKTUR", dan tidak ada NOT FOUND palsu.
- Kalau NOT FOUND palsu masih muncul: naikkan `DELAY_AFTER_ENTER` (0.7 → 0.8–1.0).
- Toggle cepat: `GABUNG_ROW_DUPLIKAT = False` (kembali ke ambil baris pertama), `RE_SEARCH_KONFIRMASI = False` (lebih cepat, rawan NOT FOUND palsu).
- Nambah tool ke sidebar = edit `config.yaml` saja (script taruh di root).
