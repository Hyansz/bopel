"""Window activation helpers for Windows — menggantikan alt-tab manual.

Tools automation (check.py / scan.py) butuh window aplikasi warehouse
menjadi foreground sebelum pyautogui mulai interaksi. Sebelumnya user
harus alt-tab manual; sekarang launcher jalanin tool dengan env
BOPEL_UI_MODE=1, lalu tool panggil find_target_window() + activate_window()
di awal (lihat `persiapkan_window_target()`).

win32gui/win32con/win32api di-import LAZY di dalam fungsi (bukan di top
module) biar modul ini tetap bisa di-import & di-unit-test di environment
tanpa pywin32 (fungsi yang butuh win32 tinggal raise RuntimeError dengan
pesan jelas pas dipanggil, bukan gagal pas import).
"""

from __future__ import annotations

import os
import shlex
import subprocess
import sys
import time
import re

from core.config import Config


def _win32():
    """Return (win32gui, win32con, win32api) — None kalau pywin32 gak ada."""
    try:
        import win32api
        import win32con
        import win32gui
        return win32gui, win32con, win32api
    except ImportError:
        return None, None, None


def is_windows() -> bool:
    return sys.platform.startswith("win")


def target_window_title(script_name: str) -> str:
    """Ambil keyword judul window target dari config.yaml
    (tools[].target_window_title). Kosong = tool gak butuh aktivasi otomatis."""
    Config.ensure_loaded()
    for t in Config.tools():
        if t.get("script") == script_name:
            return str(t.get("target_window_title") or "").strip()
    return ""


def find_target_window(title_keyword: str, enum_windows=None):
    """Cari window yang judulnya MENGANDUNG title_keyword (case-insensitive).

    Hanya window yang terlihat (IsWindowVisible) yang dipertimbangkan.
    Return (hwnd, title) window pertama yang cocok, atau None kalau
    tidak ketemu / keyword kosong.

    `enum_windows` cuma dipakai buat unit test (inject fake enumerator);
    kalau None, pakai win32gui.EnumWindows asli.
    """
    if not title_keyword:
        return None

    win32gui, _, _ = _win32()
    if win32gui is None:
        raise RuntimeError(
            "pywin32 tidak terinstall — jalankan 'pip install pywin32' "
            "(lihat requirements.txt). Aktivasi window otomatis tidak bisa jalan."
        )

    keyword = title_keyword.lower()
    hasil: list = []

    def cb(hwnd, _):
        if not win32gui.IsWindowVisible(hwnd):
            return
        title = win32gui.GetWindowText(hwnd)
        if title and keyword in title.lower():
            hasil.append((hwnd, title))

    (enum_windows or win32gui.EnumWindows)(cb, None)
    return hasil[0] if hasil else None


def activate_window(hwnd) -> bool:

    """Urutan percobaan:
    1. SW_RESTORE kalau window lagi minimize.
    2. SetForegroundWindow langsung.
    3. Kalau gagal (Windows foreground-lock): toggle TOPMOST (trick umum
       biar window ke-paksa ke foreground), lalu SetForegroundWindow lagi.
    """
    win32gui, win32con, _ = _win32()
    if win32gui is None or hwnd is None:
        return False

    try:
        if win32gui.IsIconic(hwnd):
            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)

        try:
            win32gui.SetForegroundWindow(hwnd)
            return True
        except Exception:
            pass

        # Fallback: TOPMOST toggle buat lawan foreground lock Windows 10+.
        try:
            win32gui.SetWindowPos(
                hwnd, win32con.HWND_TOPMOST, 0, 0, 0, 0,
                win32con.SWP_NOMOVE | win32con.SWP_NOSIZE,
            )
            win32gui.SetWindowPos(
                hwnd, win32con.HWND_NOTOPMOST, 0, 0, 0, 0,
                win32con.SWP_NOMOVE | win32con.SWP_NOSIZE,
            )
            win32gui.SetForegroundWindow(hwnd)
            return True
        except Exception:
            return False
    except Exception:
        return False


def ensure_foreground(hwnd, timeout: float = 3.0, interval: float = 0.15,
                     win32gui=None, activate=None, sleep=time.sleep,
                     clock=time.monotonic) -> bool:
    """Aktifkan hwnd dan PASTIKAN GetForegroundWindow() == hwnd.

    `activate_window()` mengembalikan True walau SetForegroundWindow
    sebenarnya ditolak Windows foreground-lock (return value API tidak
    dicek). Kalau keystroke dikirim tanpa cek ini, Ctrl+L bisa jatuh ke
    window lain — akar bug "Ctrl+L memilih saran/elemen lain" 2026-11-03.

    Poll sampai timeout; return False kalau fokus tidak pernah pindah
    (caller wajib batal, jangan kirim keystroke ke window yang salah).
    Parameter win32gui/activate/sleep/clock bisa di-inject untuk test.
    """
    if hwnd is None:
        return False
    if win32gui is None:
        win32gui, _, _ = _win32()
    if win32gui is None:
        return False
    act = activate or activate_window
    batas = clock() + timeout
    while clock() < batas:
        try:
            if win32gui.GetForegroundWindow() == hwnd:
                return True
        except Exception:
            pass
        try:
            act(hwnd)
        except Exception:
            pass
        sleep(interval)
    try:
        return win32gui.GetForegroundWindow() == hwnd
    except Exception:
        return False


def chrome_windows(win32gui=None) -> list[tuple[int, str]]:
    """SEMUA window Chrome visible: [(hwnd, title), ...] — termasuk yang
    bukan foreground. Fallback deterministik saat Chrome gagal menaikkan
    window profil toko (Windows foreground-lock)."""
    if win32gui is None:
        win32gui, _, _ = _win32()
    if win32gui is None:
        return []
    hasil: list[tuple[int, str]] = []

    def cb(hwnd, _):
        if not win32gui.IsWindowVisible(hwnd):
            return
        title = win32gui.GetWindowText(hwnd) or ""
        t = title.lower()
        if "google chrome" in t and not any(p in t for p in (
                "google sheets", "google docs", "google slides", "google drive",
                "google gmail", "google youtube")):
            hasil.append((hwnd, title))

    win32gui.EnumWindows(cb, None)
    return hasil


def split_windows_args(raw: str) -> list[str]:
    """Pecah string Arguments .lnk ala Windows: kutip boleh di tengah token
    atau spasi di dalam kutip.
    '--profile-directory="Profile 7"' -> '--profile-directory=Profile 7'
    """
    raw = str(raw or "").strip()
    if not raw:
        return []
    # Use shlex to split respecting quotes, but it may split a flag=value where value has spaces.
    try:
        parts = shlex.split(raw, posix=False)
    except Exception:
        parts = re.findall(r'[^\s"]+|"[^"]*"', raw)
    merged: list[str] = []
    i = 0
    while i < len(parts):
        part = parts[i]
        # If part contains '=' and does not end with a quote, likely split value with spaces.
        if "=" in part and not (part.endswith('"') or part.endswith("'")):
            # Look ahead for next part that is not a flag (doesn't start with '--').
            if i + 1 < len(parts) and not parts[i + 1].startswith("--"):
                part = part + " " + parts[i + 1]
                i += 1
        merged.append(part.replace('"', '').replace("'", ""))
        i += 1
    return merged


def read_lnk(shortcut, shell=None) -> tuple[str, list[str]]:
    """Baca Target + Arguments dari shortcut Windows (.lnk).

    Return (target, args). Raise RuntimeError dengan pesan jelas kalau
    file tidak ada / win32com tidak tersedia — caller memutuskan fallback.
    `shell` bisa di-inject (objek dengan CreateShortcut) untuk test.
    """
    path = str(shortcut or "").strip()
    if shell is None and (not path or not os.path.exists(path)):
        raise RuntimeError(f"shortcut tidak ditemukan: {path or '(kosong)'}")
    if shell is None:
        try:
            import win32com.client
        except ImportError as exc:
            raise RuntimeError(
                "pywin32 (win32com) tidak terinstall — jalankan 'pip install pywin32'"
            ) from exc
        shell = win32com.client.Dispatch("WScript.Shell")
    sc = shell.CreateShortcut(path) if path else shell.CreateShortcut("dummy")
    target = str(getattr(sc, "TargetPath", "") or "").strip()
    args = split_windows_args(str(getattr(sc, "Arguments", "") or ""))
    if not target:
        raise RuntimeError(f"Target kosong di shortcut: {path}")
    return target, args


def build_chrome_command(target: str, args: list[str], url: str,
                         exists=os.path.exists) -> list[str]:
    """Command line Chrome untuk membuka `url` di profil toko — TANPA keystroke.

    - URL lama di argumen .lnk DIBUANG (kalau tidak, Chrome membuka 2 tab:
      URL default .lnk + URL target). `--app=` juga dibuang supaya tab
      normal (bukan app window) yang dipakai untuk screenshot.
    - chrome_proxy.exe → chrome.exe sibling kalau ada (chrome_proxy hanya
      shim; chrome.exe menerima flag + URL yang sama).
    """
    exe = str(target or "").strip()
    if os.path.basename(exe).lower() == "chrome_proxy.exe":
        kandidat = os.path.join(os.path.dirname(exe), "chrome.exe")
        if exists(kandidat):
            exe = kandidat
    keep = []
    for a in args:
        low = str(a).lower()
        if low.startswith(("http://", "https://", "--app=")):
            continue
        keep.append(a)
    return [exe, *keep, url]


def launch_url_in_profile(shortcut, url: str, popen=None, shell=None,
                          exists=os.path.exists) -> bool:
    """Buka `url` LANGSUNG lewat Chrome profil toko dari file .lnk.

    Ini jalur UTAMA (deterministik): tidak ada Ctrl+L/paste/Enter, jadi
    tampilan default Chrome (NTP, restore tab, halaman terakhir) tidak
    bisa mempengaruhi alur. Chrome yang sudah jalan untuk profil itu
    membuka URL di tab/window-nya sendiri.

    Return True kalau proses berhasil dijalankan; False = caller pakai
    fallback keystroke minimal.
    """
    try:
        # Jika shortcut berupa string path dan file tidak ada, tapi shell di-inject,
        # kita lewati os.path.exists check untuk keperluan unit test mock shell.
        if shell is None and not os.path.exists(str(shortcut)):
            raise RuntimeError(f"shortcut tidak ditemukan: {shortcut}")
        target, args = read_lnk(shortcut, shell=shell)
        cmd = build_chrome_command(target, args, url, exists=exists)
        (popen or subprocess.Popen)(cmd)
        return True
    except Exception as exc:
        print(f"[WARN] Gagal membuka URL langsung via shortcut ({exc}) — fallback ke keystroke.")
        return False


def persiapkan_window_target(script_name: str, required: bool = False):
    """Satu paket untuk tool: cari + aktivasi window target dari config.

    - config kosong  -> print warning, return None (perilaku lama, tanpa
      aktivasi otomatis).
    - window ketemu  -> aktivasi, print status, return hwnd.
    - window TIDAK ketemu:
        * required=True  -> print pesan error JELAS lalu sys.exit(1)
          (bukan crash; launcher menampilkannya sebagai tool gagal di UI).
        * required=False -> print warning, return None (lanjut tanpa
          aktivasi — user alt-tab manual seperti dulu).
    """
    title = target_window_title(script_name)
    if not title:
        print(f"[WARN] config.yaml: 'target_window_title' kosong untuk {script_name} "
              "-> aktivasi window otomatis di-skip (alt-tab manual seperti lama).")
        return None

    if not is_windows():
        print(f"[WARN] Bukan Windows -> aktivasi window otomatis di-skip untuk {script_name}.")
        return None

    print(f"🔎 Mencari window aplikasi warehouse '{title}'...")
    ketemu = find_target_window(title)
    if ketemu is None:
        pesan = (
            f"❌ Aplikasi warehouse '{title}' TIDAK DITEMUKAN.\n"
            "   Buka dulu aplikasinya (klik iconnya), lalu klik Start lagi."
        )
        print(pesan)
        if required:
            sys.exit(1)
        return None

    hwnd, nama_window = ketemu
    if activate_window(hwnd):
        print(f"[OK] Window '{nama_window}' diaktifkan otomatis — fokus pindah ke aplikasi warehouse.")
    else:
        print(f"[WARN] Window '{nama_window}' ketemu tapi GAGAL di-aktifkan otomatis (Windows foreground-lock). Klik manually window-nya kalau perlu.")
    return hwnd
