"""Screenshot Iklan — screenshot bagian iklan produk di dashboard iklan Shopee Seller Center.

Dipanggil BOPEL sebagai tool subprocess (stdout di-stream ke UI oleh
core/launcher.py). Alur:

1. Baca config.yaml stores: + rentang tanggal (logs/.active_store.json).
2. Konversi tanggal pilihan user (YYYY-MM-DD) jadi unix timestamp GMT+7
   (from = awal hari 00:00:00, to = akhir hari 23:59:59).
3. Bentuk URL marketing/pas/index + parameter from/to.
4. Buka URL marketing LANGSUNG lewat Chrome profil toko (baca Target +
   Arguments .lnk → jalankan chrome.exe + URL sebagai argumen terakhir;
   TANPA keystroke) — lihat core/window.launch_url_in_profile. Tampilan
   default Chrome (NTP/restore tab/halaman terakhir) tidak pernah dibaca
   atau ditunggu.
5. Jalur utama: tunggu window baru secara pasif (tanpa keystroke, tanpa aktivasi
   window lain). Jalur fallback (kalau launch langsung gagal): startfile .lnk →
   Ctrl+T → Ctrl+L → paste URL → Enter (tanpa Down/Tab/klik).
6. Tunggu halaman render (delay tetap).
7. Scroll ke bawah SCROLL_AMOUNT notch (diukur sekali via
   calibrate_chart_crop.py) supaya bagian iklan produk kelihatan.
8. Capture region chart dengan koordinat CHART_CROP & CROP_MARGIN_PX,
   simpan ke logs/screenshots/iklan/<nama_toko>_<tanggal>.png.
9. Cetak marker:
   - 📌 SCREENSHOT_IKLAN_FILE: <path>
   - 📌 SCREENSHOT_IKLAN_TOKO: <path>\t<nama toko>
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from core.caption import bangun_teks_caption
from core.clipboard import copy_files_with_caption
from core.config import Config, ConfigError
from core.window import (
    activate_window,
    chrome_windows as _chrome_windows,
    ensure_foreground,
    launch_url_in_profile,
)

BASE = Path(__file__).resolve().parent
OUT_DIR = BASE / "logs" / "screenshots" / "iklan"

# ── Konstanta Opsi ─────────────────────────────────────────────────────
LABEL_DI_GAMBAR = False


def _apply_label_to_image(img_path: Path, store_name: str) -> None:
    """Tambahkan strip teks 'Shopee Ads [<nama toko>]' di bagian atas PNG jika LABEL_DI_GAMBAR=True."""
    if not LABEL_DI_GAMBAR:
        return
    try:
        from PIL import Image, ImageDraw, ImageFont
        img = Image.open(img_path)
        w, h = img.size
        strip_h = 40
        new_img = Image.new("RGB", (w, h + strip_h), (255, 255, 255))
        new_img.paste(img, (0, strip_h))
        draw = ImageDraw.Draw(new_img)
        font = None
        for font_path in [
            r"C:\Windows\Fonts\arial.ttf",
            r"C:\Windows\Fonts\segoeui.ttf",
        ]:
            if os.path.exists(font_path):
                try:
                    font = ImageFont.truetype(font_path, 20)
                    break
                except Exception:
                    pass
        if font is None:
            font = ImageFont.load_default()
        text = f"Shopee Ads [{store_name}]"
        draw.text((15, 10), text, fill=(0, 0, 0), font=font)
        new_img.save(img_path)
    except Exception as exc:
        print(f"⚠ Gagal menambahkan label ke gambar ({exc})")


# ── URL template ──────────────────────────────────────────────────────
_BASE_URL = (
    "https://seller.shopee.co.id/portal/marketing/pas/index"
    "?source_page_id=1&from={from_ts}&to={to_ts}"
    "&type=new_cpc_homepage&group=custom"
)

# ── Timezone ──────────────────────────────────────────────────────────
_TZ_JAKARTA = timezone(timedelta(hours=7))

# ── Timing ────────────────────────────────────────────────────────────
WINDOW_WAIT = 30          # detik menunggu window Chrome muncul
PAGE_LOAD_WAIT = 8        # detik tunggu halaman marketing selesai render chart
NAV_SETTLE = 0.3          # detik setelah Ctrl+T / Ctrl+L sebelum langkah berikut
PASTE_SETTLE = 0.4        # detik setelah paste URL sebelum Enter
SCROLL_SETTLE = 0.6       # detik setelah scroll sebelum screenshot
CHROME_TARGET_W = 1448
CHROME_TARGET_H = 876

# ── Chart Crop & Scroll Configuration ─────────────────────────────────
# Koordinat fraksi (left, top, right, bottom) bagian iklan produk di halaman
# marketing Shopee (diukur sekali via calibrate_chart_crop.py).
CHART_CROP = (0.000, 0.113, 1.000, 0.876)
CROP_MARGIN_PX = 30       # toleransi ekstra atas-bawah (pixel)
SCROLL_AMOUNT = 1110      # total notch scroll ke bawah
SCROLL_STEP = 20          # notch per step
BODY_CLICK_X_PCT = 0.5    # titik klik aman di body (tengah horizontal)
BODY_CLICK_Y_PCT = 0.4    # titik klik aman di body (atas-tengah vertical)

# ── Verifikasi Identitas Akun ─────────────────────────────────────────
SALAH_ABORT_N = 3
SALAH_ABORT_MIN_S = 3.0


def _win32():
    try:
        import win32gui
        import win32process
        return win32gui, win32process
    except ImportError:
        return None, None


def _foreground_chrome_window() -> tuple[int, str] | None:
    win32gui, _ = _win32()
    if win32gui is None:
        return None
    hwnd = win32gui.GetForegroundWindow()
    if not hwnd or not win32gui.IsWindowVisible(hwnd):
        return None
    title = win32gui.GetWindowText(hwnd) or ""
    return hwnd, title


def _window_identity(hwnd: int, akun: str) -> str:
    win32gui, win32process = _win32()
    if win32gui is None:
        return "kosong"
    try:
        _, pid = win32process.GetWindowThreadProcessId(hwnd)
        title = win32gui.GetWindowText(hwnd) or ""
        if not win32gui.IsWindowVisible(hwnd) or win32gui.IsIconic(hwnd):
            return "kosong"
        if not activate_window(hwnd):
            return "kosong"
        import pyautogui
        import pyperclip
        pyautogui.hotkey("ctrl", "a")
        time.sleep(0.15)
        pyautogui.hotkey("ctrl", "c")
        time.sleep(0.15)
        text = pyperclip.paste() or ""
        if not text.strip():
            return "kosong"
        if akun and akun.lower() in text.lower():
            return "ok"
        if "shopee" in title.lower() or "seller" in title.lower():
            if not akun:
                return "ok"
        return "salah"
    except Exception:
        return "kosong"


def _active_store_state() -> dict:
    state_path = BASE / "logs" / ".active_store.json"
    if state_path.exists():
        try:
            return json.loads(state_path.read_text("utf-8"))
        except Exception:
            pass
    return {}


def date_to_timestamp(date_str: str) -> int:
    dt = datetime.strptime(date_str.strip(), "%Y-%m-%d")
    dt_local = dt.replace(hour=0, minute=0, second=0, tzinfo=_TZ_JAKARTA)
    return int(dt_local.timestamp())


def date_to_timestamp_end(date_str: str) -> int:
    dt = datetime.strptime(date_str.strip(), "%Y-%m-%d")
    dt_local = dt.replace(hour=23, minute=59, second=59, tzinfo=_TZ_JAKARTA)
    return int(dt_local.timestamp())


def build_marketing_url(start_date: str, end_date: str) -> str:
    ts_from = date_to_timestamp(start_date)
    ts_to = date_to_timestamp_end(end_date)
    return _BASE_URL.format(from_ts=ts_from, to_ts=ts_to)


def _wait_store_window(name: str, akun: str = "", primary: bool = True,
                       timeout: float = WINDOW_WAIT) -> int | None:
    deadline = time.monotonic() + timeout
    t_mulai = time.monotonic()
    hwnd_gagal: int | None = None
    n_gagal = 0
    checked: set[int] = set()
    fallback_so = 4.0
    fallback_jalan = False
    while time.monotonic() < deadline:
        cand = _foreground_chrome_window() if "_foreground_chrome_window" in globals() else None
        # fallback to active check
        hwnd_fg = None
        try:
            import win32gui as _w
            hwnd_fg = _w.GetForegroundWindow()
        except Exception:
            pass
        
        if hwnd_fg:
            status = _window_identity(hwnd_fg, akun)
            if status == "ok":
                return hwnd_fg
            if status == "salah":
                checked.add(hwnd_fg)
        
        if not fallback_jalan and time.monotonic() - t_mulai >= fallback_so:
            fallback_jalan = True
            for hwnd2, title2 in _chrome_windows():
                if hwnd2 in checked:
                    continue
                status2 = _window_identity(hwnd2, akun)
                if status2 == "ok":
                    return hwnd2
                if status2 == "salah":
                    checked.add(hwnd2)
        time.sleep(0.7)
    return None


def _wait_store_window_passive(snapshot_hwnds: set[int], used_hwnds: set[int],
                               timeout: float = WINDOW_WAIT) -> int | None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        current = _chrome_windows()
        new_hwnds = [hwnd for hwnd, _ in current if hwnd not in snapshot_hwnds and hwnd not in used_hwnds]
        if len(new_hwnds) == 1:
            hwnd = new_hwnds[0]
            ensure_foreground(hwnd)
            return hwnd
        elif len(new_hwnds) > 1:
            print(f"❌ Ambigu: ditemukan {len(new_hwnds)} window Chrome baru sekaligus.")
            return None
        else:
            try:
                import win32gui as _w
                hwnd_fg = _w.GetForegroundWindow()
                if hwnd_fg and hwnd_fg not in used_hwnds:
                    # check if it's a chrome window
                    chrome_hwnds = {h for h, _ in current}
                    if hwnd_fg in chrome_hwnds:
                        ensure_foreground(hwnd_fg)
                        return hwnd_fg
            except Exception:
                pass
        time.sleep(0.7)
    print(f"❌ Window Chrome baru tidak muncul dalam {timeout:.0f} detik.")
    return None


def _attach_store_window(shortcut: str, name: str, akun: str = "") -> int | None:
    print(f"🪟 Menjalankan shortcut toko '{name}'...")
    try:
        os.startfile(shortcut)
    except Exception as exc:
        print(f"❌ Gagal menjalankan shortcut '{shortcut}': {exc}")
        return None
    return _wait_store_window(name, akun)


def _open_store_url(shortcut: str, name: str, akun: str,
                    url: str, used_hwnds: set[int]) -> tuple[int | None, bool]:
    snapshot = {hwnd for hwnd, _ in _chrome_windows()}
    print("🔗 Membuka URL langsung di Chrome profil toko (tanpa keystroke)...")
    if launch_url_in_profile(shortcut, url):
        hwnd = _wait_store_window_passive(snapshot, used_hwnds)
        if hwnd is not None:
            return hwnd, False
        print(f"❌ Jalur utama launch URL gagal / timeout untuk toko '{name}'.")
        return None, False
    hwnd = _attach_store_window(shortcut, name, akun)
    return hwnd, hwnd is not None


def _resize_chrome(hwnd: int) -> None:
    win32gui, _ = _win32()
    if win32gui is None:
        return
    try:
        import win32con
        if win32gui.IsIconic(hwnd):
            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
        win32gui.MoveWindow(hwnd, 0, 0, CHROME_TARGET_W, CHROME_TARGET_H, True)
        time.sleep(0.5)
    except Exception as exc:
        print(f"⚠ Tidak bisa resize window ({exc}) — lanjut dengan ukuran saat ini")


def _navigate_to_url(hwnd: int, url: str) -> bool:
    try:
        import pyautogui
        import pyperclip
    except ImportError:
        print("❌ pyautogui/pyperclip belum terinstall.")
        sys.exit(1)

    if not ensure_foreground(hwnd):
        print("❌ Window Chrome toko tidak bisa dipastikan foreground — navigasi dibatalkan.")
        return False

    print("🔗 Fallback: tab baru (Ctrl+T) → Ctrl+L → paste URL → Enter...")
    pyautogui.hotkey("ctrl", "t")
    time.sleep(NAV_SETTLE)
    pyautogui.hotkey("ctrl", "l")
    time.sleep(NAV_SETTLE)
    pyperclip.copy(url)
    pyautogui.hotkey("ctrl", "v")
    time.sleep(PASTE_SETTLE)
    pyautogui.press("enter")
    print(f"⏳ Menunggu halaman iklan render ({PAGE_LOAD_WAIT} detik)...")
    time.sleep(PAGE_LOAD_WAIT)
    return True


def _scroll_to_chart(hwnd: int) -> bool:
    try:
        import pyautogui
        import win32gui as _w
    except ImportError:
        print("❌ pyautogui/pywin32 belum terinstall.")
        sys.exit(1)

    if not ensure_foreground(hwnd):
        print("❌ Window Chrome toko tidak bisa dipastikan foreground — scroll dibatalkan.")
        return False
    time.sleep(0.3)

    rect = _w.GetWindowRect(hwnd)
    w = rect[2] - rect[0]
    h = rect[3] - rect[1]
    cx = rect[0] + int(w * BODY_CLICK_X_PCT)
    cy = rect[1] + int(h * BODY_CLICK_Y_PCT)

    pyautogui.click(cx, cy)
    time.sleep(0.3)

    print(f"📜 Scroll ke bawah {SCROLL_AMOUNT} notch...")
    steps = SCROLL_AMOUNT // SCROLL_STEP
    remainder = SCROLL_AMOUNT % SCROLL_STEP
    for _ in range(steps):
        pyautogui.scroll(-SCROLL_STEP)
        time.sleep(0.02)
    if remainder:
        pyautogui.scroll(-remainder)
    time.sleep(SCROLL_SETTLE)
    return True


def compute_crop_box(size, frac, margin_px: int = 0):
    width, height = size
    left = max(0, int(width * frac[0]))
    top = int(height * frac[1]) - margin_px
    right = min(width, int(width * frac[2]))
    bottom = int(height * frac[3]) + margin_px

    top = max(0, top)
    bottom = min(height, bottom)

    if right <= left:
        right = left + 1
    if bottom <= top:
        bottom = top + 1
    return (left, top, right, bottom)


def _take_screenshot(hwnd: int, out_path: Path) -> Path | None:
    from PIL import ImageGrab
    if not ensure_foreground(hwnd):
        print("❌ Window Chrome toko tidak bisa dipastikan foreground — screenshot dibatalkan.")
        return None

    try:
        import win32gui as _w
        rect = _w.GetWindowRect(hwnd)
        img = ImageGrab.grab(bbox=rect)
    except Exception as exc:
        print(f"❌ ImageGrab gagal: {exc}")
        return None

    size = img.size
    box = compute_crop_box(size, CHART_CROP, CROP_MARGIN_PX)
    try:
        img = img.crop(box)
    except Exception:
        pass

    out_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_path)
    _apply_label_to_image(out_path, out_path.stem.split("_")[0])
    print(f"📸 Screenshot tersimpan: {out_path}  ({img.size[0]}x{img.size[1]})")
    return out_path


def _capture_store(store: dict, start_date: str, end_date: str, used_hwnds: set[int]) -> tuple[str | None, int | None]:
    name = store["name"]
    shortcut = str(store.get("shortcut") or "").strip()
    print(f"📸 Screenshot Iklan — toko: {name}")

    if not shortcut:
        print("❌ config.yaml: stores[].shortcut belum diisi untuk toko ini.")
        return None, None

    url = build_marketing_url(start_date, end_date)
    print(f"ℹ URL: {url[:100]}...")

    akun = str(store.get("akun") or "")
    hwnd, perlu_navigasi = _open_store_url(shortcut, name, akun, url, used_hwnds)
    if hwnd is None:
        return None, None

    _resize_chrome(hwnd)

    if perlu_navigasi:
        if not _navigate_to_url(hwnd, url):
            return None, hwnd
    else:
        print(f"⏳ Menunggu halaman iklan render ({PAGE_LOAD_WAIT} detik)...")
        time.sleep(PAGE_LOAD_WAIT)

    if not _scroll_to_chart(hwnd):
        return None, hwnd

    ts_str = f"{start_date}_sd_{end_date}"
    safe_name = re.sub(r'[^\w\-]', '_', name)
    out_path = OUT_DIR / f"{safe_name}_{ts_str}.png"
    out_path = _take_screenshot(hwnd, out_path)
    if out_path is None:
        return None, hwnd

    print(f"✅ Screenshot iklan selesai: {out_path.name}")
    print(f"   Tersimpan di: {out_path}")
    print(f"📌 SCREENSHOT_IKLAN_FILE: {out_path}")
    print(f"📌 SCREENSHOT_IKLAN_TOKO: {out_path}\t{name}")
    return str(out_path), hwnd


def main() -> None:
    Config.ensure_loaded()
    state = _active_store_state()
    start_date = state.get("start_date", "")
    end_date = state.get("end_date", "")

    if not start_date or not end_date:
        print("❌ Pilih tanggal AWAL dan AKHIR di UI dulu.")
        sys.exit(1)

    stores = [s for s in Config.stores() if s.get("enabled")]
    if not stores:
        print("❌ Tidak ada toko yang enabled di config.yaml (stores: kosong).")
        sys.exit(1)

    ok = 0
    used_hwnds: set[int] = set()
    success_paths = []
    success_stores = []
    for store in stores:
        path, hwnd = _capture_store(store, start_date, end_date, used_hwnds)
        if path is not None:
            ok += 1
            success_paths.append(path)
            success_stores.append(store)
            if hwnd:
                used_hwnds.add(hwnd)
        print()

    if success_paths:
        caption = bangun_teks_caption(success_stores)
        if copy_files_with_caption(success_paths, caption):
            print(f"📌 {len(success_paths)} screenshot + caption tersalin. Paste ke WhatsApp.")

    print(f"\n✅ Selesai: {ok}/{len(stores)} toko berhasil di-screenshot.")


if __name__ == "__main__":
    main()
