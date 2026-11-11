# Session Report — 2026-11-11

## Ringkasan
Implementasi fungsi `open_bsm_shortcut()` di dalam `check_new.py` yang otomatis membaca dan meluncurkan file shortcut `C:\Users\PC\Desktop\Inventory BSM.lnk` (sesuai konfigurasi di `config.yaml`) saat tombol Start ditekan pada mode otomatis. Setelah jendela aplikasi terbuka, jendela difokuskan otomatis dan halaman web aplikasi diparsing menggunakan `parse_bsm.py`.

## Perubahan File
- `config.yaml`: Menambahkan path `shortcut: C:\Users\PC\Desktop\Inventory BSM.lnk` pada tool "Checklist Automation - New".
- `check_new.py`: Menambahkan fungsi peluncur shortcut `.lnk` (`open_bsm_shortcut()`) tepat sebelum persiapan window target.
- `test_e2e_bsm.py`: Memperbaiki format uji parser data BSM.

## Status Testing
- [x] Test suite pytest: **14/14 passed** (termasuk tes parser E2E BSM dan Playwright).
- [x] Peluncuran shortcut `.lnk` terintegrasi langsung dengan siklus Start tool.

---

# Session Report — 2026-11-10

## Ringkasan
Duplikasi menu Checklist Automation menjadi "Checklist Automation - New" di BOPEL (`config.yaml`), menambahkan script turunan `check_new.py`, serta mengonfigurasi `target_window_title: Inventory BSM` agar pada mode otomatis tool menargetkan dan membuka aplikasi desktop "Inventory BSM".
...
