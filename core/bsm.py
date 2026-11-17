"""Helper untuk interaksi dengan aplikasi Inventory BSM.
"""
import os
import time
import subprocess
import sys
import pyautogui
import ctypes
from core.window import find_target_window, activate_window, ensure_foreground

def is_bsm_running():
    # Menggunakan window title "Inventory BSM"
    return find_target_window("Inventory BSM")

# Konstanta dari instruksi
BSM_WAIT_AFTER_F5 = 5.0
BSM_REFRESH_F5 = True

def get_search_click_coords():
    """Hitung koordinat klik search box berdasarkan window rect "Inventory BSM"
    dan rasio dari config.yaml [0.4512, 0.2089].
    """
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass

    import win32gui
    ketemu = is_bsm_running()
    if not ketemu:
        return None

    hwnd, _ = ketemu
    rect = win32gui.GetWindowRect(hwnd)
    L, T, R, B = rect

    # Rasio dari instruksi
    rx, ry = 0.4512, 0.2089

    # Cek config jika ada override
    from core.config import Config
    Config.ensure_loaded()
    for t in Config.tools():
        if t.get("script") == "scan.py":
            coords = t.get("bsm_search_click")
            if isinstance(coords, list) and len(coords) == 2:
                try:
                    rx, ry = float(coords[0]), float(coords[1])
                except (TypeError, ValueError):
                    pass

    x = int(L + rx * (R - L))
    y = int(T + ry * (B - T))
    print(f"[BSM] Window rect: L={L}, T={T}, R={R}, B={B} | Klik search di: ({x}, {y})")
    return x, y


def launch_bsm():
    lnk_path = r"C:\Users\PC\Desktop\Inventory BSM.lnk"
    if not os.path.exists(lnk_path):
        raise FileNotFoundError(f"Shortcut tidak ditemukan: {lnk_path}")

    os.startfile(lnk_path)

    # Polling tunggu window muncul
    for _ in range(60): # maks 30 dtk (0.5 dtk * 60)
        if is_bsm_running():
            time.sleep(5) # tunggu 5 detik tambahan setelah window muncul
            return True
        time.sleep(0.5)

    return False

def activate_and_refresh_bsm():
    # 1. Cari atau jalankan
    ketemu = is_bsm_running()
    if not ketemu:
        print("Aplikasi tidak ditemukan, mencoba meluncurkan...")
        if not launch_bsm():
            print("Gagal meluncurkan aplikasi.")
            return False
        ketemu = is_bsm_running()

    hwnd, title = ketemu

    # 2. Pastikan foreground
    if not ensure_foreground(hwnd):
        print("Gagal mengaktifkan window Inventory BSM.")
        return False

    # 3. Refresh (F5)
    if BSM_REFRESH_F5:
        print("Melakukan refresh (F5)...")
        pyautogui.press('f5')
        time.sleep(BSM_WAIT_AFTER_F5)

    return True
