"""Skrip untuk mengambil screenshot SPA pywebview per halaman secara otomatis (v2.0.0).
Dijalankan dalam mode dry-run (BOPEL_PYWEBVIEW_DRY_RUN=1) ke screenshots_spa/v3/.
"""

from __future__ import annotations

import os
import time
import threading
from pathlib import Path

os.environ["BOPEL_PYWEBVIEW_DRY_RUN"] = "1"

try:
    import ctypes
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass

import webview
from PIL import Image, ImageGrab

from app import Api
from core.launcher_cb import ToolLauncher
from core.window import find_target_window, activate_window

OUT_DIR = Path("C:/robot/bopel/screenshots_spa/v3")
OUT_DIR.mkdir(parents=True, exist_ok=True)

def count_unique_colors(img_path: Path) -> int:
    try:
        im = Image.open(img_path)
        colors = im.getcolors(maxcolors=100000)
        if colors is None:
            return 100000
        return len(colors)
    except Exception:
        return 0

def capture_window_rect(filename: str) -> bool:
    time.sleep(1.2)
    hwnds = find_target_window("Bopel Automation Toolkit")
    if not hwnds:
        print(f"Window tidak ditemukan untuk {filename}")
        return False
    hwnd = hwnds[0]
    activate_window(hwnd)
    time.sleep(0.3)
    
    try:
        import win32gui
        rect = win32gui.GetWindowRect(hwnd)
        box = (rect[0], rect[1], rect[2], rect[3])
        img = ImageGrab.grab(bbox=box)
        out_path = OUT_DIR / f"{filename}.png"
        img.save(out_path)
        uc = count_unique_colors(out_path)
        size_kb = out_path.stat().st_size // 1024
        print(f"[saved] {filename}.png ({size_kb} KB, {uc} unique colors)")
        return True
    except Exception as exc:
        print(f"Gagal capture {filename}: {exc}")
        return False

def automation_sequence(window):
    time.sleep(2.0)
    
    # 1. dashboard
    print("Navigasi ke dashboard...")
    window.evaluate_js("document.querySelector('.sb-item[data-nav=\"dashboard\"]')?.click();")
    capture_window_rect("dashboard")

    # 2. logs
    print("Navigasi ke logs...")
    window.evaluate_js("document.querySelector('.sb-item[data-nav=\"logs\"]')?.click();")
    capture_window_rect("logs")

    # 3. settings
    print("Navigasi ke settings...")
    window.evaluate_js("document.querySelector('.sb-item[data-nav=\"settings\"]')?.click();")
    capture_window_rect("settings")

    # 4. checklist-manual-idle & checklist-otomatis-idle & running & selesai & gagal
    print("Navigasi ke Checklist Automation...")
    window.evaluate_js("document.querySelector('.sb-item[data-nav=\"tool\"][data-script=\"check.py\"]')?.click();")
    time.sleep(0.5)
    capture_window_rect("checklist-manual-idle")

    print("Pilih mode otomatis di Checklist...")
    window.evaluate_js("""
    (function(){
        const btns = document.querySelectorAll('#data-mode-btns .btn.choice');
        for (const b of btns) { if (b.textContent.trim() === 'Otomatis') { b.click(); break; } }
    })();
    """)
    time.sleep(0.5)
    capture_window_rect("checklist-otomatis-idle")

    print("Mulai Checklist Automation (berjalan)...")
    window.evaluate_js("document.getElementById('start-btn')?.click();")
    time.sleep(0.6)
    capture_window_rect("checklist-berjalan-awal")
    time.sleep(1.2)
    capture_window_rect("checklist-berjalan-tengah")

    print("Menunggu checklist selesai...")
    time.sleep(2.5)
    capture_window_rect("checklist-selesai")

    print("Simulasi Checklist Gagal...")
    window.evaluate_js("""
    (function(){
        const key = 'check.py';
        if (typeof onToolFinished === 'function') {
            onToolFinished(key, false, 'Gagal koneksi shopee', 'Gagal validasi');
        }
    })();
    """)
    time.sleep(0.5)
    capture_window_rect("checklist-gagal")

    # 5. Screenshot Iklan
    print("Navigasi ke Screenshot Iklan...")
    window.evaluate_js("document.querySelector('.sb-item[data-nav=\"tool\"][data-script=\"screenshot_iklan.py\"]')?.click();")
    time.sleep(0.5)
    capture_window_rect("screenshot-iklan-idle")

    print("Mulai Screenshot Iklan (berjalan)...")
    window.evaluate_js("document.getElementById('start-btn')?.click();")
    time.sleep(1.2)
    capture_window_rect("screenshot-iklan-berjalan")

    print("Menunggu Screenshot Iklan selesai...")
    window.evaluate_js("""
    (function(){
        const key = 'screenshot_iklan.py';
        if (typeof onToolFinished === 'function') {
            onToolFinished(key, true, '', 'Berhasil screenshot 3 toko');
            if (typeof showScreenshotPreviews === 'function') {
                showScreenshotPreviews(key, [
                    { path: 'logs/screenshots/iklan/Toko_1_Toko_Alkes_Solo.png', uri: 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==' },
                    { path: 'logs/screenshots/iklan/Toko_2_Toko_Alkes_BSM.png', uri: 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==' }
                ]);
            }
        }
    })();
    """)
    time.sleep(1.0)
    capture_window_rect("screenshot-iklan-selesai")

    # 6. Inventory Scanner
    print("Navigasi ke Inventory Scanner...")
    window.evaluate_js("document.querySelector('.sb-item[data-nav=\"tool\"][data-script=\"scan.py\"]')?.click();")
    time.sleep(0.5)
    capture_window_rect("inventory-idle")

    print("Mulai Inventory Scanner (berjalan)...")
    window.evaluate_js("""
    (function(){
        const btns = document.querySelectorAll('#mode-btns .btn.choice');
        if (btns.length) btns[0].click();
    })();
    """)
    time.sleep(1.2)
    capture_window_rect("inventory-berjalan")

    print("Menunggu Inventory Scanner selesai...")
    window.evaluate_js("""
    (function(){
        const key = 'scan.py::Scan Kode Pesanan';
        if (typeof onToolFinished === 'function') {
            onToolFinished(key, true, '', 'Scan selesai');
            if (typeof updateSummaryCards === 'function') {
                updateSummaryCards(key, { total: 10, ok: 10, beda: 0, notfound: 0, durasi: '1.2' });
            }
        }
    })();
    """)
    time.sleep(1.0)
    capture_window_rect("inventory-selesai")

    print("Semua screenshot SPA v3 selesai diambil!")
    time.sleep(1.0)
    window.destroy()

def main():
    api = Api(ToolLauncher())
    from app import _WEB_INDEX
    window = webview.create_window(
        "Bopel Automation Toolkit",
        str(_WEB_INDEX),
        js_api=api,
        width=1220,
        height=780,
        min_size=(900, 600),
        resizable=True,
    )
    api.bind_window(window)

    threading.Thread(target=automation_sequence, args=(window,), daemon=True).start()
    webview.start()

if __name__ == "__main__":
    main()
