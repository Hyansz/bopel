"""Bopel Automation Toolkit — entry point pywebview (migrasi dari Textual TUI).

Run with:  python app.py
Atau:      start.bat (diubah di Fase 5 migrasi)

Bridge js_api (class Api) — method dipanggil JS via window.pywebview.api.*.
- get_config(): sidebar dinamis dari config.yaml (Fase 1)
- start_tool/stop_tool: ToolLauncher yang SAMA dengan Textual (core/launcher.py,
  refactor callback-based Fase 2) — bridge cuma pemicu; seluruh logic keamanan
  (validasi clipboard, auto window-activation, BOPEL_UI_MODE=1, subprocess
  hidden) tetap di dalam tool/launcher.
- get_system_info/get_settings_info: dari core/system.py & core/config.py yang
  ADA (bukan rewrite).
"""

from __future__ import annotations

import json
import os
import re
import sys
import threading
import time
from pathlib import Path

from core.config import Config, ConfigError
from core.launcher_cb import ToolLauncher
from core.window import activate_window, find_target_window
from core.system import (
    cpu_percent,
    current_date,
    current_time,
    os_info,
    python_version,
    ram_percent,
    ram_total_gb,
    ram_used_gb,
    terminal_name,
)

def _web_index_path() -> Path:
    """Resolve path web/index.html untuk dua skenario jalan:

    - python app.py (non-frozen): relatif ke file ini.
    - exe PyInstaller (frozen): `web/` diekstrak ke sys._MEIPASS via
      --add-data "web;web" (lihat docs/PYWEBVIEW_BUILD.md). sys._MEIPASS
      ada di mode onefile & onedir; fallback ke folder exe kalau aneh-aneh.

    Dipisah jadi fungsi supaya bisa di-test tanpa build exe (lihat
    test_webindex_path.py) — jalankan python test_webindex_path.py.
    """
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        base = Path(sys._MEIPASS)
    else:
        base = Path(__file__).resolve().parent
    return base / "web" / "index.html"


_WEB_INDEX = _web_index_path()


def png_to_dib_bytes(path) -> bytes:
    """Baca gambar (PNG/JPG/etc) → byte DIB siap kirim ke clipboard CF_DIB.

    CF_DIB = BitmapInfoHeader (40 byte) + data piksel bottom-up, tanpa header
    file BMP (14 byte). PIL sudah ada di requirements (MCP test + screenshot).
    Dipisah jadi fungsi murni supaya bisa di-test tanpa desktop session
    (see test_copy_image.py) — konversi & ekstraksi DIB diuji di sini.
    """
    from io import BytesIO
    from PIL import Image
    img = Image.open(path).convert("RGB")
    with BytesIO() as buf:
        img.save(buf, "BMP")
        data = buf.getvalue()
    if data[:2] != b"BM":
        raise ValueError("hasil konversi BMP tidak valid (kurang magic 'BM')")
    return data[14:]  # buang header file BMP, sisakan DIB


def _dropfiles_header() -> bytes:
    """Header DROPFILES (20 byte) untuk CF_HDROP: offset data + fWide=1
    (path berikutnya UTF-16). Fungsi terpisah supaya bisa diuji tanpa
    clipboard (lihat test_copy_image.py check_hdrop)."""
    import ctypes
    from ctypes import wintypes

    class DROPFILES(ctypes.Structure):
        _fields_ = [
            ("pFiles", wintypes.DWORD),
            ("pt", wintypes.POINT),
            ("fNC", wintypes.BOOL),
            ("fWide", wintypes.BOOL),
        ]

    df = DROPFILES()
    df.pFiles = ctypes.sizeof(df)  # data path mulai tepat setelah header
    df.fWide = True                # path UTF-16 (Unicode)
    return bytes(df)


def make_hdrop_bytes(paths: list[str]) -> bytes:
    """Bangun payload CF_HDROP (file drop) dari daftar path file.

    Format: header DROPFILES + daftar path absolut UTF-16 di-null-
    terminate, diakhiri double-null. Hasil paste di app penerima = FILE
    (bisa 3 foto berbeda sekaligus), BUKAN satu gambar gabungan. Fungsi
    murni — diuji test_copy_image.py check_hdrop().
    """
    if not paths:
        raise ValueError("butuh minimal 1 path file")
    data = ("\0".join(paths) + "\0").encode("utf-16-le") + b"\0\0"
    return _dropfiles_header() + data


def png_to_data_uri(path) -> str:
    """Baca file gambar → data URI base64 (`data:image/png;base64,...`).

    Preview screenshot (2026-09-03): `<img src>` TIDAK boleh pakai file://
    di pywebview/WebView2 — permission & encoding path Windows (backslash,
    spasi) bikin broken image icon. Paling reliable: kirim base64 image
    langsung sebagai data URI ke elemen <img>, bebas masalah
    permission/path. Hanya digunakan untuk display; tombol Salin ke
    Clipboard tetap pakai path asli (app.copy_image → CF_DIB).
    """
    import base64
    with open(path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("ascii")
    return f"data:image/png;base64,{b64}"




# Dry-run untuk pywebview: set env BOPEL_PYWEBVIEW_DRY_RUN=1 sebelum
# menjalankan app → tombol Start TIDAK meluncurkan subprocess / pyautogui
# (simulasi streaming + finish saja). Default (env tidak diset) = perilaku
# produksi: Start memicu tool asli (check.py/scan.py) terhadap aplikasi
# warehouse. Pola ini sejalan dengan BOPEL_UI_TEST_ALLOW_REAL_LAUNCH milik
# MCP bopel_ui_tester, tapi khusus lapisan bridge pywebview.
_DRY_RUN = os.environ.get("BOPEL_PYWEBVIEW_DRY_RUN") == "1"


class Api:
    """Bridge Python ↔ JS (window.pywebview.api.*)."""

    def __init__(self, launcher: ToolLauncher) -> None:
        self.launcher = launcher
        # Log global aplikasi (alur tool) — sumber data Logs screen (Fase 4).
        # Append dari reader thread + baca dari JS thread: GIL membuat
        # list.append atomik; baca via salinan list().
        self._global_log: list[str] = []
        # Window pywebview — di-set lewat bind_window() setelah create_window.
        self._window = None
        # State streaming (per tool run) — dipakai callback reader thread.
        self._summary: dict[str, str | None] = {"total": None, "ok": None, "notfound": None, "beda": None, "durasi": None}
        self._banner_text: str | None = None
        self._dry_stop = False  # dry-run: user klik Stop → hentikan simulasi
        # ── data terstruktur per-item (fitur salin per kolom) ────────────
        # Parsing dari baris TABEL RINGKASAN yang sudah dicetak scan.py /
        # scan_bulanan.py (print_summary_table) dan check.py (tabel harga)
        # — TIDAK mengubah format output tool, cukup parse apa yang dicetak.
        # Kolom scan: NO | NOMOR FAKTUR | KODE PESANAN | CUSTOMER | SALESMAN
        # | STATUS BAYAR | VALIDASI HARGA (App vs Excel) | DUPLIKAT ROW.
        # Kolom check: NO | KODE PESANAN | HARGA APLIKASI | HARGA SHOPEE |
        # COCOK. Item disimpan per run key (konsisten toolStates JS) dan
        # di-push SATU KALI saat tool selesai (bukan reparse per klik).
        self._items: dict[str, list[dict]] = {}
        self._table_cols: dict[str, list[str]] = {}  # header tabel aktif per run key (anti campur 2 tool paralel)
        self._table_num_re = re.compile(r"(\d[\d.,]*)")
        self._shopee_re = re.compile(r"Excel:\s*(?:Rp\s*)?(\d[\d.,]*)")  # '⚠ App:X vs Excel:Y' (harga bisa 'Rp39.550')
        self._ok_eq_re = re.compile(r"OK\s*\(\s*(\d[\d.,]*)\s*=\s*(?:Rp\s*)?(\d[\d.,]*)\s*\)")
        # Screenshot Iklan (2026-09-03): path PNG per toko yang dicetak tool
        # di stdout (marker `📌 SCREENSHOT_IKLAN_FILE: <path>`) → dikirim ke
        # JS utk preview thumbnail + tombol salin gambar ke clipboard. Bisa
        # BANYAK file per run (loop semua toko), jadi disimpan sebagai LIST
        # per run key (urutan = urutan toko; lihat screenshot_iklan.py).
        self._screenshot_files: dict[str, list[str]] = {}
        self._screenshot_re = re.compile(r"SCREENSHOT_IKLAN_FILE:\s*(.+)$")
        # ── port dari ui/dashboard.py ToolScreen._SUMMARY_PATTERNS (Fase 3,
        # jangan rewrite kalau sudah benar) ──
        self._summary_patterns = (
            (re.compile(r"Total nomor unik tersisa untuk discan\s*:\s*(\d+)"), "total"),
            (re.compile(r"^Total\s*:\s*(\d+)"), "total"),
            (re.compile(r"Ketemu\s*:\s*(\d+)\s*/\s*(\d+)"), "ok_total"),
            (re.compile(r"Final\s*:\s*(\d+)\s*/\s*(\d+)"), "ok_total"),
            (re.compile(r"Status OK\s*:\s*(\d+)"), "ok"),
            (re.compile(r"Tidak\s*:\s*(\d+)"), "notfound"),
            (re.compile(r"Not Found\s*:\s*(\d+)"), "notfound"),
            (re.compile(r"🟢 Sukses\s*:\s*(\d+)"), "ok"),
            (re.compile(r"🟢 Sudah\s*:\s*(\d+)"), "ok"),
            (re.compile(r"🟡 Cek manual\s*:\s*(\d+)"), "beda"),
            (re.compile(r"🟡 Belum\s*:\s*(\d+)"), "beda"),
            # "≠ Beda   : 3 (tidak di-checklist)" (check.py) — item ketemu tapi
            # harga beda / butuh cek manual. BELUM ada di Textual (ui/dashboard.py
            # _SUMMARY_PATTERNS cuma 4 metrik) — card ke-5 ini fitur baru, bukan
            # regresi migrasi.
            (re.compile(r"Beda\s*:\s*(\d+)"), "beda"),
            (re.compile(r"Waktu\s*:\s*([\d.,]+)\s*detik"), "durasi"),
        )
        self._banner_pattern = re.compile(r"(SEMUA VALID|berhasil dibuat|tersalin ke clipboard)", re.IGNORECASE)

    def bind_window(self, window) -> None:
        """Set referensi window pywebview (dipanggil setelah create_window)."""
        self._window = window

    def bring_to_front(self) -> None:
        """Bawa window BOPEL ke depan & normal (tidak minimized).

        Dipakai di 2 tempat:
        - Kelompok A1 (startup): window kadang kebuka minimized / ke
          belakang saat start.bat dijalankan -> jangan andalkan default OS.
        - Kelompok A2 (tool selesai): selama tool jalan, window aplikasi
          warehouse yang di-fokus (core/window.py activate_window), jadi
          window BOPEL kemungkinan besar tertutup/ke belakang. Dipanggil
          saat status jadi Finished ATAU Failed (bukan cuma sukses).

        Aman dipanggil dari background thread (reader thread / event
        handler): pywebview restore/show di-marshal ke UI thread via
        Form.Invoke (backend winforms); TOPMOST toggle + SetForeground-
        Window pakai win32 langsung (core/window.py, pola yang SAMA dengan
        aktivasi window warehouse) — itu murni user32, tanpa perlu UI
        thread.
        """
        w = self._window
        if w is None:
            return
        # 1) Normalisasi state dulu: restore() = WindowState Normal (no-op
        #    kalau emang lagi normal), show() = Show + Activate (winforms).
        try:
            w.restore()
        except Exception:
            pass
        try:
            w.show()
        except Exception:
            pass
        # 2) Paksa ke foreground: cari HWND by judul + activate_window
        #    (SW_RESTORE kalau minimized -> SetForegroundWindow -> fallback
        #    TOPMOST toggle lawan foreground-lock Windows).
        try:
            ketemu = find_target_window("Bopel Automation Toolkit")
            if ketemu:
                activate_window(ketemu[0])
        except Exception:
            pass

    def copy_text(self, text: str) -> dict:
        """Salin teks ke clipboard via pyperclip (tombol 'Salin Log').

        Kelompok C: log panel harus bisa di-copy buat kerja manual (detail
        item Beda/Cek Manual). Pyperclip sudah dipakai tool scan/check;
        jalan juga di pywebview (backend WebView2 gak bisa dijamin punya
        navigator.clipboard di context file://, dan context menu kanan
        di-disable pywebview di mode produksi).
        """
        try:
            import pyperclip
            pyperclip.copy(text or "")
            return {"ok": True}
        except Exception as exc:
            return {"ok": False, "message": str(exc)}



    def copy_files(self, paths_json: str) -> dict:
        """Salin DAFTAR FILE ke clipboard sebagai CF_HDROP (file drop).

        Screenshot Iklan revisi 2026-09-17: user mau sekali salin = 3 FOTO
        BERBEDA (per toko), bukan 1 gambar gabungan — Windows clipboard
        cuma muat 1 gambar per format, tapi bisa muat BANYAK FILE. Paste
        di WA/Telegram/Explorer/dokumen mengeluarkan semua file sekaligus
        (chat apps menampilkannya sebagai foto terpisah per toko).
        Path absolut wajib; file yang tidak ada di-skip.

        GlobalAlloc/GlobalLock/GlobalUnlock DIAMBIL dari kernel32 (ctypes),
        BUKAN win32clipboard — module itu tidak punya atribut tersebut
        (bug terverifikasi runtime 2026-09-17). Payload dari
        make_hdrop_bytes(); roundtrip GetClipboardData(CF_HDROP) sudah
        diverifikasi mengembalikan daftar path yang benar.
        """
        try:
            import ctypes

            import win32clipboard
            import win32con
            raw = json.loads(paths_json or "[]")
            paths = [str(p).strip() for p in raw if p and os.path.exists(p)]
            if not paths:
                return {"ok": False, "message": "tidak ada file screenshot yang valid"}
            payload = make_hdrop_bytes(paths)
            GMEM_MOVEABLE, GMEM_DDESHARE = 0x0002, 0x2000
            kernel32 = ctypes.windll.kernel32
            kernel32.GlobalAlloc.restype = ctypes.c_void_p
            kernel32.GlobalAlloc.argtypes = [ctypes.c_uint, ctypes.c_size_t]
            kernel32.GlobalLock.restype = ctypes.c_void_p
            kernel32.GlobalLock.argtypes = [ctypes.c_void_p]
            kernel32.GlobalUnlock.argtypes = [ctypes.c_void_p]
            win32clipboard.OpenClipboard()
            try:
                win32clipboard.EmptyClipboard()
                h = kernel32.GlobalAlloc(
                    GMEM_MOVEABLE | GMEM_DDESHARE, len(payload)
                )
                if not h:
                    return {"ok": False, "message": "GlobalAlloc gagal"}
                ptr = kernel32.GlobalLock(h)
                if not ptr:
                    return {"ok": False, "message": "GlobalLock gagal"}
                ctypes.memmove(ptr, payload, len(payload))
                kernel32.GlobalUnlock(h)
                win32clipboard.SetClipboardData(win32clipboard.CF_HDROP, h)
            finally:
                win32clipboard.CloseClipboard()
            return {"ok": True, "count": len(paths)}
        except Exception as exc:
            return {"ok": False, "message": str(exc)}

    def _push_js(self, script: str) -> None:
        """Kirim JS ke window. Aman dari background thread: backend
        edgechromium me-marshal via Control.Invoke (diverifikasi dari source
        pywebview 6.2.1, Fase 1). Guard try/except untuk teardown / page
        belum loaded — push di-skip diam-diam kalau window tak siap.
        """
        w = self._window
        if w is None:
            return
        try:
            w.evaluate_js(script)
        except Exception:
            pass

    def _parse_summary(self, line: str) -> dict | None:
        """Port dari ui/dashboard.py ToolScreen._parse_summary — mengisi
        self._summary dan return snapshot kalau ada yang cocok."""
        for pattern, key in self._summary_patterns:
            m = pattern.search(line)
            if not m:
                continue
            if key == "ok_total":
                self._summary["ok"] = m.group(1)
                self._summary["total"] = m.group(2)
            else:
                self._summary[key] = m.group(1)
            return {k: v for k, v in self._summary.items() if v is not None}
        return None

    # ── parsing data terstruktur per-item (salin per kolom) ─────────────
    # State machine per baris stream: header tabel ringkasan memicu
    # capture; baris `| ... |` dipecah jadi item; baris `+---` menutup.
    # Tidak mengubah format output tool — hanya membaca apa yang dicetak.
    def _table_start(self, rk: str, cols: list[str]) -> bool:
        """True kalau baris ini header tabel ringkasan scan/check (kolom
        pertama 'NO' + ada 'KODE PESANAN'). Simpan header per run key
        biar 2 tool paralel tidak saling menimpa state parse."""
        if len(cols) >= 4 and cols[0] == "NO" and any("KODE PESANAN" in c for c in cols):
            self._table_cols[rk] = cols
            self._items[rk] = []
            return True
        return False

    def _split_row(self, line: str) -> list[str] | None:
        """Split baris tabel `| a | b | ... |` -> list sel ter-strip.
        None kalau bukan baris data/header tabel (mis. `+----+`)."""
        s = line.strip()
        if not s.startswith("|"):
            return None
        cells = [c.strip() for c in s.split("|")]
        # `|` di ujung menghasilkan string kosong pertama & terakhir
        if len(cells) >= 2 and cells[0] == "" and cells[-1] == "":
            return cells[1:-1]
        return None

    def _norm_num(self, raw: str) -> str:
        """Normalisasi angka harga ("Rp 50.000" / "200000" / "1,5") ->
        digit murni ("50000"). Baris sejajar: string kosong kalau kosong."""
        raw = (raw or "").strip()
        if not raw:
            return ""
        m = self._table_num_re.search(raw)
        if not m:
            return ""
        s = m.group(1)
        # desimal 2 digit di ujung ("83,513.00" / "1.234,56") = desimal,
        # buang dulu sebelum separator dibersihin (kalau tidak, 2 nol
        # desimal ikut terhitung -> salah 100x).
        if re.search(r"[.,]\d{2}$", s):
            s = s[:-3]
        return s.replace(".", "").replace(",", "")

    def _parse_table_line(self, rk: str, line: str) -> None:
        """Proses satu baris stream untuk struktur per-item. Dipanggil di
        on_output & _simulate_run SETIAP baris (cheap: regex + split)."""
        cells = self._split_row(line)
        if cells is None:
            return
        if self._table_start(rk, cells):
            return
        cols = self._table_cols.get(rk)
        if cols is None or len(cells) != len(cols):
            return
        # baris separator `+----+` -> sel-nya mulai '+', bukan data
        if not cells[0] or cells[0].startswith("+"):
            return
        d = dict(zip(cols, cells))

        def col(name: str) -> str:
            return d.get(name, "")

        kode = col("KODE PESANAN")
        no_faktur = col("NOMOR FAKTUR")
        status = col("STATUS BAYAR")  # scan: '🟢 Sudah' / '🟡 Belum' / '🔴 Not Found'
        validasi = col("VALIDASI HARGA (App vs Excel)")
        duplikat = col("DUPLIKAT ROW")
        harga_shopee_raw = col("HARGA SHOPEE")  # check.py: kolom eksplisit
        cocok = col("COCOK")  # check.py: OK/BEDA/?

        # Kategori OK vs Beda/Cek Manual — dipakai dropdown filter.
        # scan.py: OK (app=excel) / SELISIH (App:X vs Excel:Y) / '-' (mode
        # kecil tanpa Excel) + DUPLIKAT 'cek manual' (multi-item genuin).
        # Not Found juga masuk Beda/Cek Manual (termasuk cek manual) —
        # kode ikut disalin, harga/fakturnya kosong (baris tetap sejajar).
        kode = kode if kode and kode != "-" else ""
        if not kode:
            return
        cek_manual = "cek manual" in duplikat.lower()
        if "Not Found" in status or "🔴" in status:
            kategori = "bedacek"
        elif "SELISIH" in validasi or validasi.startswith("⚠") or cek_manual:
            kategori = "bedacek"
        elif cocok == "BEDA" or cocok == "?":
            kategori = "bedacek"
        else:
            kategori = "ok"

        # Harga Shopee: scan.py pakai harga EXCEL (dari data Shopee) yang
        # muncul di kolom validasi ('OK (150000 = 150000)' / 'App:X vs
        # Excel:Y'); check.py punya kolom HARGA SHOPEE eksplisit.
        if harga_shopee_raw:
            harga = self._norm_num(harga_shopee_raw)
        else:
            m = self._ok_eq_re.search(validasi)
            if m:
                harga = self._norm_num(m.group(2))
            else:
                m2 = self._shopee_re.search(validasi)
                harga = self._norm_num(m2.group(1)) if m2 else ""

        # No Faktur: scan.py kolom eksplisit; check.py TIDAK mencetak
        # faktur -> string kosong (baris tetap ikut supaya sejajar).
        no_faktur = no_faktur if no_faktur and no_faktur != "-" else ""
        item = {"kode": kode, "harga_shopee": harga, "no_faktur": no_faktur, "kategori": kategori}
        self._items.setdefault(rk, []).append(item)

    def _push_items(self, rk: str) -> None:
        """Kirim struktur per-item ke JS — DIPANGGIL SATU KALI saat tool
        selesai (on_finished / akhir simulasi), bukan per baris."""
        self._push_js(f"pushItems({json.dumps(rk)}, {json.dumps(self._items.get(rk, []))})")

    def _reset_table_state(self, rk: str) -> None:
        self._items[rk] = []
        self._table_cols[rk] = []
        self._screenshot_files[rk] = []

    # ── config (Fase 1) ───────────────────────────────────────────────
    def get_config(self) -> dict:
        """Serialize config.yaml (meta app + daftar tools) untuk render sidebar.

        Source of truth tetap config.yaml lewat core/config.py — method ini
        hanya memformat ulang ke JSON-friendly dict.

        ensure_loaded() (pola yang sama dipakai check.py/scan.py) supaya
        Api TIDAK pernah melayani default diam-diam (version 0.0.0 / tools
        kosong) kalau Config.load() belum sempat dipanggil — mis. Api
        dibangun di luar main() (test/harness). Di jalur normal app.py
        main() sudah Config.load(), jadi ini no-op.
        """
        Config.ensure_loaded()
        return {
            "app": {
                "name": Config.app_name(),
                "version": Config.app_version(),
                "subtitle": Config.app_subtitle(),
            },
            "tools": Config.tools(),
            "stores": Config.stores(),
        }

    def set_active_store(self, name: str | None, start_date: str = "", end_date: str = "") -> dict:
        """Simpan pilihan toko + date range Auto-Fetch Shopee (selector UI).

        Ditulis ke logs/.active_store.json — dibaca shopee_fetch.py /
        screenshot_iklan.py saat tool dijalankan. File runtime, bukan
        config: pilihan user, bukan konfigurasi. start_date/end_date
        format ISO YYYY-MM-DD (dari <input type="date"> UI); kosong =
        fetch tanpa dateRange (perilaku lama).

        name kosong/None (2026-09-17): Screenshot Iklan tidak milih toko
        di UI (loop semua toko 1→2→3) — cukup rentang tanggal. Key 'name'
        tak ditulis; screenshot_iklan.py sudah pilih toko sendiri.
        """
        try:
            if name:
                stores = Config.stores()
                if not any(s.get("name") == name and s.get("enabled") for s in stores):
                    return {"ok": False, "message": f"Toko '{name}' tidak dikenal / tidak aktif"}
            from pathlib import Path
            path = Path(Config.logs_dir()) / ".active_store.json"
            data: dict = {"name": name} if name else {}
            if start_date and end_date:
                data["start_date"] = str(start_date)
                data["end_date"] = str(end_date)
            path.write_text(json.dumps(data), encoding="utf-8")
            return {"ok": True}
        except Exception as exc:
            return {"ok": False, "message": str(exc)}

    # ── tool lifecycle (Fase 2; streaming output = Fase 3) ────────────
    def start_tool(self, script: str, run_key: str | None = None) -> dict:
        """Start tool via ToolLauncher yang SAMA seperti Textual pakai.

        Fase 3: callback reader thread (background) push baris output,
        ringkasan, status & banner ke JS via evaluate_js (thread-safe di
        backend edgechromium — diverifikasi).

        `run_key` (Kelompok D): identitas run untuk state front-end —
        script yang sama bisa punya beberapa mode (mis. scan.py dipakai
        mode 'Scan Kecil' & 'Scan Detail'; scan_bulanan.py mode 'Scan
        Bulanan'), jadi key-nya unik per (tool, mode), bukan cuma nama
        script. Kosong = key-nya script itu sendiri. Semua push JS
        (appendLogLine/updateSummaryCards/onToolStarted/onToolFinished)
        membawa run_key ini supaya front-end menyimpan state per mode.

        Kalau BOPEL_PYWEBVIEW_DRY_RUN=1: TIDAK meluncurkan apa pun —
        simulasi streaming (aman diklik, tidak menyentuh aplikasi warehouse).
        """
        self._summary = {"total": None, "ok": None, "notfound": None, "beda": None, "durasi": None}
        self._banner_text = None
        self._dry_stop = False
        rk = run_key or script
        self._reset_table_state(rk)

        if _DRY_RUN:
            self._simulate_run(script, rk)
            return {"ok": True, "message": "started (dry-run)"}

        def on_output(line: str) -> None:
            self._global_log.append(line)
            # Kelompok B/D: push JS bawa run_key (unik per tool+mode)
            # supaya front-end simpan state per run, bukan satu state global.
            self._push_js(f"appendLogLine({json.dumps(rk)}, {json.dumps(line)})")
            snapshot = self._parse_summary(line)
            if snapshot:
                self._push_js(f"updateSummaryCards({json.dumps(rk)}, {json.dumps(snapshot)})")
            if self._banner_text is None and self._banner_pattern.search(line):
                self._banner_text = line.strip()
            # struktur per-item (salin per kolom) — parse dari tabel yang
            # dicetak tool; disimpan per run, dikirim sekali saat selesai.
            self._parse_table_line(rk, line)
            # Screenshot Iklan — tangkap path file PNG dari marker stdout
            # (bisa BANYAK per run: loop semua toko → list per run key).
            m = self._screenshot_re.search(line)
            if m:
                self._screenshot_files.setdefault(rk, []).append(m.group(1).strip())

        def on_started(name: str) -> None:
            self._global_log.append(f"[RUN] {name}")
            self._push_js(f"onToolStarted({json.dumps(rk)})")

        def on_finished(name: str, success: bool, return_code: int, error: str) -> None:
            mark = "OK" if success else "FAIL"
            extra = f" — {error}" if error else ""
            self._global_log.append(f"[{mark}] {name} finished (exit {return_code}){extra}")
            self._push_js(
                f"onToolFinished({json.dumps(rk)}, {json.dumps(success)}, {json.dumps(error)}, {json.dumps(self._banner_text)})"
            )
            # struktur per-item dikirim SEKALI di sini (bukan per baris)
            self._push_items(rk)
            # Screenshot Iklan — kirim DAFTAR path PNG + data URI (base64) utk
            # preview. Data URI dipakai src <img> (file:// gagal di WebView2:
            # broken image). Label preview diambil JS dari nama file
            # (mengandung nama toko). Gagal salin tidak menggagalkan run
            # (screenshot per toko tetap ada di logs/screenshots/iklan/).
            paths = self._screenshot_files.get(rk) or []
            if paths:
                items = []
                for path in paths:
                    try:
                        uri = png_to_data_uri(path)
                    except Exception:
                        uri = None
                    items.append({"path": path, "uri": uri})
                self._push_js(
                    f"showScreenshotPreviews({json.dumps(rk)}, {json.dumps(items)})"
                )
                # SALIN SEKALI, FOTO TETAP TERPISAH (2026-09-17): semua PNG
                # toko disalin sekaligus ke clipboard sebagai FILE
                # (copy_files → CF_HDROP) — bukan digabung jadi 1 gambar.
                # Paste di WA/Telegram → keluar 3 foto berbeda per toko.
                if paths:
                    res = self.copy_files(json.dumps(paths))
                    n = res.get("count", len(paths))
                    msg = (
                        f"📌 {n} screenshot tersalin sekaligus ke clipboard ({n} foto berbeda, per toko) — tinggal paste."
                        if res.get("ok")
                        else f"⚠ Gagal salin screenshot ke clipboard: {res.get('message')} — file tetap tersimpan di logs/screenshots/iklan/."
                    )
                    self._global_log.append(msg)
                    self._push_js(f"appendLogLine({json.dumps(rk)}, {json.dumps(msg)})")
            # Kelompok A2: tool selesai (Finished ATAU Failed — bukan cuma
            # sukses) -> window BOPEL kembali ke depan, biar user langsung
            # lihat hasilnya tanpa klik taskbar. Selama tool jalan, window
            # warehouse yang difokus jadi BOPEL tertutup.
            self.bring_to_front()

        extra_env = {}
        if rk and "Scan Detail" in rk:
            extra_env["BOPEL_SCAN_MODE"] = "detail"
        elif rk and ("Scan Kode Pesanan" in rk or "Scan Kecil" in rk):
            extra_env["BOPEL_SCAN_MODE"] = "kecil"

        ok = self.launcher.start(
            script,
            on_output=on_output,
            on_started=on_started,
            on_finished=on_finished,
            extra_env=extra_env,
        )
        if ok:
            return {"ok": True, "message": "started"}
        return {"ok": False, "message": "gagal start (sudah running / script tidak ditemukan)"}

    def _simulate_run(self, script: str, run_key: str | None = None) -> None:
        """Simulasi run di mode dry-run — tanpa subprocess, tanpa pyautogui.

        Meniru streaming tool asli (baris output + summary + banner + status)
        supaya tombol Start / Stop / UI bisa diuji aman. Thread terpisah
        dengan jeda kecil biar streaming-nya terlihat real-time.
        """
        tool = next((t for t in Config.tools() if t.get("script") == script), None)
        name = tool["name"] if tool else script
        rk = run_key or script
        lines = [
            "Total: 2",
            "proses 1/2 ok",
            "Ketemu: 2 / 2",
            "proses 2/2 ok",
            "Sudah: 2",
            "Beda: 0 (tidak di-checklist)",
            "Tidak: 0",
            "Waktu: 1.23 detik",
            "SEMUA VALID — hasil_scan.xlsx berhasil dibuat (DRY-RUN: bot TIDAK dijalankan)",
        ]

        def run() -> None:
            time.sleep(0.2)
            self._global_log.append(f"[RUN] {name} (DRY-RUN)")
            self._push_js(f"onToolStarted({json.dumps(rk)})")
            for ln in lines:
                if self._dry_stop:
                    break
                self._global_log.append(ln)
                self._push_js(f"appendLogLine({json.dumps(rk)}, {json.dumps(ln)})")
                snapshot = self._parse_summary(ln)
                if snapshot:
                    self._push_js(f"updateSummaryCards({json.dumps(rk)}, {json.dumps(snapshot)})")
                if self._banner_text is None and self._banner_pattern.search(ln):
                    self._banner_text = ln.strip()
                self._parse_table_line(rk, ln)
                time.sleep(0.25)
            if self._dry_stop:
                self._global_log.append(f"[STOP] {name} (dry-run)")
                self._push_js(f"onToolFinished({json.dumps(rk)}, false, '', {json.dumps(None)})")
            else:
                self._global_log.append(f"[OK] {name} finished (exit 0) (DRY-RUN)")
                self._push_js(
                    f"onToolFinished({json.dumps(rk)}, true, '', {json.dumps(self._banner_text)})"
                )
            self._push_items(rk)
            # Kelompok A2 (dry-run): sama seperti jalur launcher asli —
            # bawa window BOPEL ke depan pas tool selesai (sukses/gagal).
            self.bring_to_front()

        threading.Thread(target=run, daemon=True).start()

    def stop_tool(self, script: str) -> dict:
        self._dry_stop = True  # dry-run: hentikan simulasi (no-op untuk launcher asli)
        self.launcher.stop(script)
        self._global_log.append(f"[STOP] {script} dihentikan user")
        return {"ok": True, "message": "stopped"}

    def get_logs(self) -> list[str]:
        """Snapshot log global untuk Logs screen."""
        return list(self._global_log)

    # ── system / settings (Fase 2; polling dashboard = Fase 4) ────────
    def get_system_info(self) -> dict:
        return {
            "python": python_version(),
            "os": os_info(),
            "terminal": terminal_name(),
            "date": current_date(),
            "time": current_time(),
            "cpu": f"{cpu_percent():.0f}%",
            "ram": f"{ram_percent():.0f}%  ({ram_used_gb():.1f}/{ram_total_gb():.1f} GB)",
        }

    def get_settings_info(self) -> dict:
        # ensure_loaded() — lihat catatan di get_config().
        Config.ensure_loaded()
        return {
            "app": {"name": Config.app_name(), "version": Config.app_version()},
            "tools": [
                {"name": t.get("name", t["script"]), "script": t["script"]}
                for t in Config.tools()
            ],
            "python": {"version": python_version(), "executable": sys.executable},
        }

    # ── exit ──────────────────────────────────────────────────────────
    def exit_app(self) -> None:
        """Tutup window (lazy import supaya module bisa di-import test)."""
        import webview
        try:
            webview.windows[0].destroy()
        except Exception:
            pass


def _apply_window_icon() -> None:
    """Pasang ikon BOPEL.ico ke window taskbar & title bar via Windows API (WM_SETICON)."""
    if sys.platform != "win32":
        return
    try:
        import ctypes
        ico_path = Path(__file__).resolve().parent / "assets" / "bopel.ico"
        if not ico_path.exists():
            print(f"[WARNING] Ikon {ico_path} tidak ditemukan, lanjut tanpa ikon.")
            return

        user32 = ctypes.windll.user32
        title = "Bopel Automation Toolkit"
        hwnd = None
        for _ in range(50):
            hwnd = user32.FindWindowW(None, title)
            if hwnd:
                break
            time.sleep(0.1)

        if not hwnd:
            return

        IMAGE_ICON = 1
        LR_LOADFROMFILE = 0x0010
        LR_DEFAULTSIZE = 0x0040
        WM_SETICON = 0x0080
        ICON_SMALL = 0
        ICON_BIG = 1

        hicon_small = user32.LoadImageW(
            None, str(ico_path), IMAGE_ICON, 0, 0, LR_LOADFROMFILE | LR_DEFAULTSIZE
        )
        hicon_big = user32.LoadImageW(
            None, str(ico_path), IMAGE_ICON, 0, 0, LR_LOADFROMFILE | LR_DEFAULTSIZE
        )

        if hicon_small:
            user32.SendMessageW(hwnd, WM_SETICON, ICON_SMALL, hicon_small)
        if hicon_big:
            user32.SendMessageW(hwnd, WM_SETICON, ICON_BIG, hicon_big)
    except Exception as exc:
        print(f"[WARNING] Gagal memasang ikon window: {exc}")


def main() -> None:
    import webview  # lazy import supaya `python -c "import app"` tetap ringan
    from core.paste_macro import init_hotkey
    from core.emergency_stop import init_emergency_stop
    try:
        init_hotkey()
    except Exception as exc:
        # Log traceback to startup_error.log without Unicode symbols
        import traceback, os
        log_path = os.path.join(os.path.dirname(__file__), 'logs', 'startup_error.log')
        os.makedirs(os.path.dirname(log_path), exist_ok=True)
        with open(log_path, 'w', encoding='utf-8') as f:
            f.write(traceback.format_exc())
        # Avoid Unicode in console output
        _safe_print = lambda msg: print(msg.encode('ascii', errors='replace').decode('ascii'))
        _safe_print('Error during hotkey initialization (see logs/startup_error.log)')
        # Continue without hotkeys

    try:
        Config.load()  # validasi struktur config.yaml (raise ConfigError kalau invalid)
    except ConfigError as exc:
        # Pesan jelas sebelum app gagal hidup — sama seperti main.py (Textual).
        print(f"\n[ERROR] {exc}")
        sys.exit(1)

    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("BOPEL.Toolkit")
        except Exception:
            pass

    api = Api(ToolLauncher())
    # Daftarkan emergency stop Q dengan referensi ke launcher
    try:
        init_emergency_stop(launcher=api.launcher)
    except Exception as exc:
        print(f"[WARNING] Gagal mendaftarkan emergency stop: {exc}")
    window = webview.create_window(
        "Bopel Automation Toolkit",
        str(_WEB_INDEX),
        js_api=api,
        width=1180,
        height=760,
        min_size=(900, 600),
        resizable=True,
    )
    api.bind_window(window)

    # Kelompok A1: window harus terbuka NORMAL & ke depan — jangan andalkan
    # default OS (bukti pemakaian: start.bat kadang buka window minimized /
    # ke belakang, user harus klik taskbar manual). Dua lapis:
    # 1. events.shown — tepat saat form pertama ditampilkan.
    # 2. Re-assert delay ~1.5 dtk — WebView2 init bisa beberapa detik;
    #    ini nutup race kalau restore pertama kena saat form belum selesai
    #    layout (race diam-diam yang bikin window balik ke belakang).
    window.events.shown += api.bring_to_front
    window.events.shown += lambda: threading.Thread(target=_apply_window_icon, daemon=True).start()

    def _ensure_foreground_delayed() -> None:
        time.sleep(1.5)
        api.bring_to_front()

    threading.Thread(target=_ensure_foreground_delayed, daemon=True).start()
    threading.Thread(target=_apply_window_icon, daemon=True).start()

    webview.start()


if __name__ == "__main__":
    main()
