"""End-to-End Test with Playwright for BOPEL Toolkit and BSM Parser Integration."""

import os
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright
from parse_bsm import parse_page


def test_e2e_bsm_and_ui():
    print("[E2E] Memulai pengujian Playwright untuk BOPEL & Parser BSM...")

    # 1. Uji parser BSM dengan sampel data realistis (2 tanggal, nilai - ppn = net)
    sample_data = """
1	26-FP.2026.0001	2026-11-10	2026-11-20	0	10000	100000	0	0	90000	2611028Q6QTV
2	26-FP.2026.0002	2026-11-10	2026-11-20	0	5000	50000	0	0	45000	2611028Q6QTW
Total Bayar 2 baris
"""
    res = parse_page(sample_data)
    print(f"[E2E] Hasil parse BSM: {len(res['rows'])} baris terbaca, masalah: {res['problems']}")
    assert len(res["rows"]) == 2
    assert res["problems"] == []

    # 2. Uji antarmuka web BOPEL via Playwright (menggunakan file index.html lokal)
    index_path = Path("web/index.html").resolve()
    assert index_path.exists(), f"index.html tidak ditemukan di {index_path}"

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(f"file:///{index_path.as_posix()}")

        title = page.title()
        print(f"[E2E] Judul halaman BOPEL: {title}")
        assert "Bopel" in title

        page.wait_for_selector("#app-title", timeout=3500)
        app_title_text = page.locator("#app-title").inner_text()
        print(f"[E2E] Header Title terbaca: {app_title_text}")

        browser.close()
    print("[E2E] Pengujian Playwright Selesai — Semua pemeriksaan E2E sukses ✅")


if __name__ == "__main__":
    test_e2e_bsm_and_ui()
