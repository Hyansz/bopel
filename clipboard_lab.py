"""Skrip uji Clipboard Lab (A-E) untuk Screenshot Iklan & Caption.
Tidak dijalankan secara interaktif otomatis; sediakan menu CLI sederhana untuk pengujian manual.
"""

from __future__ import annotations

import os
from pathlib import Path
from core.clipboard import salin_paket
from core.caption import bangun_teks_caption


def find_latest_screenshots() -> list[Path]:
    base = Path("logs/screenshots/iklan")
    if not base.exists():
        return []
    # Ambil file PNG di root base (bukan di subfolder captioned/)
    files = [f for f in base.glob("*.png") if f.is_file()]
    # Urutkan berdasarkan waktu modifikasi terbaru
    files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
    return files


def main():
    print("=== CLIPBOARD LAB (A-E) ===")
    screenshots = find_latest_screenshots()
    if not screenshots:
        print("❌ Tidak ditemukan file screenshot asli di logs/screenshots/iklan/. Jalankan screenshot_iklan.py dulu.")
        return

    print(f"Ditemukan {len(screenshots)} file screenshot:")
    for i, p in enumerate(screenshots):
        print(f"  [{i}] {p.name}")

    # Ambil screenshot pertama sebagai sampel utama
    sample_path = screenshots[0]
    # Ambil nama toko untuk caption menggunakan helper bersama
    from core.store_name import nama_toko_dari_file
    final_store = nama_toko_dari_file(sample_path) or sample_path.stem.split("_")[0]
    caption = bangun_teks_caption([final_store])
    print(f"\nContoh Caption Terpilih:\n{caption}\n")

    while True:
        mode = input("Pilih mode [A/B/C/D/E] atau 'q' untuk keluar: ").strip().upper()
        if mode == 'Q':
            break
        if mode not in ['A', 'B', 'C', 'D', 'E']:
            print("Pilihan tidak valid. Masukkan A, B, C, D, E, atau q.")
            info_list = screenshots if mode == 'E' else [str(sample_path)]
            continue

        paths_to_copy = [str(p) for p in screenshots] if mode == 'E' else [str(sample_path)]
        res = salin_paket(mode, paths_to_copy, caption)
        print(f"👉 Mode {mode} Result: ok={res['ok']}")
        print(f"   Format terdaftar di Clipboard: {res['formats']}")
        print(f"   Caption disalin: {caption!r}")
        print("   -> Instruksi: Sekarang Ctrl+V di aplikasi tujuan (WhatsApp/Notepad/dll), lihat apakah gambar & teks muncul.\n")

    print("Keluar dari Clipboard Lab.")


if __name__ == "__main__":
    main()
