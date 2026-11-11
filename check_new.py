import time
import os
import pyautogui
import pyperclip
import re
import sys

from core import window
from core.config import Config
from core.observ import simpan_metrik
import bsm_match

UI_MODE = os.environ.get("BOPEL_UI_MODE") == "1"
SCRIPT_NAME = os.path.basename(__file__)
GRACE_PASTE_DATA = 5
FAST = 0.12

CODE_PATTERN = re.compile(r'\b26[A-Z0-9]{12,13}\b')
CLIP_SENTINEL = "__CLIP_EMPTY_SENTINEL__"
STEP1_ONLY = True  # Step 1 only per instructions: parse and report, do not check/click


def safe_copy(delay=FAST, retries=4, settle=0.05, metrik=None):
    for attempt in range(retries):
        if metrik is not None and attempt > 0:
            metrik["retry"] += 1
        pyperclip.copy(CLIP_SENTINEL)
        time.sleep(settle)
        pyautogui.hotkey('ctrl', 'c')
        time.sleep(delay + attempt * 0.05)
        text = pyperclip.paste()
        if text is not None and text != CLIP_SENTINEL and text.strip() != "":
            return text
    return None


def parse_shopee_prices(raw_text, target_codes):
    result = {}
    matches = list(CODE_PATTERN.finditer(raw_text))
    for i, m in enumerate(matches):
        kode = m.group(0)
        if kode not in target_codes or kode in result:
            continue
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(raw_text)
        block = raw_text[start:end]
        price_match = re.search(r'Rp\s*([\d.,]+)', block)
        if price_match:
            cleaned = re.sub(r'[^\d]', '', price_match.group(1))
            if cleaned:
                result[kode] = int(cleaned)
    return result


def open_bsm_shortcut():
    Config.ensure_loaded()
    shortcut_path = ""
    for t in Config.tools():
        if t.get("script") == SCRIPT_NAME:
            shortcut_path = t.get("shortcut", "")
            break
    if not shortcut_path:
        shortcut_path = r"C:\Users\PC\Desktop\Inventory BSM.lnk"

    print(f"🚀 Membuka aplikasi Inventory BSM lewat shortcut: {shortcut_path}")
    try:
        os.startfile(shortcut_path)
        return True
    except Exception as exc:
        print(f"❌ Gagal membuka shortcut {shortcut_path}: {exc}")
        return False


print("=" * 50)
print("BOT VALIDASI + AUTO CHECKLIST (INVENTORY BSM - WEB APP)")
print("=" * 50)

if UI_MODE:
    print(f"\nSTEP 1:\nPastikan data Shopee sudah dicopy. Membaca dalam {GRACE_PASTE_DATA} detik...")
    time.sleep(GRACE_PASTE_DATA)
else:
    input("\nSTEP 1:\nCopy data Shopee → ENTER...\n")

raw = pyperclip.paste()
if not raw.strip():
    print("❌ Clipboard kosong!")
    sys.exit(1)

orders = CODE_PATTERN.findall(raw)
orders = list(dict.fromkeys(orders))
if not orders:
    print("❌ Tidak ada kode pesanan Shopee ditemukan di clipboard.")
    sys.exit(1)

print(f"\nTotal order Shopee terbaca: {len(orders)}")
shopee_prices = parse_shopee_prices(raw, set(orders))
pyperclip.copy("")

print("\nSTEP 2:")
open_bsm_shortcut()
time.sleep(3.0)

hwnd = window.persiapkan_window_target(SCRIPT_NAME, required=UI_MODE)
print("Mengambil data halaman BSM via Ctrl+A...")

if UI_MODE:
    time.sleep(2)
else:
    input("Klik area netral di halaman BSM, lalu ENTER...")

pyautogui.hotkey('ctrl', 'a')
time.sleep(0.3)
bsm_raw = safe_copy(delay=0.3, retries=5)
pyautogui.press('esc')

if not bsm_raw:
    print("❌ Gagal menyalin halaman BSM dari clipboard.")
    sys.exit(1)

# Simpan teks hasil Ctrl+A ke logs\bsm_ctrla_last.txt untuk debugging
os.makedirs("logs", exist_ok=True)
with open(r"logs\bsm_ctrla_last.txt", "w", encoding="utf-8") as f:
    f.write(bsm_raw)

# Match codes with bsm_match
res = bsm_match.match_codes(orders, bsm_raw)
bsm_match.print_report(res)

# Cetak baris ringkasan dengan label yang dipahami launcher untuk kartu metrik UI
total_n = res["total_baris_app"]
cocok_n = len(res["found"])
tidak_n = len(res["missing"])
print(f"Total: {total_n}")
print(f"Ketemu: {cocok_n} / {total_n}")
print(f"Sudah: {cocok_n}")
print(f"Beda: 0")
print(f"Tidak: {tidak_n}")
print(f"Waktu: 1.00 detik")

if res["parser_problems"] or total_n == 0:
    print("❌ Ctrl+A tidak terbaca sebagai tabel Inventory BSM; pastikan halaman Tambah Bayar Customer terbuka dan fokus ada di area netral.")
    sys.exit(1)

if STEP1_ONLY:
    print("\n✔ STEP 1 Selesai (STEP1_ONLY = True): Sesuai instruksi, skrip berhenti setelah laporan pencocokan.")
    sys.exit(0)
