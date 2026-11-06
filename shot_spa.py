"""Skrip untuk mengambil screenshot SPA pywebview per halaman secara otomatis.
Dijalankan dalam mode dry-run (BOPEL_PYWEBVIEW_DRY_RUN=1).
"""

from __future__ import annotations

import os
import time
import threading
from pathlib import Path

# WAJIB mode simulasi
os.environ["BOPEL_PYWEBVIEW_DRY_RUN"] = "1"

# Set DPI awareness
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

OUT_DIR = Path("C:/robot/bopel/screenshots_spa/v2")
OUT_DIR.mkdir(parents=True, exist_ok=True)

pages = [
    ("02_dashboard", "dashboard"),
    ("03_logs", "logs"),
    ("04_settings", "settings"),
]

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
    time.sleep(1.2)  # tunggu animasi / render halaman
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
    # Tunggu sebentar agar pywebviewready / DOM load selesai
    time.sleep(2.0)
    
    # 1. Dashboard, Logs, Settings
    for filename, nav_name in pages:
        print(f"Navigasi ke {nav_name}...")
        script = f"""
        (function() {{
            const btn = document.querySelector('.sb-item[data-nav="{nav_name}"]');
            if (btn) {{ btn.click(); return true; }}
            return false;
        }})();
        """
        try:
            window.evaluate_js(script)
        except Exception as e:
            print(f"Evaluasi JS gagal untuk {nav_name}: {e}")
        capture_window_rect(filename)

    # 2. Tools (Checklist Automation / check.py, dll.)
    # Ambil tools dari sidebar button dengan data-nav="tool"
    print("Navigasi ke tools...")
    script_tools = """
    Array.from(document.querySelectorAll('.sb-item[data-nav="tool"]')).map(el => ({
        script: el.getAttribute('data-script'),
        text: el.textContent.trim()
    }))
    """
    try:
        tools_info = window.evaluate_js(script_tools)
        print(f"Ditemukan tools: {tools_info}")
    except Exception as e:
        print(f"Gagal ambil tools: {e}")
        tools_info = []

    # Map tools to expected output filenames
    # 03_checklist_manual, 04_checklist_otomatis, 05_screenshot_iklan, 06_inventory_scan_kode_pesanan, 07_inventory_scan_detail
    tool_map = {
        "check.py": "04_checklist_otomatis",
        "screenshot_iklan.py": "05_screenshot_iklan",
        "scan.py": "06_inventory_scan_kode_pesanan",
    }

    for t in tools_info:
        script = t["script"]
        print(f"Klik tool script: {script}")
        click_script = f"""
        (function() {{
            const btn = document.querySelector('.sb-item[data-nav="tool"][data-script="{script}"]');
            if (btn) {{ btn.click(); return true; }}
            return false;
        }})();
        """
        window.evaluate_js(click_script)
        time.sleep(1.0)
        
        # Tentukan nama file screenshot
        fname = tool_map.get(script, f"tool_{script.replace('.py', '')}")
        capture_window_rect(fname)

        # Jika tool adalah check.py (checklist otomatis), jalankan simulasi run
        if script == "check.py":
            print("Simulasi Start Checklist Otomatis...")
            window.evaluate_js('document.getElementById("btn-start-checklist-otomatis")?.click();')
            time.sleep(1.0)
            capture_window_rect("10_checklist_otomatis_running")
            print("Menunggu simulasi selesai...")
            time.sleep(3.5)
            capture_window_rect("11_checklist_otomatis_selesai")

        # Jika tool adalah screenshot_iklan.py, jalankan simulasi run
        if script == "screenshot_iklan.py":
            print("Simulasi Start Screenshot Iklan...")
            window.evaluate_js('document.getElementById("btn-start-screenshot-iklan")?.click();')
            time.sleep(4.0)
            capture_window_rect("12_screenshot_iklan_selesai")

    print("Semua screenshot SPA selesai diambil!")
    time.sleep(1.0)
    window.destroy()

def main():
    api = Api(ToolLauncher())
    from app import _WEB_INDEX
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

    threading.Thread(target=automation_sequence, args=(window,), daemon=True).start()
    webview.start()

if __name__ == "__main__":
    main()
