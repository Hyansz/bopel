# Session Report — 2026-11-14 (Fix Countdown Trigger for `shopee_fetch.py`)

## Ringkasan
- Memperbaiki bug pada pemicu countdown 10 detik pasca-fetch: sebelumnya memeriksa `baseScript(key) === "shopee_fetch.py"` yang selalu mengembalikan `"check.py"`, sehingga hitung mundur gagal aktif saat `shopee_fetch.py` selesai sukses.
- Sekarang menggunakan pemeriksaan `const rawScript = String(key).split("::")[0]; rawScript === "shopee_fetch.py"`.

## Perubahan
- `web/app.js`: Di `onToolFinished`, mengganti pengecekan `baseScript(key)` dengan `rawScript === "shopee_fetch.py"`.

## Status Testing
- [x] `node --check web/app.js` lulus.
- [ ] E2E nyata: pastikan setelah log fetch berhasil, hitung mundur 10 detik langsung muncul di samping tombol Fetch.

---
# Session Report — 2026-11-14 (Refine Countdown Setelah Fetch & Tombol Lanjut saat Stop/Pause)

## Ringkasan
- Memindahkan pemicu hitung mundur 10 detik agar aktif **pasca-fetch sukses** (`shopee_fetch.py` selesai dengan sukses), bukan saat tombol Fetch diklik.
- Menambahkan logika tombol **"Lanjut"**: ketika proses (misal fetch data Shopee) dihentikan di tengah jalan lewat tombol Stop atau tombol `Q` (emergency stop), status berubah menjadi dihentikan (`stopped`), tombol Start berubah menjadi **"Lanjut"**, dan saat diklik akan mengulang/fetch data kembali (`onFetchClick()`).

## Perubahan
- `web/app.js`:
  - `onToolFinished`: memanggil `startFetchCountdown()` saat `shopee_fetch.py` selesai sukses (`success === true`).
  - `renderRunButtons`: mendeteksi status `stopped` dan mengubah teks label tombol menjadi `"Lanjut"`.
  - `onStartClick`: jika proses yang dihentikan adalah `shopee_fetch.py`, klik tombol `"Lanjut"` akan menjalankan ulang `onFetchClick()`.
  - Event listener `#start-btn` diganti ke `onStartClick`.

## Status Testing
- [x] `node --check web/app.js` lulus.
- [ ] E2E nyata di aplikasi pywebview.

---
﻿# Session Report â€” 2026-11-14 (Countdown Auto-Start Setelah Fetch Shopee)

## Ringkasan
Menambahkan hitung mundur 10 detik (dengan animasi bar) setelah tombol "Fetch dari Shopee" diklik, yang otomatis mengeklik Start (jalankan `check_new.py`). Chip countdown dapat diklik untuk jeda; klik lagi melanjutkan dari angka yang tersisa.

## Perubahan
- `web/index.html`: tambah `<button id="fetch-countdown">` di samping tombol Fetch.
- `web/app.js`: tambah modul hitung mundur (`startFetchCountdown`, `tickFetchCountdown`, `toggleFetchCountdown`, `endFetchCountdown`, `renderFetchCountdown`, `runFetchAutoStart`); `onFetchClick` memanggil `startFetchCountdown()`; auto-Start memanggil `onStart()` saat countdown habis, tetapi dilewati (dengan toast info) jika Start sedang disabled (mis. Fetch masih running atau belum ada mode).
- `web/style.css`: tambah style `.countdown-chip` dengan animasi bar horisontal menggunakan CSS custom property `--cd-frac` (diperbarui tiap tick 50 ms).

## Status Testing
- [x] `node --check web/app.js` lulus.
- [ ] E2E nyata: klik Fetch, lihat countdown berjalan â†’ jeda â†’ lanjutkan â†’ auto-Start berjalan.

---
# Session Report â€” 2026-11-13 (Update Scan Flow for Inventory BSM New Version)

## Ringkasan
- Mengubah alur scan di `scan.py` agar cocok dengan aplikasi Inventory BSM versi baru (web app).
- Menambahkan modul `core/bsm.py` untuk penanganan window "Inventory BSM", aktivasi foreground, peluncuran via shortcut, dan refresh (F5) sekali per run.
- Menambahkan modul `core/parsing_bsm.py` untuk memparsing teks halaman web app BSM baru yang disalin lewat `Ctrl+A` + `Ctrl+C`.
- Memperbarui `config.yaml` untuk tool "Inventory Scanner" (target window, shortcut, koordinat klik pencarian).
- Membuat skrip penunjang `tools_capture_bsm.py` dan `live_test_scan_bsm.py` untuk pengujian sampel dan visual.

## Root Cause / Alur Baru
- Aplikasi warehouse lama (`Inventorycabang`) diganti dengan web app `Inventory BSM`. Alur navigasi grid berbasis panah (`Down`/`Up`) diganti dengan klik koordinat absolut pada kotak pencarian, `Ctrl+A`/`Ctrl+V`/`Enter`, keluar via `Tab`, lalu `Ctrl+A`/`Ctrl+C` untuk membaca seluruh teks halaman dan diparsing secara aman.

## Status Testing
- [x] Test suite pytest 28/28 lulus.
- [ ] Tes live visual dengan aplikasi nyata (menunggu eksekusi langsung oleh user).

---

# Session Report â€” 2026-11-12 (Fix Price Validation NILAI vs Shopee in `check_new.py`)

## Ringkasan
- Memperbaiki validasi harga di `check_new.py` dan `bsm_match.py`: harga Shopee kini dibandingkan dengan kolom **NILAI** (harga kotor) Inventory BSM (bukan NET), dengan toleransi pembulatan `abs(harga_shopee - nilai) <= 1` rupiah.
- Menambahkan field `nilai` pada item `found` di `bsm_match.py`.
- Menerapkan **gating centang**: baris dengan harga BEDA tidak dicentang (`space`), dicatat di ringkasan `Beda:`, dan dicetak sebagai `[CEK MANUAL] baris N kode X: Shopee <harga> vs aplikasi <nilai>`. Plan navigasi `turun` dihitung ulang hanya untuk baris `OK`.
- Menambahkan unit test validasi harga (`test_price_validation_rules`) di `test_check_new_items.py`.

## Root Cause / Detail Perubahan
- Validasi harga sebelumnya membandingkan dengan `net` (harga setelah PPN/potongan), yang menyebabkan data nyata (seperti 120385, 39295, dll.) salah terbaca sebagai `BEDA` dan tidak ter-gate dengan benar.

## Status Testing
- Unit test baru dan pengujian harga lulus.
- BELUM terbukti secara visual langsung: menu New dengan data Shopee + Inventory BSM asli sampai panel salin terisi pada sesi GUI nyata.

---

# Session Report â€” 2026-11-12 (Fix Crash `check_new.py`, Unit Test Komprehensif, & Revisi Log Extra Rows)

## Ringkasan
- Memperbaiki crash `TypeError: object of type 'int' has no len()` pada `print_check_table()` di `check_new.py` dengan memperbaiki ekspresi `col_widths` (`max(len(headers[idx]), *(len(str(r[idx])) for r in rows))` alih-alih generator `len`).
- Merevisi pelaporan baris ekstra ("Ada di aplikasi tapi tidak di Shopee") di `bsm_match.py` agar diringkas menjadi satu baris di layar (`Baris lain di aplikasi (tidak dicentang): N`) dan detail lengkap ditulis ke `logs\bsm_match_last.txt`.
- Menambahkan test suite komprehensif di `test_check_new_items.py` menguji 0 baris, 1 baris (regresi crash), 6 baris, dan 77 baris data, dengan verifikasi parser `app.py`.

## Root Cause / Detail Perubahan
- `check_new.py` baris 101 menggunakan `max(..., key=len)` pada generator `len(...)` yang menghasilkan integer, menyebabkan `TypeError`.
- Log extra rows sebelumnya mencetak puluhan/ratusan baris ke konsol; kini diringkas dan disimpan ke `logs\bsm_match_last.txt`.

## Status Testing
- Unit test baru (`test_check_new_items.py` dengan kasus 0, 1, 6, 77 baris) dan test suite pytest lulus.
- BELUM terbukti secara visual langsung: menu New dengan data Shopee + Inventory BSM asli sampai panel salin terisi pada sesi GUI nyata.

---

# Session Report â€” 2026-11-12 (Pemasangan Ikon BOPEL & Fitur Item Checklist Automation - New)

## Ringkasan
- Menambahkan penanganan AppUserModelID (`BOPEL.Toolkit`) dan pemasangan ikon window via Windows API `WM_SETICON` (`ICON_SMALL` & `ICON_BIG`, `LoadImageW` dengan `LR_LOADFROMFILE | LR_DEFAULTSIZE`) di `app.py`.
- Membuat skrip PowerShell `buat_shortcut.ps1` untuk pembuatan shortcut `BOPEL.lnk` di Desktop dengan `start.bat`, working directory folder proyek, icon `assets\bopel.ico,0`, dan `WindowStyle = 7` (minimized), lengkap dengan konfirmasi timpa file jika sudah ada.
- Menambahkan fitur parsing tabel ringkasan per-item di `check_new.py` (mengembalikan fitur "Salin per kolom ke Excel" / `pushItems` pada Checklist Automation - New).
- Menambahkan unit test baru `test_window_icon.py` dan `test_check_new_items.py`.

## Root Cause / Detail Perubahan
- `check_new.py` sebelumnya tidak mencetak tabel ringkasan format standar yang di-parse oleh launcher `app.py` (`_parse_table_line`), sehingga panel "Salin per kolom ke Excel" tidak muncul.
- Diperbaiki dengan menambahkan `print_check_table()` di `check_new.py` dengan struktur kolom yang sesuai (`NO`, `KODE PESANAN`, `NOMOR FAKTUR`, `HARGA SHOPEE`, `COCOK`).

## Status Testing
- Unit test baru (`test_window_icon.py`, `test_check_new_items.py`) dan test suite pytest lulus.
- BELUM terbukti secara visual langsung: ikon benar-benar muncul di title bar/taskbar Windows user dan panel salin kolom benar-benar muncul di UI dengan data Shopee asli (perlu dicek langsung pada sesi GUI nyata).

---

# Session Report â€” 2026-11-11 (Tahap 2 BSM Live Centering & Ringkasan Angka)

## Ringkasan
- Revisi pelaporan metrik angka ringkasan di `check_new.py` (`Total` kini menghitung jumlah kode Shopee unik, bukan baris tabel aplikasi).
- Implementasi Tahap 2: navigasi baris otomatis menggunakan tombol panah bawah (`down`) dan pencentangan kolom P. menggunakan tombol spasi (`space`) berdasarkan `res["plan"]`.
- Penambahan konfigurasi opsional `bsm_first_row_click` di `config.yaml`.
- Seluruh pengujian test suite pytest lulus (**22/22 passed**).

## Perubahan File
- `check_new.py`: Mengaktifkan mode `live` untuk navigasi dan penekanan spasi per baris cocok.
- `parse_bsm.py`: Menambahkan ekstraksi `bayar_raw` dan `terbayar_raw` untuk verifikasi kolom bayar.
- `config.yaml`: Menambahkan `bsm_first_row_click: [0.768, 0.591]`.
- `test_bsm_step2.py`: Menambahkan unit test validasi metrik ringkasan.

## Status Pengujian
- Test suite pytest: **22/22 passed**.
- Uji navigasi panah bawah dan spasi dikonfirmasi benar oleh pengguna.

---

# Session Report â€” 2026-11-11 (Shortcut Integration)
...
