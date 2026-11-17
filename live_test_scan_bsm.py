import time
import os
import sys
import pyautogui
from core.bsm import activate_and_refresh_bsm
from core.parsing_bsm import parse_bsm_page
import pyperclip

# Menambahkan directory saat ini ke sys.path agar bisa import
sys.path.append(os.getcwd())

def test_live_scan():
    # 1. Pastikan aplikasi siap
    if not activate_and_refresh_bsm():
        print("Aplikasi tidak siap.")
        return

    # 2. Koordinat dari config (misal untuk sekarang kita hardcode atau baca dari config)
    # Target: [-8,-8,1448,868]; x = L + 0.4512 * (R - L), y = T + 0.2089 * (B - T)
    # L=-8, T=-8, R=1448, B=868 -> R-L=1456, B-T=876
    x = -8 + 0.4512 * 1456
    y = -8 + 0.2089 * 876
    print(f"Klik di {x}, {y}")

    codes_to_test = ["2611028WKAQYXT", "261104DBU9377Y", "261199ZZZZZZZZ"]

    for kode in codes_to_test:
        print(f"\n--- Testing kode: {kode} ---")
        # Klik kotak pencarian
        pyautogui.click(x, y)
        time.sleep(0.5)

        # Ctrl+A, Ctrl+V, Enter
        pyautogui.hotkey('ctrl', 'a')
        pyperclip.copy(kode)
        pyautogui.hotkey('ctrl', 'v')
        pyautogui.press('enter')
        time.sleep(1.0)

        # Tab
        pyautogui.press('tab')
        time.sleep(0.5)

        # Ctrl+A, Ctrl+C
        pyautogui.hotkey('ctrl', 'a')
        time.sleep(0.5)
        pyautogui.hotkey('ctrl', 'c')
        time.sleep(0.5)

        text = pyperclip.paste()
        # Simpan sampel
        with open(f"logs/sample_{kode}.txt", "w") as f:
            f.write(text)

        # Parsing
        rows, cols_map, valid = parse_bsm_page(text, kode)
        print(f"Valid: {valid}, Rows found: {len(rows)}")
        for r in rows:
            print(f"Row: {r}")

if __name__ == "__main__":
    test_live_scan()
