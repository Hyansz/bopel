import pyautogui
import pyperclip
import time
from datetime import datetime

def capture_bsm_sample(label):
    print("Mempersiapkan capture dalam 3 detik...")
    time.sleep(3)

    # 1. Ctrl+A, Ctrl+C
    pyautogui.hotkey('ctrl', 'a')
    time.sleep(0.5)
    pyautogui.hotkey('ctrl', 'c')
    time.sleep(0.5)

    text = pyperclip.paste()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    filename = f"bsm_scan_sample_{label}_{timestamp}.txt"

    with open(filename, "w", encoding="utf-8") as f:
        f.write(text)
    print(f"Teks disimpan ke {filename}")

if __name__ == "__main__":
    # Langsung pakai label hardcode untuk menghindari input
    capture_bsm_sample("sesudah_cari")
