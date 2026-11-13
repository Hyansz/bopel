import time
import os
import pyautogui
import win32gui
from core.config import Config
from core.window import activate_window, find_target_window

def bring_terminal_to_front():
    """Cari window terminal / python / powershell dan bawa ke depan."""
    def cb(hwnd, _):
        if not win32gui.IsWindowVisible(hwnd):
            return
        title = win32gui.GetWindowText(hwnd).lower()
        if any(k in title for k in ["python", "powershell", "cmd.exe", "command prompt", "bopel"]):
            if "inventory bsm" not in title:
                try:
                    activate_window(hwnd)
                except Exception:
                    pass
    win32gui.EnumWindows(cb, None)

def track():
    print("=== Track Koordinat BSM (Transfer Input) ===")

    # 1. Buka shortcut Inventory BSM
    Config.ensure_loaded()
    shortcut_path = r"C:\Users\PC\Desktop\Inventory BSM.lnk"
    print(f"Membuka: {shortcut_path}")
    os.startfile(shortcut_path)

    # 2. Tunggu window muncul
    print("Menunggu window 'Inventory BSM' muncul...")
    hwnd = None
    deadline = time.monotonic() + 30.0
    while time.monotonic() < deadline:
        res = find_target_window("Inventory BSM")
        if res:
            hwnd = res[0]
            break
        time.sleep(0.5)

    if not hwnd:
        print("❌ Window 'Inventory BSM' tidak ditemukan setelah 30 detik!")
        return

    print("Mengaktifkan window Inventory BSM...")
    activate_window(hwnd)
    time.sleep(1.0)

    # 3. Navigasi: ALT + 4, lalu F2
    print("Menekan ALT + 4...")
    pyautogui.hotkey('alt', '4')
    time.sleep(0.8)

    print("Menekan F2...")
    pyautogui.press('f2')
    time.sleep(1.0)

    # 4. Tunggu 8 detik bagi user untuk mengarahkan mouse
    print("\n[PERHATIAN] Arahkan kursor mouse ke posisi yang diinginkan!")
    for i in range(8, 0, -1):
        print(f"Merekam posisi dalam {i} detik...")
        time.sleep(1)

    x, y = pyautogui.position()
    rect = win32gui.GetWindowRect(hwnd)
    w = rect[2] - rect[0]
    h = rect[3] - rect[1]

    rel_x = (x - rect[0]) / w
    rel_y = (y - rect[1]) / h

    # 5. Tutup window Inventory BSM
    print("\nMenutup window 'Inventory BSM'...")
    bring_terminal_to_front()
    time.sleep(0.5)
    try:
        win32gui.PostMessage(hwnd, 0x0010, 0, 0) # WM_CLOSE
    except Exception as e:
        print(f"Gagal menutup otomatis: {e}")

    print("\n" + "=" * 40)
    print("HASIL TRACKING KORDINAT:")
    print(f"  Posisi Layar (Absolute) : {x}, {y}")
    print(f"  Window Rect (L, T, R, B): {rect}")
    print(f"  Ukuran Window           : {w}x{h}")
    print(f"  Koordinat Relatif [x, y]: [{rel_x:.4f}, {rel_y:.4f}]")
    print("=" * 40)

if __name__ == "__main__":
    track()
