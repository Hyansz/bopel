"""Unit test untuk screenshot_iklan.py — timestamp conversion, URL building, caption, label, & full chain simulation.

Jalankan: python test_screenshot_iklan.py
"""

from datetime import datetime, timedelta, timezone
from screenshot_iklan import (
    build_marketing_url,
    compute_crop_box,
    date_to_timestamp,
    date_to_timestamp_end,
    bangun_teks_caption,
)

_TZ = timezone(timedelta(hours=7))
_PASS = 0
_FAIL = 0


def check(name: str, got, want) -> None:
    global _PASS, _FAIL
    if got == want:
        _PASS += 1
    else:
        _FAIL += 1
        print(f"  ✗ {name}: got {got!r}, want {want!r}")


# ── date_to_timestamp (awal hari 00:00:00 GMT+7) ─────────────────────
print("date_to_timestamp:")

ts = date_to_timestamp("2026-08-20")
dt = datetime.fromtimestamp(ts, tz=_TZ)
check("2026-08-20 jam", dt.hour, 0)
check("2026-08-20 menit", dt.minute, 0)
check("2026-08-20 detik", dt.second, 0)
check("2026-08-20 nilai", ts, 1787158800)

ts2 = date_to_timestamp("2026-01-01")
dt2 = datetime.fromtimestamp(ts2, tz=_TZ)
check("2026-01-01 jam", dt2.hour, 0)
check("2026-01-01 nilai", ts2, 1767200400)

# ── date_to_timestamp_end (akhir hari 23:59:59 GMT+7) ────────────────
print("date_to_timestamp_end:")

ts_e = date_to_timestamp_end("2026-08-20")
dt_e = datetime.fromtimestamp(ts_e, tz=_TZ)
check("2026-08-20 end jam", dt_e.hour, 23)
check("2026-08-20 end menit", dt_e.minute, 59)
check("2026-08-20 end detik", dt_e.second, 59)
check("2026-08-20 end nilai", ts_e, 1787245199)

ts_e2 = date_to_timestamp_end("2026-01-01")
check("2026-01-01 end nilai", ts_e2, 1767286799)

# ── build_marketing_url ──────────────────────────────────────────────
print("build_marketing_url:")

url = build_marketing_url("2026-08-20", "2026-08-20")
check("domain", "seller.shopee.co.id" in url, True)
check("path", "/portal/marketing/pas/index" in url, True)
check("source_page_id", "source_page_id=1" in url, True)
check("from param", "from=1787158800" in url, True)
check("to param", "to=1787245199" in url, True)
check("type param", "type=new_cpc_homepage" in url, True)
check("group param", "group=custom" in url, True)

url2 = build_marketing_url("2026-01-01", "2026-01-01")
check("url2 from", "from=1767200400" in url2, True)
check("url2 to", "to=1767286799" in url2, True)

# ── from < to ────────────────────────────────────────────────────────
print("ordering:")
check("from < to", date_to_timestamp("2026-08-20") < date_to_timestamp_end("2026-08-20"), True)
check("different dates", date_to_timestamp("2026-08-19") < date_to_timestamp_end("2026-08-20"), True)

# ── compute_crop_box (crop chart, revisi 2026-09-03) ──────────────────
print("compute_crop_box:")
size = (1448, 876)

box = compute_crop_box(size, (0.0, 0.50, 1.0, 0.80), 0)
check("no-margin left", box[0], 0)
check("no-margin top", box[1], int(876 * 0.50))
check("no-margin right", box[2], 1448)
check("no-margin bottom", box[3], int(876 * 0.80))

box_m = compute_crop_box(size, (0.0, 0.50, 1.0, 0.80), 30)
check("margin top -30", box_m[1], int(876 * 0.50) - 30)
check("margin bottom +30", box_m[3], int(876 * 0.80) + 30)

box_t = compute_crop_box(size, (0.0, 0.02, 1.0, 0.05), 30)
check("margin clamp top>=0", box_t[1] >= 0, True)
box_b = compute_crop_box(size, (0.0, 0.95, 1.0, 0.98), 30)
check("margin clamp bottom<=h", box_b[3] <= size[1], True)

box_odd = compute_crop_box(size, (0.9, 0.9, 0.1, 0.1), 0)
check("order right>left", box_odd[2] > box_odd[0], True)
check("order bottom>top", box_odd[3] > box_odd[1], True)


# ── bangun_teks_caption ──────────────────────────────────────────────
print("bangun_teks_caption:")
cap1 = bangun_teks_caption(["Toko A", {"name": "Toko B"}, ""])
check("caption format & order", cap1, "Shopee Ads [Toko A]\nShopee Ads [Toko B]")

# ── LABEL_DI_GAMBAR & _apply_label_to_image ──────────────────────────
print("LABEL_DI_GAMBAR:")
import screenshot_iklan as si
from pathlib import Path
from PIL import Image
si.LABEL_DI_GAMBAR = True
tmp_img = Path("logs/screenshots/iklan/_test_label.png")
tmp_img.parent.mkdir(parents=True, exist_ok=True)
img_base = Image.new("RGB", (100, 100), (255, 255, 255))
img_base.save(tmp_img)
si._apply_label_to_image(tmp_img, "Toko Test")
img_res = Image.open(tmp_img)
img_res.close()
check("label height increased", img_res.size[1] > 100, True)
if tmp_img.exists():
    tmp_img.unlink()
si.LABEL_DI_GAMBAR = False


# ── Signature Test ────────────────────────────────────────────────────
print("signature test:")
import inspect
sig = inspect.signature(si._open_store_url)
check("_open_store_url has used_hwnds parameter", "used_hwnds" in sig.parameters, True)


# ── Full Chain Simulation Test ───────────────────────────────────────
print("full chain simulation test:")
from unittest import mock
import sys

stores_mock = [
    {"name": "Toko Alpha", "shortcut": "alpha.lnk", "enabled": True},
    {"name": "Toko Beta", "shortcut": "beta.lnk", "enabled": True},
    {"name": "Toko Gamma", "shortcut": "gamma.lnk", "enabled": True},
]

class MockGrab:
    @staticmethod
    def grab(bbox=None):
        return Image.new("RGB", (1448, 876), (200, 200, 200))

active_windows = []
hwnd_counter = 100

def mock_launch_url(shortcut, url):
    global hwnd_counter
    hwnd_counter += 1
    tname = "Unknown"
    if "alpha" in shortcut:
        tname = "Toko Alpha"
    elif "beta" in shortcut:
        tname = "Toko Beta"
    elif "gamma" in shortcut:
        tname = "Toko Gamma"
    active_windows.append((hwnd_counter, tname))
    return True

with mock.patch("screenshot_iklan.Config.stores", return_value=stores_mock), \
     mock.patch("screenshot_iklan._active_store_state", return_value={"start_date": "2026-08-20", "end_date": "2026-08-20"}), \
     mock.patch("screenshot_iklan.launch_url_in_profile", side_effect=mock_launch_url), \
     mock.patch("screenshot_iklan._chrome_windows", side_effect=lambda: list(active_windows)), \
     mock.patch("screenshot_iklan.ensure_foreground", return_value=True), \
     mock.patch("screenshot_iklan._scroll_to_chart", return_value=True), \
     mock.patch("PIL.ImageGrab.grab", MockGrab.grab), \
     mock.patch("time.sleep", return_value=None), \
     mock.patch("win32gui.GetWindowRect", return_value=(0, 0, 1448, 876)), \
     mock.patch("win32gui.MoveWindow"), \
     mock.patch("win32gui.IsIconic", return_value=False), \
     mock.patch("sys.stdout", autospec=True):
    
    try:
        active_windows.clear()
        hwnd_counter = 100
        si.main()
        main_ok = True
    except Exception as exc:
        print(f"  ✗ main() exception: {exc}")
        import traceback
        traceback.print_exc()
        main_ok = False
    check("main() ran without exception", main_ok, True)

# Test fallback scenario (launch_url_in_profile -> False, _window_identity -> 'ok')
with mock.patch("screenshot_iklan.Config.stores", return_value=[{"name": "Toko Fallback", "shortcut": "fb.lnk", "enabled": True, "akun": "acc1"}]), \
     mock.patch("screenshot_iklan._active_store_state", return_value={"start_date": "2026-08-20", "end_date": "2026-08-20"}), \
     mock.patch("screenshot_iklan.launch_url_in_profile", return_value=False), \
     mock.patch("screenshot_iklan.os.startfile", return_value=None), \
     mock.patch("screenshot_iklan._foreground_chrome_window", return_value=(999, "Fallback Window")), \
     mock.patch("screenshot_iklan._window_identity", return_value="ok"), \
     mock.patch("screenshot_iklan.ensure_foreground", return_value=True), \
     mock.patch("screenshot_iklan._navigate_to_url", return_value=True), \
     mock.patch("screenshot_iklan._scroll_to_chart", return_value=True), \
     mock.patch("PIL.ImageGrab.grab", MockGrab.grab), \
     mock.patch("time.sleep", return_value=None), \
     mock.patch("win32gui.GetWindowRect", return_value=(0, 0, 1448, 876)), \
     mock.patch("win32gui.MoveWindow"), \
     mock.patch("win32gui.IsIconic", return_value=False):
    try:
        si.main()
        fallback_ok = True
    except Exception as exc:
        print(f"  ✗ fallback main() exception: {exc}")
        fallback_ok = False
    check("fallback main() ran without exception", fallback_ok, True)


# ── summary ──────────────────────────────────────────────────────────
status = "PASS" if _FAIL == 0 else "FAIL"
print(f"\n{_PASS}/{_PASS + _FAIL} tests {status}")
if _FAIL:
    raise SystemExit(1)
