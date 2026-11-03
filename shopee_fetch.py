"""Auto-Fetch Shopee — ambil data 'Dana Dilepaskan' dari Chrome profile toko.

Dipanggil BOPEL sebagai tool subprocess (stdout di-stream ke UI oleh
core/launcher.py). Alur:

1. Baca config.yaml `stores:` + pilihan toko aktif (`logs/.active_store.json`).
2. Jalankan shortcut .lnk toko dengan os.startfile() — PERSIS double-click
   user (investigasi 2026-08-19: "Toko Alkes Solo.lnk" -> chrome_proxy.exe
   --profile-directory="Profile 7" --ignore-profile-directory-if-not-exists
   <URL>; proses hasil = chrome.exe --source-shortcut=<lnk> --profile-directory
   =Profile 7 ...). SELALU dijalankan — juga saat window sudah terbuka:
   Chrome terbukti menaikkan window profil yang benar (uji empiris
   2026-08-22), dan itulah satu-satunya cara memilih window yang benar
   saat beberapa window toko terbuka dengan judul identik.
3. "Menempel" ke window Chrome toko: tangkap foreground TANPA filter judul,
   VERIFIKASI identitas via token akun toko (config stores[].akun, dibaca
   dari teks halaman Ctrl+A/C) -> baru activate -> Ctrl+L (address bar) ->
   ketik URL income -> Enter -> tunggu load -> Ctrl+A / Ctrl+C -> baca
   clipboard sistem. Sesi login Shopee 100% milik window Chrome ASLI — bot
   tidak pernah masuk lewat CDP/API, tidak ada proses Chrome buatan.
4. Verifikasi teks hasil copy = format blok Dana Dilepaskan (header 'Total
   Penghasilan', kode pesanan 26xxxx) -> salin ke clipboard via pyperclip.
   TIDAK auto-start scan — user klik Scan Kecil.

Navigasi URL ke address bar pakai clipboard paste (pyperclip.copy + Ctrl+V),
BUKAN pyautogui.typewrite — typewrite punya race condition dengan browser/OS
yang bisa kehilangan karakter pertama (domain rusak, DNS_PROBE_FINISHED_NXDOMAIN).

MENGAPA BUKAN Playwright/CDP lagi (investigasi 2026-08-19, data nyata):
- Chrome 151 di mesin ini shared-process: SEMUA profil jalan dalam SATU
  browser process (cmdline '--no-startup-window', TANPA --profile-directory)
  -> deteksi "profil mana yang terbuka" via cmdline MUSTAHIL.
- connect_over_cdp TIDAK MUNGKIN: Chrome 136+ dengan sengaja MENGABAIKAN
  --remote-debugging-port pada user data dir default (kebijakan keamanan,
  developer.chrome.com/blog/remote-debugging-port). Terbukti di mesin ini:
  flag diteruskan utuh ke cmdline tapi port tidak pernah listen.
- launch_persistent_context = proses Chrome buatan dengan flag automation
  (--enable-automation dll.) -> berisiko deteksi anti-bot Shopee.

Audit keamanan (wajib): keyboard yang dipakai bot di window Chrome toko =
Ctrl+L (fokus address bar), ketik URL income (ADDRESS BAR, bukan field
login), Ctrl+A/C (salin halaman). Tidak ada penulisan ke field
password/OTP — login/verifikasi TETAP manual oleh user di window asli.
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlsplit, urlunsplit

from core.config import Config
from core.window import chrome_windows, ensure_foreground, launch_url_in_profile, activate_window

BASE = Path(__file__).resolve().parent
ACTIVE_STORE_FILE = BASE / "logs" / ".active_store.json"

# URL halaman income (Dana Dilepaskan) — type=2 = halaman income, BUKAN
# type=new_cpc_homepage (halaman marketing/PAS yang ada di shortcut .lnk
# toko — shortcut cuma dipakai untuk membuka window, URL income selalu
# diketik ulang oleh bot ke address bar).
INCOME_URL = "https://seller.shopee.co.id/portal/finance/income?type=2"

WINDOW_WAIT = 30          # detik menunggu window Chrome toko muncul setelah startfile
SALAH_ABORT_N = 5         # cek identitas 'salah' beruntun pada hwnd yang sama -> batal
SALAH_ABORT_MIN_S = 15    # tapi tidak sebelum sekian detik: Chrome bisa tertahan
                          # Windows foreground-lock sampai belasan detik sebelum
                          # menaikkan window target (kasus nyata 2026-08-22) —
                          # abort dini malah memotong raise yang sah.
PAGE_LOAD_WAIT = 6        # detik tunggu halaman income selesai load setelah Enter
COPY_RETRIES = 3          # kali coba Ctrl+A/C kalau hasil belum format Dana Dilepaskan
COPY_RETRY_WAIT = 3       # detik antara percobaan copy
COPY_SETTLE = 0.6         # detik setelah Ctrl+C sebelum baca clipboard

# --- Pagination halaman income (INVESTIGASI NYATA 2026-08-19, Chrome toko
# asli, screenshot + copy clipboard sebagai bukti) ---
# Dropdown page-size di kanan-bawah tabel Dana Dilepaskan: opsi 10/20/50,
# default 10/page. MINGGU INI = 24 pesanan: di 10/page hasil Ctrl+A/C cuma
# 10 kode (halaman 1), 14 sisanya HILANG. Di 50/page: 24 kode lengkap.
# Opsi TIDAK persist — reset ke 10/page tiap navigasi ulang, bot harus
# klik tiap fetch. Pagination bar ADA DI BAWAH FOLD setelah load -> wajib
# scroll dulu (metode terverifikasi: klik area aman + PageDown).
# Menu dropdown terbuka ke ATAS (button dekat bottom viewport).
PAGE_SIZE_MAX = 50        # opsi terbesar yang tersedia (10/20/50)
DD_X_OFFSET = 938         # px dari rect.left ke dropdown pagination (window maximized 1448x876)
DD_Y_FROM_BOTTOM = 128    # px dari rect.bottom ke dropdown saat scroll penuh
# (ukurannya: tombol '10/ page' ~30px, center di rect.bottom-128; pakai 120
# sempat MISS 8px di bawah tombol -> menu tidak terbuka -> klik opsi jatuh ke
# baris tabel -> navigasi ke halaman detail. Diverifikasi E2E 2026-08-19.)
OPTION_DX, OPTION_DY = -49, -60  # opsi "50" relatif ke button (menu buka ke atas)
DD_OPEN_WAIT = 1.2        # detik setelah klik dropdown sebelum klik opsi
PAGE_SIZE_SETTLE = 2.5    # detik tunggu tabel re-render setelah pilih 50 (terverifikasi: ~2s cukup)

_KODE_RE = re.compile(r"\b26[A-Z0-9]{12,13}\b")

# --- Post-process hasil Ctrl+A/C (INVESTIGASI NYATA 2026-08-19, clipboard
# clip_50page.txt): Ctrl+A/C menyalin SELURUH halaman income — sidebar,
# search box, tab Pending/Sudah Dilepas, date-range picker, tombol Export,
# pagination, faktur, biaya, dst ikut ter-copy. Struktur baris nyata:
#   [UI ...] 'Cari Pesanan' 'Pending' 'Sudah Dilepas' '17/08/2026 - 19/08/2026'
#   'Pesanan' 'Tanggal Dana Dilepaskan' 'Status' 'Metode Pembayaran'
#   'Total Penghasilan'  <kode> 'Pembeli:<nama>' <tanggal> <status> <metode>
#   'Rp<harga>' [xN blok] '1' '50 / page' 'Catatan Transaksi Penghasilan' [UI]
# _trim_to_income_table memotong ke HANYA header + blok 6 baris per pesanan
# (format SAMA dengan yang dibaca scan.py/check.py). ---
_TABLE_HEADER = (
    "Pesanan",
    "Tanggal Dana Dilepaskan",
    "Status",
    "Metode Pembayaran",
    "Total Penghasilan",
)

# Indikator halaman "minta verifikasi password" (BUKTI NYATA 2026-08-19:
# clipboard hasil copy saat buka URL income — Shopee redirect ke beranda +
# modal 'Untuk melindungi keamanan akun Anda, mohon masukkan password
# Shopee Anda untuk diverifikasi.' + field 'Password'). Frasa ini sangat
# khas — tidak muncul di halaman income/beranda tanpa modal.
_VERIF_PASSWORD_MARKERS = (
    "masukkan password shopee anda untuk diverifikasi",
    "melindungi keamanan akun anda",
)

def _active_store_name() -> str | None:
    """Nama toko yang dipilih user di UI (ditulis bridge set_active_store)."""
    try:
        return json.loads(ACTIVE_STORE_FILE.read_text(encoding="utf-8")).get("name")
    except Exception:
        return None


def _active_store_state() -> dict:
    """State toko + date range pilihan user (logs/.active_store.json,
    ditulis bridge set_active_store saat user pilih toko/klik Fetch).
    Field start_date/end_date format ISO YYYY-MM-DD (dari <input
    type="date">); kosong/tidak ada = fetch tanpa dateRange (perilaku
    lama: rentang default akun)."""
    try:
        data = json.loads(ACTIVE_STORE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return {
        "name": data.get("name"),
        "start_date": str(data.get("start_date") or "").strip(),
        "end_date": str(data.get("end_date") or "").strip(),
    }


def _income_url(start_date: str, end_date: str) -> str:
    """URL income + parameter dateRange kalau rentang tersedia.

    Format dateRange (KONFIRMASI nyata 2026-08-19, buka manual di Chrome
    toko): YYYYMMDD+YYYYMMDD digabung tanpa separator — contoh
    `dateRange=2026081820260818` menampilkan 'Pilih Tanggal:
    18/08/2026 - 18/08/2026'. Parameter dibangun via urllib.parse
    (bukan string-concat) supaya aman saat URL punya param lain.
    start/end kosong -> URL tanpa dateRange (perilaku lama).
    """
    parts = urlsplit(INCOME_URL)
    q = parse_qs(parts.query, keep_blank_values=True)
    if start_date and end_date:
        q["dateRange"] = [start_date.replace("-", "") + end_date.replace("-", "")]
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(q, doseq=True), parts.fragment))


def resolve_store() -> dict:
    """Pilih toko dari config.yaml: pilihan user -> store enabled pertama."""
    stores = Config.stores()
    if not stores:
        print("❌ Tidak ada toko di config.yaml (stores: kosong).")
        print("   Tambahkan toko dulu (lihat docs/CONFIG_SCHEMA.md), lalu jalankan lagi.")
        sys.exit(1)
    picked = _active_store_name()
    for s in stores:
        if s.get("name") == picked and s.get("enabled"):
            return s
    for s in stores:
        if s.get("enabled"):
            return s
    print("❌ Tidak ada toko yang enabled di config.yaml (stores:).")
    print("   Aktifkan minimal 1 toko (enabled: true), lalu jalankan lagi.")
    sys.exit(1)


def _win32():
    """(win32gui, win32con, win32process) — None kalau pywin32 tidak ada
    (lazy, pola sama dengan core/window.py supaya modul tetap testable).
    GetWindowThreadProcessId ada di win32process, BUKAN win32gui."""
    try:
        import win32con
        import win32gui
        import win32process
        return win32gui, win32con, win32process
    except ImportError:
        return None, None, None


def _foreground_chrome_window() -> tuple[int, str] | None:
    """Window Chrome yang jadi FOREGROUND saat ini: (hwnd, title) kalau
    visible + judul mengandung 'Google Chrome' dan BUKAN tab produk
    Google (Sheets/Docs/Slides/Drive/Gmail/YouTube).
    """
    win32gui, _, _ = _win32()
    if win32gui is None:
        return None
    hwnd = win32gui.GetForegroundWindow()
    if not hwnd or not win32gui.IsWindowVisible(hwnd):
        return None
    title = win32gui.GetWindowText(hwnd) or ""
    t = title.lower()
    if "google chrome" not in t or any(p in t for p in (
            "google sheets", "google docs", "google slides", "google drive",
            "google gmail", "google youtube")):
        return None
    return hwnd, title


def _window_identity(hwnd: int, akun: str) -> str:
    """Status identitas window vs akun toko: 'ok' / 'kosong' / 'salah'.

    Cara: activate -> bersihkan clipboard (sentinel) -> Ctrl+A/C -> cari
    token akun di teks halaman. Nama akun SELALU tampil di sidebar seller
    center (ground truth 2026-08-22 dari Ctrl+A/C tiap window: 'tokoa-
    lkessolo', 'tokoalkesbsm', 'alkesmedikasolo').

    - akun kosong (config lama tanpa stores[].akun) -> 'ok' TANPA sentuh
      keyboard (fallback perilaku lama).
    - teks kosong / clipboard tidak berubah -> 'kosong': halaman masih
      load, inconclusive — caller poll ulang (TIDAK dihitung salah).
    - teks ada tapi token tidak ketemu -> 'salah': window milik toko
      lain — caller WAJIB batal, jangan navigasi di window itu.
    """
    if not akun:
        return "ok"
    try:
        import pyautogui
        import pyperclip
    except ImportError:
        print("❌ pyautogui/pyperclip belum terinstall — jalankan: pip install pyautogui pyperclip")
        return "salah"
    # GUARD fokus (race nyata 2026-08-22): os.startfile membuat Chrome
    # menaikkan window target DI WAKTU BERSAMAAN dengan activate_window kita
    # -> Ctrl+A/C bisa terkirim saat z-order masih berubah dan copy gagal
    # senyap (clipboard tetap sentinel). Jangan menilai 'salah' dari kondisi
    # itu: pastikan dulu foreground == hwnd, kalau tidak, activate ulang
    # (maks 3x); gagal juga -> 'kosong' (inconclusive, poll ulang).
    win32gui, _, _ = _win32()
    for _ in range(3):
        if not activate_window(hwnd):
            return "kosong"
        time.sleep(0.5)
        if win32gui is None or win32gui.GetForegroundWindow() == hwnd:
            break
        time.sleep(0.4)
    else:
        return "kosong"
    sentinel = "__BOPEL_IDENTITY_CHECK__"
    try:
        pyperclip.copy(sentinel)
    except Exception:
        pass
    pyautogui.hotkey("ctrl", "a")
    time.sleep(0.15)
    pyautogui.hotkey("ctrl", "c")
    time.sleep(COPY_SETTLE)
    try:
        teks = pyperclip.paste() or ""
    except Exception:
        return "kosong"
    if teks == sentinel or not teks.strip():
        return "kosong"
    return "ok" if akun in teks.lower() else "salah"


def _wait_store_window(name: str, akun: str,
                       timeout: float = WINDOW_WAIT,
                       verify_identity: bool = True,
                       allow_fallback: bool = True) -> tuple[int, str] | None:
    """Cari + VERIFIKASI window Chrome milik toko (TANPA menjalankan shortcut).

    - verify_identity=True: cek token akun via Ctrl+A/C (dipakai jalur fallback / attach).
    - verify_identity=False (jalur utama): tunggu window Chrome muncul secara pasif,
      tanpa keystroke, tanpa verifikasi identitas, tanpa enumerasi window lain.
    """
    deadline = time.monotonic() + timeout
    t_mulai = time.monotonic()
    hwnd_gagal: int | None = None
    n_gagal = 0
    checked: set[int] = set()
    fallback_so = 4.0
    fallback_jalan = False
    while time.monotonic() < deadline:
        cand = _foreground_chrome_window()
        if cand is None:
            hwnd_gagal, n_gagal = None, 0
        else:
            hwnd, title = cand
            if not verify_identity:
                return hwnd, title
            status = _window_identity(hwnd, akun)
            if status == "ok":
                print(f"✔ Window Chrome {name} terverifikasi: '{title}'")
                return hwnd, title
            if status == "salah":
                checked.add(hwnd)
                if hwnd != hwnd_gagal:
                    hwnd_gagal, n_gagal = hwnd, 1
                else:
                    n_gagal += 1
                if n_gagal >= SALAH_ABORT_N and time.monotonic() - t_mulai >= SALAH_ABORT_MIN_S and fallback_jalan:
                    print(f"❌ Window foreground BUKAN {name} — token akun '{akun}' tidak ada di halamannya.")
                    print("   Fetch DIBATALKAN supaya data toko lain tidak ikut ke clipboard.")
                    return None

        if allow_fallback and not fallback_jalan and time.monotonic() - t_mulai >= fallback_so:
            fallback_jalan = True
            for hwnd2, title2 in chrome_windows():
                if hwnd2 in checked or (cand is not None and hwnd2 == cand[0]):
                    continue
                status2 = _window_identity(hwnd2, akun)
                if status2 == "ok":
                    print(f"✔ Window Chrome {name} terverifikasi (fokus dipindahkan): '{title2}'")
                    return hwnd2, title2
                if status2 == "salah":
                    checked.add(hwnd2)
        time.sleep(0.7)

    cw = list(chrome_windows())
    if cw and not verify_identity:
        return cw[0]

    print(f"❌ Window Chrome toko tidak muncul/terverifikasi dalam {timeout:.0f} detik.")
    return None


def _attach_store_window(shortcut: str, name: str, akun: str) -> tuple[int, str] | None:
    """Jalankan shortcut toko (os.startfile, persis double-click user) lalu
    kembalikan window profil toko yang TERVERIFIKASI via _wait_store_window.

    Ini jalur FALLBACK (kalau launch URL langsung gagal).
    """
    print("🪟 Menjalankan shortcut toko persis seperti double-click...")
    try:
        os.startfile(shortcut)
    except Exception as exc:
        print(f"❌ Gagal menjalankan shortcut '{shortcut}': {exc}")
        return None
    return _wait_store_window(name, akun)


def _open_store_url(shortcut: str, name: str, akun: str,
                    url: str) -> tuple[tuple[int, str] | None, bool]:
    """Buka URL income secara deterministik.

    Return ((hwnd, title), perlu_navigasi_keystroke):
    - Jalur UTAMA: Chrome dijalankan dengan argumen .lnk + URL income;
      perlu_navigasi=False.
    - Jalur FALLBACK: launch langsung gagal → startfile .lnk → _wait_store_window;
      perlu_navigasi=True.
    """
    print("🔗 Membuka URL income langsung di Chrome profil toko (tanpa keystroke)...")
    if launch_url_in_profile(shortcut, url):
        # Primary path: window opened by Chrome with URL, no identity verification needed
        return _wait_store_window(name, akun, verify_identity=False), False
    res = _attach_store_window(shortcut, name, akun)
    return res, res is not None


def verify_shopee_text(text: str) -> tuple[bool, str]:
    """Verifikasi teks hasil copy = format blok Dana Dilepaskan.

    Kriteria sama dengan extract_kode_dan_harga_dari_daftar_shopee di
    scan.py (header 'Total Penghasilan' + minimal 1 kode pesanan 26xxxx).
    Return (ok, alasan) — dipakai fail-fast supaya user tidak dapat
    clipboard berisi halaman yang salah.
    """
    if "Total Penghasilan" not in text:
        return False, "header 'Total Penghasilan' tidak ditemukan"
    if not _KODE_RE.search(text):
        return False, "tidak ada kode pesanan (26xxxx) di hasil copy"
    return True, f"{len(_KODE_RE.findall(text))} kode pesanan + harga ditemukan"


def _is_password_verification(text: str) -> bool:
    """Deteksi halaman 'minta verifikasi password' Shopee (anti-bot) dari
    teks hasil copy — berbasis frasa nyata yang tertangkap 2026-08-19
    (lihat _VERIF_PASSWORD_MARKERS), BUKAN keyword tebakan. Return False
    untuk semua teks lain (halaman income, format salah, beranda biasa)."""
    t = text.lower()
    return any(m in t for m in _VERIF_PASSWORD_MARKERS)


def _trim_to_income_table(text: str) -> str | None:
    """Potong hasil Ctrl+A/C jadi HANYA blok tabel Dana Dilepaskan.

    Hasil = header 5 kolom + blok 6 baris per pesanan (kode,
    'Pembeli:<nama>', tanggal, status, metode, 'Rp<harga>') — format
    SAMA PERSIS dengan yang dibaca scan.py (extract_kode_dan_harga_
    dari_daftar_shopee: baris setelah 'Total Penghasilan', blok 6 baris)
    dan check.py (kode 26xxxx + Rp pertama di blok per kode). Teks UI
    halaman (search box, tab, date-range, tombol Export, dst) dibuang.

    Return None kalau struktur tidak dikenali (header hilang / tidak ada
    blok valid) -> caller pakai teks asli (fallback aman, tidak pernah
    merusak hasil copy)."""
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    try:
        idx = lines.index("Total Penghasilan")
    except ValueError:
        return None
    header = [h for h in lines[max(0, idx - 4):idx + 1] if h in _TABLE_HEADER]
    if len(header) != 5:
        header = ["Total Penghasilan"]
    blok = list(header)
    i = idx + 1
    while i < len(lines):
        line = lines[i]
        if _KODE_RE.fullmatch(line) and i + 5 < len(lines):
            blok.extend(lines[i:i + 6])
            i += 6
        else:
            i += 1
    if len(blok) == len(header):
        return None
    return "\n".join(blok)


def _set_max_page_size(hwnd: int) -> None:
    """Ubah page size tabel income ke maksimum (50) sebelum Ctrl+A/C.

    Alasan (INVESTIGASI NYATA 2026-08-19, data asli): dropdown pagination
    default 10/page — rentang dengan >10 pesanan (minggu ini 24) cuma
    ter-copy halaman 1 (10 kode). Opsi max = 50 (10/20/50, tidak ada 100),
    TIDAK persist antar navigasi -> harus diklik ulang tiap fetch.

    Langkah (window-level, semua koordinat terverifikasi di Chrome toko
    maximized 1448x876 — lihat const di atas):
    1. PageDown x10 -> scroll ke bawah supaya pagination bar (di bawah
       fold setelah load) tampil. TANPA klik: klik area aman TIDAK ada —
       layout dateRange menaruh tabel lebih tinggi (baris mulai ~y 208),
       klik di posisi 'aman' malah kena baris = navigasi ke halaman detail
       (terbukti E2E 2026-08-19: hasil copy jadi 'Rincian Transaksi').
    2. Klik dropdown pagination (kanan-bawah tabel).
    3. Klik opsi "50" (menu terbuka ke ATAS dari button).

    Raise exception kalau gagal (pywin32 hilang, rect tidak valid, dll) —
    caller menangkapnya dan lanjut copy dengan tampilan default.
    Audit keamanan: klik/scroll di halaman income — BUKAN field
    password/OTP; tidak ada .fill/.type ke field sensitif."""
    import pyautogui
    win32gui, _, _ = _win32()
    if win32gui is None:
        raise RuntimeError("pywin32 tidak tersedia — tidak bisa baca posisi window")
    rect = win32gui.GetWindowRect(hwnd)
    if rect[2] <= rect[0] or rect[3] <= rect[1]:
        raise RuntimeError(f"rect window tidak valid: {rect}")

    # 1) scroll ke bawah (pagination di bawah fold setelah halaman load)
    for _ in range(10):
        pyautogui.press("pagedown")
        time.sleep(0.25)

    # 2) buka dropdown pagination
    dd_x = rect[0] + DD_X_OFFSET
    dd_y = rect[3] - DD_Y_FROM_BOTTOM
    pyautogui.click(dd_x, dd_y)
    time.sleep(DD_OPEN_WAIT)

    # 3) pilih opsi terbesar (menu buka ke atas)
    pyautogui.click(dd_x + OPTION_DX, dd_y + OPTION_DY)


def fetch_shopee(store: dict) -> int:
    """Alur utama. Return exit code (0 sukses, 1 gagal)."""
    name = store["name"]
    shortcut = str(store.get("shortcut") or "").strip()

    print(f"🚀 Auto-Fetch Shopee — toko: {name}")
    if not shortcut:
        print("❌ config.yaml: stores[].shortcut (path .lnk toko) belum diisi untuk toko ini.")
        return 1
    print(f"ℹ Shortcut: {shortcut}")

    akun = str(store.get("akun") or "").strip().lower()
    state = _active_store_state()
    url = _income_url(state.get("start_date", ""), state.get("end_date", ""))
    if state.get("start_date") and state.get("end_date"):
        print(f"ℹ Rentang tanggal: {state['start_date']} s/d {state['end_date']} (dateRange di URL income)")
    else:
        print("ℹ Tanpa date range (rentang default akun)")

    res, perlu_navigasi = _open_store_url(shortcut, name, akun, url)
    if res is None:
        return 1
    hwnd, title = res

    try:
        import pyautogui
        import pyperclip
    except ImportError:
        print("❌ pyautogui/pyperclip belum terinstall — jalankan: pip install pyautogui pyperclip")
        return 1

    if perlu_navigasi:
        if not ensure_foreground(hwnd):
            print("⚠ Gagal mengaktifkan window Chrome toko (Windows foreground-lock).")
            print("   Klik window Chrome toko manual, lalu klik Fetch lagi.")
            return 1
        print("ℹ Fallback: tab baru (Ctrl+T) → Ctrl+L → paste URL income...")
        pyautogui.hotkey("ctrl", "t")
        time.sleep(0.3)
        pyautogui.hotkey("ctrl", "l")
        time.sleep(0.3)
        pyperclip.copy(url)
        pyautogui.hotkey("ctrl", "v")
        pyautogui.press("enter")
        time.sleep(PAGE_LOAD_WAIT)
    else:
        print(f"⏳ Menunggu halaman income render ({PAGE_LOAD_WAIT} detik)...")
        time.sleep(PAGE_LOAD_WAIT)

    try:
        print(f"ℹ Mengatur page size tabel ke maksimum ({PAGE_SIZE_MAX}/page) supaya semua pesanan ikut ter-copy...")
        _set_max_page_size(hwnd)
        time.sleep(PAGE_SIZE_SETTLE)
    except Exception as exc:
        print(f"⚠ Tidak bisa ubah page size ({type(exc).__name__}: {exc}) — lanjut dengan tampilan default.")

    text = ""
    for attempt in range(COPY_RETRIES):
        print(f"📋 Menyalin halaman (Ctrl+A/C — percobaan {attempt + 1}/{COPY_RETRIES})...")
        pyautogui.hotkey("ctrl", "a")
        pyautogui.hotkey("ctrl", "c")
        time.sleep(COPY_SETTLE)
        text = pyperclip.paste()
        ok, _ = verify_shopee_text(text)
        if ok or _is_password_verification(text) or attempt == COPY_RETRIES - 1:
            break
        print(f"⏳ Halaman belum siap (rendering/login) — coba lagi dalam {COPY_RETRY_WAIT} detik...")
        time.sleep(COPY_RETRY_WAIT)

    ok, alasan = verify_shopee_text(text)
    if ok:
        trimmed = _trim_to_income_table(text)
        if trimmed is not None:
            tok, talasan = verify_shopee_text(trimmed)
            if tok:
                text = trimmed
                pyperclip.copy(text)
                print("✂ Clipboard dipotong: HANYA blok tabel pesanan (kode, tanggal, status,")
                print("   metode, total) — teks UI halaman (search box, tab, export, dst) dibuang.")
            else:
                print(f"⚠ Pemotongan tabel gagal verifikasi ({talasan}) — clipboard tetap hasil Ctrl+A/C mentah.")
        else:
            print("⚠ Struktur tabel Dana Dilepaskan tidak dikenali — clipboard tetap hasil Ctrl+A/C mentah.")
        print(f"✔ {alasan}")
        print("✅ Data berhasil disalin ke clipboard — klik Start Scan untuk lanjut")
        print("   (window Chrome dibiarkan terbuka; sesi login TIDAK diganggu — fetch berikutnya dipakai langsung)")
        return 0

    if _is_password_verification(text):
        print(f"⚠ Tolong isi verifikasi password di Chrome {name}...")
        print("   (Shopee meminta verifikasi password untuk melanjutkan — bot TIDAK menyentuh password/OTP.)")
        time.sleep(3)
        if not activate_window(hwnd):
            print("   ⚠ Gagal mengaktifkan window Chrome toko (Windows foreground-lock) — klik manual kalau perlu.")
        print("   Setelah verifikasi selesai di Chrome toko, klik Fetch lagi.")
        return 1

    print(f"❌ Hasil copy TIDAK format Dana Dilepaskan: {alasan}.")
    print("   Kemungkinan: halaman minta login (bot TIDAK menyentuh password/OTP) atau")
    print("   halaman belum selesai load. Login manual di window Chrome toko, pastikan")
    print("   halaman income (Dana Dilepaskan) terbuka, lalu klik Fetch lagi.")
    return 1


def main() -> None:
    Config.ensure_loaded()
    store = resolve_store()
    sys.exit(fetch_shopee(store))


if __name__ == "__main__":
    main()
