"""Emergency stop hotkey untuk menghentikan semua tool yang berjalan.
Mendaftarkan hotkey global tombol Q yang akan memanggil stop_tool()
dari launcher, sama seperti tombol Stop di UI Bopel.
"""
from __future__ import annotations

import ctypes
import threading
import time
from ctypes import wintypes
from core.config import Config

user32 = ctypes.windll.user32
user32.RegisterHotKey.argtypes = [wintypes.HWND, wintypes.INT, wintypes.UINT, wintypes.UINT]
user32.RegisterHotKey.restype = wintypes.BOOL
user32.UnregisterHotKey.argtypes = [wintypes.HWND, wintypes.INT]
user32.UnregisterHotKey.restype = wintypes.BOOL
user32.GetMessageW.argtypes = [ctypes.POINTER(wintypes.MSG), wintypes.HWND, wintypes.UINT, wintypes.UINT]
user32.GetMessageW.restype = wintypes.BOOL

MOD_NOREPEAT = 0x4000
WM_HOTKEY = 0x0312
VK_Q = ord('Q') # Tombol Q tunggal

_HOTKEY_ID = 100
_REGISTERED = False
_launcher = None  # referensi ke ToolLauncher

def _stop_all_tools():
    """Panggil stop_tool untuk semua tool yang sedang running di launcher."""
    global _launcher
    if _launcher is None:
        print("[EMERGENCY STOP] Launcher belum diinisialisasi.")
        return

    # Hentikan semua tool yang sedang berjalan
    for script_name in list(_launcher.active_tools.keys()):
        if _launcher.active_tools[script_name].running:
            print(f"[EMERGENCY STOP] Menghentikan tool: {script_name}")
            _launcher.stop(script_name)

def _hotkey_loop():
    global _REGISTERED
    # Mendaftarkan tombol Q (tanpa modifier) sebagai emergency stop
    if user32.RegisterHotKey(None, _HOTKEY_ID, MOD_NOREPEAT, VK_Q):
        _REGISTERED = True
        print("[EMERGENCY STOP] Tombol Q terdaftar.")
    else:
        err = ctypes.GetLastError()
        print(f"[EMERGENCY STOP] Gagal daftar tombol Q (error {err})")
        return

    msg = wintypes.MSG()
    while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) != 0:
        if msg.message == WM_HOTKEY and msg.wParam == _HOTKEY_ID:
            print("[EMERGENCY STOP] Q ditekan! Menghentikan semua tool...")
            _stop_all_tools()

    user32.UnregisterHotKey(None, _HOTKEY_ID)

def init_emergency_stop(launcher=None):
    """Mendaftarkan emergency stop hotkey di thread terpisah.

    Args:
        launcher: Instansi ToolLauncher (wajib agar stop bisa dipanggil).
    """
    global _REGISTERED, _launcher
    if _REGISTERED:
        return
    _launcher = launcher
    t = threading.Thread(target=_hotkey_loop, daemon=True)
    t.start()

if __name__ == '__main__':
    # Standalone test (tanpa launcher, hanya test hotkey terdaftar)
    init_emergency_stop()
    while True:
        time.sleep(1)
