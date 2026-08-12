import time
import re
import pyautogui
import pyperclip
import sys
import os
from openpyxl import Workbook, load_workbook
from openpyxl.styles import PatternFill, Font

from core.observ import (
    ambil_screenshot,
    cetak_ringkasan,
    simpan_metrik,
    tunggu_grid_respon,
)

# =============================
# CONFIG — SILAKAN TUNING DI SINI
# =============================
# pyautogui secara default punya jeda 0.1 detik di SETIAP pemanggilan
# fungsi (hotkey/press/dll). Ini "pajak tersembunyi" yang paling besar
# pengaruhnya kalau scan ratusan baris. Diturunkan ke 0.02.
pyautogui.PAUSE = 0.02
pyautogui.FAILSAFE = True  # gerakkan mouse ke pojok layar buat emergency stop

# DELAY_AFTER_ENTER paling krusial: grid hasil search butuh waktu buat
# load. Kalau terlalu pendek, yang ke-copy masih grid lama / loading ->
# data yang ADA malah ke-cap NOT FOUND. Dinaikkan bertahap (0.35 -> 0.5
# -> 0.7). Konsekuensinya cuma nambah ~0.2s per baris, tapi hasil jauh
# lebih akurat. Kalau MASIH sering ada NOT FOUND palsu, naikkan lagi.
#
# OBSERVABILITY 2026-08-12: di loop scan utama & fase re-search, delay
# statis ini SUDAH DIGANTI polling tunggu_grid_respon() (cek kondisi
# 'clipboard berisi hasil copy' + timeout), jadi nilainya di sini cuma
# jadi referensi/fallback kalau polling dimatikan. Titik yang MASIH
# pakai nilai ini secara langsung: jeda antar 'down' pas ngumpulin baris
# duplikat (kumpulin_semua_baris_memo) -- di sana sleep statis sengaja
# dipertahankan, soalnya kalau ditekan ke polling tanpa jeda, baca
# clipboard bisa nyomot FRAME LAMA (scroll belum ke-render) -> baris
# duplikat di bawahnya ketutup -> grup dianggap selesai duluan.
DELAY_AFTER_ENTER = 0.7
DELAY_AFTER_DOWN  = 0.22   # tadinya 0.20
DELAY_AFTER_UP    = 0.08   # tadinya 0.15

# Polling pengganti delay statis: batas waktu maksimal tunggu grid
# merespons (tiap iterasi polling = 1x Ctrl+C ke clipboard). Grid yang
# lambat jadi nunggu SAMPAI data kebaca (bukan nunggu detik ke-0.7 doang
# terus lanjut), grid yang cepat gak ditebus delay penuh.
POLL_GRID_TIMEOUT = 1.5

# NOTE soal NOT FOUND palsu (race condition):
# Dulu SEARCH_RETRY & COPY_RETRY (retry berlapis) DIHAPUS buat ngirit
# waktu, tapi muncul bug baru: kadang grid hasil search belum ke-load pas
# 'down' ditekan -> yang ke-copy kosong / cuma HEADER -> data yang
# SEBENARNYA ADA malah ke-cap NOT FOUND (acak, cuma kena beberapa baris
# per scan). Di versi sekarang find_data_row diperbaiki biar NOT FOUND
# itu beneran NOT FOUND:
#   1. Semua hasil baca yang "mencurigakan" (clipboard kosong, cuma
#      header, atau data tapi memo gak cocok) di-retry dulu (baca ulang
#      setelah nunggu sebentar / nge-down), bukan langsung nyerah.
#   2. Kalau masih mencurigakan, kode di-SEARCH ULANG dari awal sekali
#      (balik ke kotak search, ketik ulang, enter, down, baca). Kode cuma
#      dianggap NOT FOUND kalau setelah search ulang pun tetap gak ketemu.
# Baris yang sehat tetap cepat (langsung ketemu di baca pertama); yang
# beneran gak ada baru "dihukum" nambah waktu buat konfirmasi.
HEADER_RETRY = 2
HEADER_RETRY_DELAY = 0.18
RE_SEARCH_KONFIRMASI = True   # False = matiin konfirmasi search ulang (lebih cepat, tapi rawan NOT FOUND palsu)

# GABUNG_ROW_DUPLIKAT: 1 kode pesanan (kolom Memo) kadang muncul di >1 baris
# grid (mis. split faktur: No.Faktur beda, Customer & Total SAMA PERSIS, cuma
# Status Bayar yang bisa beda -- satu Sudah, satu Belum). Sebelumnya yang
# dipakai cuma baris PERTAMA yang cocok -> kalau baris pertama kebaca 'Belum'
# padahal ada baris lain (Memo sama, harga sama) yang 'Sudah', hasilnya salah
# nyatet Belum. Fitur ini ngumpulin SEMUA baris yang Memo-nya sama dan mutusin
# baris mana yang 'asli' (prioritas yang Sudah, kalau harganya konsisten).
# False = matiin (balik ke perilaku lama: ambil baris pertama doang, lebih
# cepat tapi rawan salah 'Belum' kalau baris pertama yang kebaca yang Belum).
GABUNG_ROW_DUPLIKAT = True

# Batas aman anti infinite-loop pas ngumpulin baris duplikat (jaga-jaga aja;
# normalnya grup kode yang sama cuma 2-3 baris).
MAX_ROW_DUPLIKAT = 10

# =============================
# TAMPILAN LOG DI CMD
# =============================
# Default False -> cmd cuma nampilin progress bar + ringkasan akhir (bersih,
# gak berisik). Ganti ke True kapan aja kalau butuh lihat detail tiap baris
# (🟢/🟡/🔴 satu-satu) + info [DEBUG] pas ada yang NOT FOUND.
SHOW_DETAIL_LOG = False
DEBUG_NOTFOUND_LIMIT = 8   # batasi biar cmd gak kebanjiran pas SHOW_DETAIL_LOG aktif

# OBSERVABILITY — auto-screenshot ke logs/screenshots/.
# Setiap NOT FOUND & re-search difoto (biasanya jarang, difoto semua).
# Retry ringan difoto tapi DI-BATASI biar gak banjir file kalau lagi
# banyak yang retry. Matiin total: FOTO_AKTIF = False.
FOTO_AKTIF = True
FOTO_RETRY_BATAS = 5

# posisi kolom Price/Harga = 10 dari kiri (hitung mulai 1)
# di Python index dimulai dari 0, jadi index-nya = posisi - 1
PRICE_COLUMN_INDEX = 9

# posisi kolom Retur = 12 dari kiri (hitung mulai 1) -> index 11
RETUR_COLUMN_INDEX = 11

# posisi kolom Tanggal = 3 dari kiri (hitung mulai 1) -> index 2
TANGGAL_COLUMN_INDEX = 2

# posisi kolom Salesman = 7 dari kiri (hitung mulai 1) -> index 6
SALESMAN_COLUMN_INDEX = 6

# nama kolom "No. Pesanan" di file export Excel Shopee (mode skala besar).
# dipakai buat cari otomatis index kolomnya dari baris header, jadi gak
# hardcode posisi kalau urutan kolom Shopee berubah-ubah.
SHOPEE_KODE_HEADER_NAME = "No. Pesanan"

# nama kolom harga/total di export Excel Shopee (mode skala besar) -> ini
# yang secara posisi ada di kolom AG. Dicari dari NAMA header (bukan
# hardcode huruf kolom AG), soalnya kalau user cuma copy sebagian tabel
# (gak mulai dari kolom A), posisi huruf kolomnya bakal geser tapi nama
# headernya tetap sama.
SHOPEE_HARGA_HEADER_NAME = "Total Penghasilan"

CHECKPOINT_FILE = "checkpoint_scan.xlsx"
CHECKPOINT_EVERY = 25   # autosave tiap 25 baris, biar aman kalau 800 baris macet di tengah

spinner = ["|", "/", "-", "\\"]

# =============================
# HEADER
# =============================
print("=" * 60)
print(" INVENTORY PAYMENT CHECKER (OPTIMIZED) ")
print("=" * 60)

# =============================
# RESUME DARI CHECKPOINT (kalau ada)
# =============================
sudah = []
belum = []
not_found = []

# NEW: nyimpen hasil dalam URUTAN SCAN (dipakai buat tabel ringkasan di cmd),
# beda sama sudah/belum/not_found yang kepisah per kategori.
hasil_urut = []

sudah_scan = set()

if os.path.exists(CHECKPOINT_FILE):
    if input(f"\nDitemukan checkpoint '{CHECKPOINT_FILE}'. Lanjutkan dari situ? (y/n): ").lower() == "y":
        wb_ck = load_workbook(CHECKPOINT_FILE)
        ws_ck = wb_ck.active
        for row in ws_ck.iter_rows(min_row=2, values_only=True):
            # dukung checkpoint format LAMA (9 kolom, sebelum ada
            # ValidasiHarga & HargaExcel), format SEDANG (11 kolom),
            # format BARU (13 kolom: + JumlahDuplikatRow & CatatanMerge
            # buat gabung row duplikat), maupun format TERBARU (14 kolom:
            # + JumlahCocokExcel buat notifikasi duplikasi tervalidasi).
            if len(row) >= 14:
                nomor, no_faktur, salesman, customer, tanggal, memo, harga, retur, status, validasi, harga_excel_ck, jumlah_dupl_ck, catatan_ck, jumlah_cocok_ck = row
            elif len(row) >= 13:
                nomor, no_faktur, salesman, customer, tanggal, memo, harga, retur, status, validasi, harga_excel_ck, jumlah_dupl_ck, catatan_ck = row
                jumlah_cocok_ck = 0
            elif len(row) >= 11:
                nomor, no_faktur, salesman, customer, tanggal, memo, harga, retur, status, validasi, harga_excel_ck = row
                jumlah_dupl_ck, catatan_ck, jumlah_cocok_ck = 1, "", 0
            else:
                nomor, no_faktur, salesman, customer, tanggal, memo, harga, retur, status = row
                validasi, harga_excel_ck, jumlah_dupl_ck, catatan_ck, jumlah_cocok_ck = "-", "", 1, "", 0

            sudah_scan.add(nomor)
            if status == "Sudah":
                sudah.append({"nomor": nomor, "no_faktur": no_faktur, "salesman": salesman, "customer": customer, "tanggal": tanggal, "memo": memo, "harga": harga, "retur": retur, "validasi": validasi, "harga_excel": harga_excel_ck, "jumlah_duplikat_row": jumlah_dupl_ck, "catatan_merge": catatan_ck or "", "jumlah_cocok_excel": jumlah_cocok_ck or 0})
                hasil_urut.append({"nomor": nomor, "no_faktur": no_faktur, "salesman": salesman, "customer": customer, "tanggal": tanggal, "memo": memo, "status": "Sudah", "validasi": validasi, "harga": harga, "harga_excel": harga_excel_ck, "retur": retur, "jumlah_duplikat_row": jumlah_dupl_ck, "catatan_merge": catatan_ck or "", "jumlah_cocok_excel": jumlah_cocok_ck or 0})
            elif status == "Belum":
                belum.append({"nomor": nomor, "no_faktur": no_faktur, "salesman": salesman, "customer": customer, "tanggal": tanggal, "memo": memo, "harga": harga, "retur": retur, "validasi": validasi, "harga_excel": harga_excel_ck, "jumlah_duplikat_row": jumlah_dupl_ck, "catatan_merge": catatan_ck or "", "jumlah_cocok_excel": jumlah_cocok_ck or 0})
                hasil_urut.append({"nomor": nomor, "no_faktur": no_faktur, "salesman": salesman, "customer": customer, "tanggal": tanggal, "memo": memo, "status": "Belum", "validasi": validasi, "harga": harga, "harga_excel": harga_excel_ck, "retur": retur, "jumlah_duplikat_row": jumlah_dupl_ck, "catatan_merge": catatan_ck or "", "jumlah_cocok_excel": jumlah_cocok_ck or 0})
            else:
                not_found.append(nomor)
                hasil_urut.append({"nomor": nomor, "no_faktur": "-", "salesman": "-", "customer": "-", "tanggal": "", "memo": "-", "status": "Not Found", "validasi": "-", "harga": "", "harga_excel": "", "jumlah_duplikat_row": 1, "catatan_merge": "", "jumlah_cocok_excel": 0})
        print(f"-> Melanjutkan, {len(sudah_scan)} nomor sudah pernah di-scan.")

# =============================
# STEP 1 — PILIH MODE INPUT
# =============================
print(
"""
STEP 1

Pilih mode input:
  1. Skala KECIL  -> paste daftar kode pesanan langsung (satu kode per baris)
  2. Skala BESAR  -> paste mentahan hasil export Excel Shopee
                      (banyak kolom, bot otomatis ambil kolom 'No. Pesanan')
"""
)

mode_input = ""
while mode_input not in ("1", "2"):
    mode_input = input("Pilih 1 atau 2: ").strip()

if mode_input == "1":
    input(
"""
Copy daftar Nomor Faktur / kode pesanan
(satu nomor per baris)

ENTER...
"""
    )
else:
    input(
"""
Copy sel-sel hasil export Excel Shopee
(boleh copy seluruh tabel apa adanya, termasuk baris
'total(Rp)' dan header -> bot otomatis pilah sendiri)

ENTER...
"""
    )

raw = pyperclip.paste().strip()

if not raw:
    print("❌ Clipboard kosong!")
    sys.exit()


def extract_kode_dan_harga_dari_excel_shopee(raw_text):
    """
    Mode skala besar: raw_text adalah hasil copy tabel Excel Shopee apa
    adanya (tab-separated), termasuk baris 'total(Rp)' di atas dan baris
    header di bawahnya.

    Cara kerja:
    1. Cari baris header -> baris yang salah satu selnya (setelah di-split
       tab) persis sama dengan SHOPEE_KODE_HEADER_NAME ('No. Pesanan').
       Dicari dari header, bukan hardcode posisi kolom, karena urutan
       kolom di export Shopee bisa beda-beda tiap kali download.
    2. Dari baris header yang sama, sekalian cari index kolom
       SHOPEE_HARGA_HEADER_NAME ('Total Penghasilan' -> posisinya di
       kolom AG). Ini dipakai buat validasi harga: harga dari Excel
       dibanding harga yang didapat bot pas scan di aplikasi.
    3. Untuk tiap baris SETELAH header, split by tab, ambil isi kode di
       index kode, dan isi harga di index harga (kalau kolomnya ketemu).
       Baris yang kodenya kosong (mis. pesanan batal/belum ada kode)
       otomatis di-skip karena gak ada yang mau dicari.

    Return (None, None) kalau baris header 'No. Pesanan' gak ketemu sama
    sekali (berarti bukan format yang diharapkan) -> caller bisa kasih
    pesan error yang jelas ke user, bukan diam-diam salah parse.

    Kalau kode ketemu tapi kolom harga ('Total Penghasilan') gak ketemu,
    tetap return kodenya, cuma harga_map-nya bakal kosong -> validasi
    harga otomatis di-skip (bukan bikin program berhenti).
    """
    lines = raw_text.splitlines()

    header_row_idx = None
    kode_col_idx = None
    harga_col_idx = None
    for i, line in enumerate(lines):
        cols = [c.strip() for c in line.split("\t")]
        if SHOPEE_KODE_HEADER_NAME in cols:
            header_row_idx = i
            kode_col_idx = cols.index(SHOPEE_KODE_HEADER_NAME)
            if SHOPEE_HARGA_HEADER_NAME in cols:
                harga_col_idx = cols.index(SHOPEE_HARGA_HEADER_NAME)
            break

    if header_row_idx is None:
        return None, None

    kodes = []
    harga_map = {}
    for line in lines[header_row_idx + 1:]:
        if not line.strip():
            continue
        cols = line.split("\t")
        if len(cols) > kode_col_idx:
            kode = cols[kode_col_idx].strip()
            if kode:
                kodes.append(kode)
                if harga_col_idx is not None and len(cols) > harga_col_idx:
                    harga_map[kode] = cols[harga_col_idx].strip()

    return kodes, harga_map


# nomor -> harga versi Excel (dari kolom AG / 'Total Penghasilan'). Cuma
# keisi kalau mode skala besar & kolomnya ketemu. Kosong = gak ada data
# pembanding -> validasi harga otomatis "-" (di-skip) buat nomor itu.
harga_excel_map = {}

if mode_input == "2":
    kodes_hasil_extract, harga_map_hasil_extract = extract_kode_dan_harga_dari_excel_shopee(raw)

    if kodes_hasil_extract is None:
        print(f"\n❌ Kolom '{SHOPEE_KODE_HEADER_NAME}' tidak ditemukan di data yang di-paste.")
        print("   Pastikan kamu copy termasuk baris header tabel Excel-nya (bukan cuma datanya doang).")
        sys.exit()

    if not kodes_hasil_extract:
        print(f"\n❌ Kolom '{SHOPEE_KODE_HEADER_NAME}' ketemu, tapi semua barisnya kosong / gak ada kodenya.")
        sys.exit()

    print(f"\n✔ Ketemu kolom '{SHOPEE_KODE_HEADER_NAME}', berhasil ambil {len(kodes_hasil_extract)} kode pesanan dari data Excel.")

    if harga_map_hasil_extract:
        print(f"✔ Ketemu kolom '{SHOPEE_HARGA_HEADER_NAME}' (AG) -> harga dari Excel akan divalidasi otomatis vs harga hasil scan aplikasi.")
        harga_excel_map = harga_map_hasil_extract
    else:
        print(f"⚠ Kolom '{SHOPEE_HARGA_HEADER_NAME}' gak ketemu -> validasi harga di-skip, cuma kode pesanan aja yang dipakai buat scan.")

    orders_raw = kodes_hasil_extract
else:
    orders_raw = []
    for line in raw.splitlines():
        line = line.strip()
        if line:
            orders_raw.append(line)

# =============================
# FILTER DUPLIKAT
# =============================
seen_count = {}
for o in orders_raw:
    seen_count[o] = seen_count.get(o, 0) + 1

duplikat = {k: v for k, v in seen_count.items() if v > 1}

orders = list(dict.fromkeys(orders_raw))  # hilangkan duplikat, urutan tetap

if duplikat:
    print(f"\n⚠ Ditemukan {len(duplikat)} nomor yang dobel di data input:")
    for nomor, jumlah in duplikat.items():
        print(f"  - {nomor}  (muncul {jumlah}x)")
    print("-> Hanya akan discan SEKALI per nomor.")
else:
    print("\n✔ Tidak ada nomor dobel di data input.")

# skip yang sudah pernah discan dari checkpoint
orders = [o for o in orders if o not in sudah_scan]

print(f"\nTotal nomor unik tersisa untuk discan : {len(orders)}")

if not orders:
    print("Semua nomor sudah pernah discan sebelumnya.")
else:
    if input("\nMulai Scan? (y/n): ").lower() != "y":
        sys.exit()

    # =============================
    # STEP 2
    # =============================
    print("\nSTEP 2")
    print("Klik SEARCH NOMOR")
    print("Cursor harus berkedip")
    input("\nENTER jika siap...")

    for i in range(5, 0, -1):
        print(f"Mulai dalam {i}...", end="\r")
        time.sleep(1)

    print("\n🚀 MULAI\n")

    # =============================
    # HELPER
    # =============================
    def to_number(harga_str):
        """
        Ubah teks harga jadi integer buat dibanding/dijumlah.

        FIX BUG: versi lama cuma buang SEMUA karakter yang bukan digit
        (''.join(c for c in s if c.isdigit())). Ini salah kalau formatnya
        ada titik/koma desimal, misalnya harga dari grid aplikasi yang
        formatnya "70,750.00" (koma = pemisah ribuan, titik = desimal)
        -> lama: kebaca "7075000" (2 nol dari '.00' ikut ke-anggap
        ribuan, padahal itu desimal yang harusnya dibuang). Akibatnya
        pas dibanding ke harga Excel yang polos "70750", dikira SELISIH
        padahal nilainya SAMA PERSIS.

        Sekarang: deteksi mana yang pemisah ribuan vs desimal.
        - Kalau ada titik DAN koma -> yang paling kanan = desimal.
        - Kalau cuma salah satu (titik ATAU koma) muncul SEKALI dan
          persis diikuti 2 digit di belakang -> dianggap desimal (mis.
          "70750.00" atau "70750,00"), sisanya dibuang/dibulatkan.
        - Selain itu -> dianggap pemisah ribuan, dibuang semua.
        """
        s = str(harga_str).strip()
        if not s:
            return 0

        negative = s.startswith("-") or s.startswith("(")
        s = re.sub(r"[^0-9.,]", "", s)
        if not s:
            return 0

        if "," in s and "." in s:
            if s.rfind(",") > s.rfind("."):
                s = s.replace(".", "").replace(",", ".")
            else:
                s = s.replace(",", "")
        elif "," in s:
            head, _, tail = s.rpartition(",")
            if "," not in head and len(tail) == 2:
                s = head + "." + tail
            else:
                s = s.replace(",", "")
        elif "." in s:
            head, _, tail = s.rpartition(".")
            if "." not in head and len(tail) == 2:
                s = head + "." + tail
            else:
                s = s.replace(".", "")

        try:
            value = float(s)
        except ValueError:
            value = 0.0

        hasil = int(round(value))
        return -hasil if negative else hasil

    def cek_validasi_harga(nomor, harga_aplikasi):
        """
        Bandingin harga hasil scan aplikasi (kolom ke-10 dari kiri) vs
        harga dari Excel (kolom AG / 'Total Penghasilan'), KALAU data
        Excel-nya ada (mode skala besar & kolomnya ketemu). Kalau gak
        ada data pembanding (mode skala kecil, atau nomor gak ada di
        Excel), hasilnya "-" -> bukan error, cuma gak ada yang dicek.
        """
        harga_excel = harga_excel_map.get(nomor)
        if not harga_excel:
            return "-", ""
        if to_number(harga_excel) == to_number(harga_aplikasi):
            return "OK", harga_excel
        return "SELISIH", harga_excel

    def find_data_row(expected):
        """
        Setelah search + Enter + down, baca baris data dan cari yang
        kolom 'Memo'-nya sama dengan kode yang dicari.

        FIX lama (masih dipertahankan): kode yang dicari itu isi kolom
        'Memo' (dicari by nama kolom, bukan hardcode index), dan header
        doang (1 baris ke-copy) BUKAN berarti datanya gak ada -- itu
        biasanya grid hasil search belum ke-load.

        FIX BARU (biar NOT FOUND beneran NOT FOUND, bukan gara-gara
        kecepatan): hasil baca yang "mencurigakan" gak langsung dinyatakan
        not found. Ada 2 fase:
          1. Retry ringan untuk SEMUA baca yang mencurigakan:
             - clipboard KOSONG  -> tunggu sebentar lalu baca ulang
               (jangan buru-buru nge-down, takut fokus malah pindah).
             - cuma HEADER (1 baris) -> nge-down satu langkah ke data,
               lalu baca ulang. Maksimal HEADER_RETRY kali.
             - data ke-copy (>=2 baris) tapi memo gak cocok -> bisa jadi
               grid masih nampilin hasil search KODE SEBELUMNYA (race),
               langsung berhenti di fase 1 karena nge-down gak bakal
               nolong; biar fase 2 yang mutusin.
          2. Kalau masih mencurigakan, kode di-SEARCH ULANG dari awal
             (balik ke kotak search, ketik ulang, enter, down, baca).
             Cuma kalau setelah search ulang pun gak ketemu -> baru
             dianggap NOT FOUND beneran. Baris yang sehat tetap cepat
             (ketemu di baca pertama tanpa nambah waktu).

        FIX TERBARU (gabung row duplikat): 1 kode pesanan (kolom Memo)
        kadang muncul di >1 baris grid (split faktur). Sebelumnya yang
        dipakai cuma baris PERTAMA yang cocok terus langsung berhenti.
        Sekarang baris lain yang Memo-nya MASIH sama ikut dikumpulin
        (lihat kumpulin_semua_baris_memo), dan caller yang mutusin baris
        mana yang 'asli' (lihat pilih_baris_primary). Kode yang cuma 1
        baris TIDAK ditambah delay -- kumpulin cuma nambah baca kalau
        emang ada indikasi baris duplikat.

        Return: (rows, debug_info, extra_down)
          - rows       : list SEMUA baris grid yang kolom Memo-nya ==
                         expected (bisa lebih dari 1 kalau split faktur),
                         atau None kalau NOT FOUND
          - debug_info : alasan gagal (cuma kepake pas NOT FOUND)
          - extra_down : jumlah 'down' ekstra yang ditekan pas ngumpulin
                         baris duplikat. Caller WAJIB balikin cursor ke
                         search box dengan nekan 'up' 1 + extra_down kali
                         (karena baris duplikat 'down'-nya nambah).
        """
        def baca_clipboard():
            pyperclip.copy("")
            time.sleep(0.05)
            pyautogui.hotkey("ctrl", "c")

            start = time.time()
            text = ""
            while time.time() - start < 0.3:
                text = pyperclip.paste().strip()
                if text:
                    break
                time.sleep(0.03)

            lines = [x.strip() for x in text.splitlines() if x.strip()] if text else []
            return lines, text

        def cari_baris_memo(lines):
            if len(lines) < 2:
                return None
            # Cari index kolom 'Memo' dari header (baris pertama) biar gak
            # hardcode posisi kalau urutan kolom beda-beda.
            header_cols = lines[0].split('\t')
            try:
                memo_idx = header_cols.index('Memo')
            except ValueError:
                memo_idx = 4  # fallback posisi default kalau nama kolom beda

            for line in lines[1:]:
                cols = line.split('\t')
                if len(cols) > memo_idx and cols[memo_idx].strip() == expected:
                    if len(cols) >= 18:
                        return cols
            return None

        def fase_baca():
            """Baca clipboard + retry ringan. Return (cols, lines, text);
            cols != None berarti baris yang dicari KETEMU."""
            for attempt in range(HEADER_RETRY + 1):
                lines, text = baca_clipboard()
                cols = cari_baris_memo(lines)
                if cols is not None:
                    return cols, lines, text

                if len(lines) >= 2:
                    # Data ke-copy tapi memo gak cocok. Nge-down gak bakal
                    # mengubah isi grid -> hentikan fase 1, serahkan ke
                    # fase 2 (re-search) buat mutusin beneran ada/gak ada.
                    return None, lines, text

                if attempt < HEADER_RETRY:
                    if not lines:
                        # Clipboard kosong = grid hasil search belum
                        # ke-load. Tunggu dulu biar ke-load, baca ulang
                        # (tanpa nge-down, takut fokus kepindah).
                        metrik["retry"] += 1
                        if FOTO_AKTIF and metrik["foto_retry"] < FOTO_RETRY_BATAS:
                            metrik["foto_retry"] += 1
                            ambil_screenshot(expected, "RETRY", "clipboard_kosong")
                        time.sleep(0.15)
                        continue
                    # Cuma header ke-copy -> masuk satu langkah ke data.
                    metrik["retry"] += 1
                    if FOTO_AKTIF and metrik["foto_retry"] < FOTO_RETRY_BATAS:
                        metrik["foto_retry"] += 1
                        ambil_screenshot(expected, "RETRY", "header_doang")
                    pyautogui.press("down")
                    time.sleep(HEADER_RETRY_DELAY)

            return None, lines, text

        def kumpulin_semua_baris_memo(expected, lines_awal):
            """
            NEW — gabung row duplikat. Baris pertama yang cocok udah
            ketemu di `lines_awal`, sekarang kumpulin SEMUA baris yang
            kolom Memo-nya MASIH sama dengan expected.

            Strategi biar kode yang cuma punya 1 row TETAP SECEPAT DULU
            (gak nambah baca clipboard / delay ekstra):
              1. Dari copy yang BARUSAN (yang bikin ketemu), langsung
                 kumpulin SEMUA baris yang Memo-nya cocok dalam satu copy
                 itu (gratis, gak nambah down).
              2. Kalau baris match TERAKHIR bukan baris data TERAKHIR di
                 copy (masih ada baris lain di bawahnya yang BUKAN Memo
                 sama) -> grup kode ini udah berakhir dalam view, LANGSUNG
                 berhenti. Ini kasus normal (match di baris atas, di
                 bawahnya hasil search lain), jadi 0 down tambahan.
              3. Baru turun (down + copy ulang) KALAU baris match
                 terakhir nyentuh baris data terakhir di copy -- artinya
                 mungkin masih ada baris Memo sama di bawahnya yang belum
                 ke-visible. Terus turun sampai copy berikutnya gak nambah
                 baris baru (udah lewat grup) / clipboard kosong (mentok
                 akhir tabel) / mentok MAX_ROW_DUPLIKAT.

            Return: (rows, extra_down)
              - rows       : list SEMUA baris (list kolom) yang Memo-nya
                             == expected
              - extra_down : jumlah 'down' ekstra yang ditekan. Caller
                             WAJIB nekan 'up' 1 + extra_down kali.
            """
            rows = []
            seen = set()

            def memo_idx_dari(header_line):
                try:
                    return header_line.split('\t').index('Memo')
                except ValueError:
                    return 4  # fallback posisi default kalau nama kolom beda

            def proses_baca(lines):
                """Tambah baris yang Memo-nya cocok ke `rows` (dedupe by
                baris mentah -- 2 baris fisik yang isinya sama persis
                tetap dihitung keduanya). Return True kalau baris match
                TERAKHIR nempel di baris data terakhir blok ini (artinya
                mungkin masih ada baris Memo sama di bawah yang belum
                ke-visible)."""
                if len(lines) < 2:
                    return False
                mi = memo_idx_dari(lines[0])
                blok = lines[1:]
                lanjut = False
                for i, raw_line in enumerate(blok):
                    if raw_line in seen:
                        continue
                    cols = raw_line.split('\t')
                    if len(cols) > mi and cols[mi].strip() == expected and len(cols) >= 18:
                        seen.add(raw_line)
                        rows.append(cols)
                        if i == len(blok) - 1:
                            lanjut = True
                return lanjut

            extra_down = 0
            lanjut = proses_baca(lines_awal)
            while lanjut and len(rows) < MAX_ROW_DUPLIKAT:
                pyautogui.press("down")
                time.sleep(DELAY_AFTER_DOWN)
                extra_down += 1
                new_lines, _ = baca_clipboard()
                lanjut = proses_baca(new_lines)

            return rows, extra_down

        # Fase 1: baca hasil search yang barusan.
        cols, lines, text = fase_baca()
        if cols is not None:
            if GABUNG_ROW_DUPLIKAT:
                rows, extra_down = kumpulin_semua_baris_memo(expected, lines)
            else:
                rows, extra_down = [cols], 0
            return rows, None, extra_down

        if RE_SEARCH_KONFIRMASI:
            # Fase 2: konfirmasi dengan search ulang dari nol. Ini yang
            # bikin NOT FOUND akurat: kode cuma dianggap gak ada kalau
            # setelah diketik & di-search ulang pun tetap gak ketemu.
            # Observability: event ini difoto + dihitung di metrik,
            # soalnya ini tanda pasti grid sempat nampilin hasil yang
            # mencurigakan (kemungkinan besar race kecepatan).
            metrik["research"] += 1
            if FOTO_AKTIF:
                ambil_screenshot(expected, "RE_SEARCH")
            pyautogui.press("up")   # balik ke kotak search (sama seperti yang
                                    # dilakukan caller setelah satu baris selesai)
            time.sleep(DELAY_AFTER_UP)
            pyautogui.hotkey("ctrl", "a")
            pyperclip.copy(expected)
            pyautogui.hotkey("ctrl", "v")
            pyautogui.press("enter")
            pyautogui.press("down")
            tunggu_grid_respon(timeout=POLL_GRID_TIMEOUT)

            cols, lines2, text2 = fase_baca()
            if cols is not None:
                if GABUNG_ROW_DUPLIKAT:
                    rows, extra_down = kumpulin_semua_baris_memo(expected, lines2)
                else:
                    rows, extra_down = [cols], 0
                return rows, None, extra_down
            lines, text = lines2, text2

        return None, {"reason": f"kode '{expected}' tidak ketemu: {len(lines)} baris ke-copy, memo gak cocok setelah retry{'+ 1x re-search' if RE_SEARCH_KONFIRMASI else ''}", "raw": text}, 0

    def pilih_baris_primary(rows, nomor):
        """
        NEW — nentuin baris 'asli' kalau 1 kode pesanan (kolom Memo)
        muncul di >1 baris grid hasil scan.

        Latar belakang: kode yang sama bisa muncul di beberapa baris
        karena order di-invoice jadi 2 faktur (split faktur) -- No.Faktur
        beda, tapi Customer & Total SAMA PERSIS, dan cuma Status Bayar
        yang bisa beda (satu Sudah, satu Belum). Kalau kita asal ambil
        baris pertama doang, pas baris pertama yang kebaca 'Belum'
        padahal ada baris lain (Memo sama, harga sama) yang 'Sudah',
        hasil scan salah nyatet Belum.

        REVISI 2026-08-04 — harga Excel sekarang jadi ACUAN UTAMA validasi
        (bukan cuma "bonus konfirmasi"). Urutan prioritas:
          1. 1 baris -> baris itu dipakai (kasus normal, mayoritas data).
          2. >1 baris DAN ADA data harga Excel buat nomor ini (mode
             skala besar):
             a. cari SEMUA baris yang harga aplikasinya PERSIS SAMA
                dengan to_number(harga_excel) -> rows_cocok_excel.
             b. kalau gak ada satupun yang cocok -> JANGAN digabung
                otomatis. Pakai rows[0], REVISI "CEK MANUAL - {n} ROW,
                TIDAK ADA YANG COCOK HARGA EXCEL".
             c. kalau ada 1+ yang cocok -> cari yang
                Sudah/paid/lunas HANYA di antara rows_cocok_excel (yang
                udah tervalidasi cocok harga Excel). Ketemu -> jadi
                primary (status final = Sudah). Gak ketemu -> baris
                pertama rows_cocok_excel (status ikut baris itu,
                biasanya Belum).
             d. KALAU len(rows_cocok_excel) > 1 (LEBIH DARI 1 baris yang
                tervalidasi cocok harga Excel) -> ini kasus mencurigakan
                (data duplikasi tervalidasi) yang HARUS di-flag jelas:
                catatan "⚠ TERDETEKSI DATA DUPLIKASI (N row tervalidasi
                sama harga Excel)" ditambahkan ke REVISI (digabung " | "
                sama catatan DOUBLE FAKTUR) + ALERT di CMD selalu
                keliatan (gak digembok SHOW_DETAIL_LOG).
          3. >1 baris TAPI gak ada data Excel (mode skala kecil / nomor
             gak ada di harga_excel_map) -> fallback validasi antar
             baris aplikasi doang:
             - harga semua baris sama -> cari yang Sudah, gabung jadi
               Sudah (kalau semua Belum, pakai baris pertama), catatan
               "DOUBLE FAKTUR ({n} row, digabung - harga konsisten,
               TANPA validasi Excel)".
             - harga beda-beda antar baris -> "CEK MANUAL - {n} ROW
               BEDA HARGA (gak ada data Excel buat validasi)".

        Return: (primary_row, jumlah_duplikat_row, catatan_revisi,
                 jumlah_cocok_excel)
          - primary_row         : baris yang dipakai sebagai data final
          - jumlah_duplikat_row : jumlah baris yang Memo-nya sama (>=1)
          - catatan_revisi      : teks buat kolom REVISI di Excel, ""
                                  kalau normal 1 baris
          - jumlah_cocok_excel  : berapa baris di antara duplikat yang
                                  harganya PERSIS cocok sama harga Excel
                                  (0 = gak ada data Excel / gak ada yang
                                  cocok). Kepake buat teks 🚨 di tabel
                                  ringkasan & statistik duplikasi.
        """
        n = len(rows)
        if n == 1:
            return rows[0], 1, "", 0

        def harga_row(r):
            if len(r) > PRICE_COLUMN_INDEX:
                return to_number(r[PRICE_COLUMN_INDEX])
            return 0

        def status_sudah(r):
            return len(r) > 17 and r[17].strip().lower().replace(" ", "") in ("sudah", "paid", "lunas")

        harga_excel = harga_excel_map.get(nomor, "")
        ada_excel = bool(harga_excel)

        if ada_excel:
            # KASUS UTAMA: harga Excel jadi acuan utama. Baris yang bener
            # = baris yang harganya PERSIS cocok sama harga Excel.
            rows_cocok_excel = [r for r in rows if harga_row(r) == to_number(harga_excel)]
            jumlah_cocok = len(rows_cocok_excel)

            if jumlah_cocok == 0:
                # Gak ada satupun yang cocok Excel -> jangan asal gabung,
                # bisa jadi ini emang pesanan beda. Suruh cek manual.
                return rows[0], n, f"CEK MANUAL - {n} ROW, TIDAK ADA YANG COCOK HARGA EXCEL", 0

            # Cari yang Sudah/paid/lunas HANYA di antara yang cocok Excel
            # (BUKAN di semua rows -- baris yang harga aplikasinya beda
            # dari Excel gak boleh nyolong status).
            primary_row = None
            for r in rows_cocok_excel:
                if status_sudah(r):
                    primary_row = r
                    break
            if primary_row is None:
                primary_row = rows_cocok_excel[0]

            catatan_parts = [f"DOUBLE FAKTUR ({n} row, digabung)"]
            if jumlah_cocok > 1:
                # NOTIFIKASI DUPLIKASI: >1 baris tervalidasi cocok harga
                # Excel -> kasus mencurigakan, flag jelas di REVISI + alert
                # CMD yang SELALU keliatan (ini sinyal penting buat user,
                # bukan detail log biasa).
                catatan_parts.append(f"⚠ TERDETEKSI DATA DUPLIKASI ({jumlah_cocok} row tervalidasi sama harga Excel)")
                print(f"\n⚠️  TERDETEKSI DATA DUPLIKASI: {nomor} -> {jumlah_cocok} row tervalidasi cocok harga Excel (Rp{harga_excel})")
            return primary_row, n, " | ".join(catatan_parts), jumlah_cocok

        # FALLBACK TANPA Excel (mode skala kecil): validasi cuma bisa
        # antar baris aplikasi doang (konsisten harga sama satu sama lain).
        semua_harga_sama = len({harga_row(r) for r in rows}) == 1
        if semua_harga_sama:
            for r in rows:
                if status_sudah(r):
                    return r, n, f"DOUBLE FAKTUR ({n} row, digabung - harga konsisten, TANPA validasi Excel)", 0
            # Semuanya Belum -> baris pertama apa adanya, tetap dicatat
            # sebagai double faktur (harga konsisten, cuma beda status).
            return rows[0], n, f"DOUBLE FAKTUR ({n} row, digabung - harga konsisten, TANPA validasi Excel)", 0
        # Beda harga antar baris -> jangan digabung otomatis, cek manual.
        return rows[0], n, f"CEK MANUAL - {n} ROW BEDA HARGA (gak ada data Excel buat validasi)", 0

    def save_checkpoint():
        wb = Workbook()
        ws = wb.active
        ws.title = "Checkpoint"
        ws.append(["Nomor", "NoFaktur", "Salesman", "Customer", "Tanggal", "Memo", "Harga", "StatusRetur", "Status", "ValidasiHarga", "HargaExcel", "JumlahDuplikatRow", "CatatanMerge", "JumlahCocokExcel"])
        for x in sudah:
            ws.append([x["nomor"], x["no_faktur"], x["salesman"], x["customer"], x["tanggal"], x["memo"], x["harga"], x["retur"], "Sudah", x.get("validasi", "-"), x.get("harga_excel", ""), x.get("jumlah_duplikat_row", 1), x.get("catatan_merge", ""), x.get("jumlah_cocok_excel", 0)])
        for x in belum:
            ws.append([x["nomor"], x["no_faktur"], x["salesman"], x["customer"], x["tanggal"], x["memo"], x["harga"], x["retur"], "Belum", x.get("validasi", "-"), x.get("harga_excel", ""), x.get("jumlah_duplikat_row", 1), x.get("catatan_merge", ""), x.get("jumlah_cocok_excel", 0)])
        for x in not_found:
            ws.append([x, "", "", "", "", "", "", "", "NotFound", "-", "", 1, "", 0])

        # FIX BUG: kalau checkpoint_scan.xlsx lagi kebuka/kekunci pas
        # autosave jalan di tengah scan (tiap CHECKPOINT_EVERY baris),
        # wb.save() bisa PermissionError dan bikin SELURUH SCAN CRASH di
        # tengah jalan. Sekarang: kalau gagal, cuma kasih warning dan
        # SKIP autosave kali ini -> scan tetap lanjut, checkpoint bakal
        # dicoba lagi otomatis di kelipatan baris berikutnya.
        try:
            wb.save(CHECKPOINT_FILE)
        except PermissionError:
            print(f"\n⚠ Gagal autosave '{CHECKPOINT_FILE}' (kemungkinan lagi kebuka di Excel) -> dilewati, scan tetap lanjut.")

    def tentukan_keterangan_status_revisi(kind, item):
        """
        Nentuin 3 kolom terakhir di template report (KETERANGAN, STATUS,
        REVISI) berdasarkan hasil scan. Urutan prioritas cek dari yang
        paling 'parah' dulu:
        1. Not found      -> gak ada datanya sama sekali di aplikasi
        2. Retur          -> ketemu, tapi kolom Retur ke-deteksi
        3. Beda Nilai     -> ketemu, tapi harga Excel vs Aplikasi beda,
                             ATAU 1 kode muncul di >1 baris dengan harga
                             BEDA (bukan split faktur, harus dicek manual)
        4. Belum bayar    -> ketemu, status bayar masih Belum
        5. Sudah, aman    -> ketemu, Sudah bayar, gak ada masalah lain
                             (termasuk yang baris duplikatnya berhasil
                             digabung jadi Sudah -> tercatat di REVISI)
        """
        if kind == "not_found":
            return "TIDAK ADA FAKTUR", "CEK", ""

        if item.get("retur") == "Retur":
            return "RETUR", "CEK", "RETUR"

        # NEW: 1 kode (Memo) muncul di >1 baris tapi harga beda antar
        # baris -> jangan digabung otomatis, tandai biar dicek manual.
        catatan = item.get("catatan_merge", "")
        if catatan.startswith("CEK MANUAL"):
            return "BEDA NILAI", "CEK", catatan

        if item.get("validasi") == "SELISIH":
            return "BEDA NILAI", "CEK", ""

        if kind == "belum":
            return "BELUM", "CEK", catatan

        # NEW: duplikat yang berhasil digabung jadi Sudah -> catat di REVISI.
        if catatan:
            return "SUDAH", "OK", catatan

        return "SUDAH", "OK", ""

    def export_final():
        wb = Workbook()

        ws = wb.active
        ws.title = "Hasil"
        ws.append(["SALES", "TGL", "KODE PESANAN", "NO. FAKTUR", "KETERANGAN", "STATUS", "REVISI"])

        # Warna per KETERANGAN, niru style "Good/Bad/Neutral" bawaan
        # Excel biar kelihatan familiar. Fill = warna latar sel, Font =
        # warna teksnya. Gampang di-scan sekilas mana yang aman (hijau)
        # vs yang perlu dicek manual (warna lain).
        WARNA = {
            "SUDAH":             (PatternFill("solid", fgColor="C6EFCE"), Font(color="006100")),  # hijau
            "RETUR":             (PatternFill("solid", fgColor="FCE4D6"), Font(color="C65911")),  # oranye
            "BEDA NILAI":        (PatternFill("solid", fgColor="FFC7CE"), Font(color="9C0006")),  # merah
            "BELUM":             (PatternFill("solid", fgColor="FFEB9C"), Font(color="9C6500")),  # kuning
            "TIDAK ADA FAKTUR":  (PatternFill("solid", fgColor="D9D9D9"), Font(color="595959")),  # abu-abu
        }

        # Urutan penulisan di Excel = urutan asli hasil_urut, yaitu
        # persis urutan kode pas kamu paste/scan (TIDAK di-sort ulang).
        # Tanpa blank row pemisah, biar tabel padat/rapat (sebelumnya blank
        # row muncul tiap SALES berubah, dan baris TIDAK ADA FAKTUR yang
        # SALES-nya '-' bikin jarak bolak-balik di tengah-tengah toko yang
        # sama).
        kind_map = {"Sudah": "sudah", "Belum": "belum", "Not Found": "not_found"}

        for r in hasil_urut:
            kind = kind_map.get(r["status"], "belum")
            keterangan, status_txt, revisi = tentukan_keterangan_status_revisi(kind, r)

            sales = r.get("customer") or "-"
            tgl = r.get("tanggal") or ""
            kode = r["nomor"]
            no_faktur = r.get("no_faktur") or ""
            if no_faktur == "-":
                no_faktur = ""

            ws.append([sales, tgl, kode, no_faktur, keterangan, status_txt, revisi])

            # warnai baris yang baru ditulis (kolom A sampai G)
            fill, font = WARNA.get(keterangan, (None, None))
            if fill is not None:
                baris_ini = ws.max_row
                for col in range(1, 8):
                    cell = ws.cell(row=baris_ini, column=col)
                    cell.fill = fill
                    cell.font = font

        last_row = ws.max_row
        ws.auto_filter.ref = f"A1:G{last_row}"
        ws.freeze_panes = "A2"  # header tetap kelihatan saat scroll

        # sheet khusus laporan duplikat dari data input
        if duplikat:
            ws2 = wb.create_sheet("Duplikat")
            ws2.append(["Nomor", "Jumlah Muncul"])
            for nomor, jumlah in duplikat.items():
                ws2.append([nomor, jumlah])
            ws2.auto_filter.ref = f"A1:B{ws2.max_row}"

        # sheet Rekap Total Harga
        ws3 = wb.create_sheet("Rekap Harga")
        all_items = sudah + belum
        rekap_total_aplikasi = sum(to_number(x["harga"]) for x in all_items)
        rekap_total_excel = sum(to_number(x.get("harga_excel", "")) for x in all_items if x.get("harga_excel"))
        rekap_total_ok = sum(to_number(x["harga"]) for x in all_items if x.get("validasi") == "OK")
        rekap_total_selisih = sum(to_number(x["harga"]) for x in all_items if x.get("validasi") == "SELISIH")

        ws3.append(["REKAP TOTAL HARGA", ""])
        ws3.append(["", ""])
        ws3.append(["Kategori", "Total (Rp)"])
        ws3.append(["Total Harga di Aplikasi", rekap_total_aplikasi])
        ws3.append(["Total Harga di Excel", rekap_total_excel])
        ws3.append(["Total Harga Status OK", rekap_total_ok])
        ws3.append(["Total Harga Status SELISIH", rekap_total_selisih])
        ws3.append(["", ""])
        ws3.append(["Jumlah Data", ""])
        ws3.append(["Sudah Bayar", len(sudah)])
        ws3.append(["Belum Bayar", len(belum)])
        ws3.append(["Not Found", len(not_found)])
        ws3.append(["Status OK", sum(1 for x in all_items if x.get("validasi") == "OK")])
        ws3.append(["Status SELISIH", sum(1 for x in all_items if x.get("validasi") == "SELISIH")])
        ws3.append(["Double Faktur (duplikat row digabung)", sum(1 for x in all_items if x.get("jumlah_duplikat_row", 1) > 1)])
        ws3.append(["Duplikasi Tervalidasi (>1 row cocok harga Excel)", sum(1 for x in all_items if "TERDETEKSI DATA DUPLIKASI" in x.get("catatan_merge", ""))])

        # format header rekap
        ws3["A1"].font = Font(bold=True, size=14)
        ws3["A3"].font = Font(bold=True)
        ws3["B3"].font = Font(bold=True)
        ws3["A9"].font = Font(bold=True)
        for row in ws3.iter_rows(min_row=4, max_row=7, min_col=1, max_col=2):
            for cell in row:
                if cell.column == 2:
                    cell.number_format = '#,##0'
        for row in ws3.iter_rows(min_row=15, max_row=16, min_col=1, max_col=2):
            for cell in row:
                if cell.column == 2:
                    cell.number_format = '#,##0'
        ws3.column_dimensions["A"].width = 30
        ws3.column_dimensions["B"].width = 20

        # FIX BUG: wb.save() bisa gagal PermissionError kalau file
        # 'hasil_scan.xlsx' lagi KEBUKA di Excel (Excel ngunci file pas
        # dibuka), atau kalau folder-nya read-only. Sebelumnya ini bikin
        # program CRASH di baris terakhir -> padahal semua hasil scan
        # udah kepegang di memory, sayang banget kalau hilang gitu aja.
        # Sekarang: kalau nama utama gagal, coba nama alternatif
        # (hasil_scan_1.xlsx, hasil_scan_2.xlsx, dst) sampai berhasil.
        nama_file = "hasil_scan.xlsx"
        percobaan = 0
        while True:
            try:
                wb.save(nama_file)
                if percobaan > 0:
                    print(f"\n⚠ 'hasil_scan.xlsx' kayaknya lagi kebuka/kekunci -> hasil disimpan sebagai '{nama_file}' sebagai gantinya.")
                    print("  Tutup dulu file Excel yang lama kalau mau nama file balik ke 'hasil_scan.xlsx'.")
                return nama_file
            except PermissionError:
                percobaan += 1
                nama_file = f"hasil_scan_{percobaan}.xlsx"
                if percobaan > 20:
                    print("\n❌ Gagal nyimpen hasil_scan.xlsx berkali-kali (kemungkinan folder read-only atau ke-lock terus).")
                    print("   Tutup semua file 'hasil_scan*.xlsx' yang lagi kebuka, atau cek izin folder ini, lalu coba lagi.")
                    raise

    # =============================
    # NEW: CETAK TABEL RINGKASAN DI CMD
    # NOMOR FAKTUR | KODE PESANAN | STATUS BAYAR
    # =============================
    def teks_duplikat(x):
        """
        NEW — teks ringkas jumlah row duplikat buat tabel ringkasan &
        detail log. Cuma berisi kalau 1 kode (Memo) muncul di >1 baris
        grid (split faktur).

        Varian khusus 🚨: kalau ada notifikasi "TERDETEKSI DATA DUPLIKASI"
        (LEBIH DARI 1 baris yang tervalidasi cocok harga Excel), teksnya
        beda dari "digabung" biasa biar user langsung ngeh kasus yang
        lebih perlu diperhatiin.
        """
        n = x.get("jumlah_duplikat_row", 1)
        if n <= 1:
            return ""
        catatan = x.get("catatan_merge", "")
        if "TERDETEKSI DATA DUPLIKASI" in catatan:
            return f"🚨 {n}x row ({x.get('jumlah_cocok_excel', 0)}x tervalidasi Excel!)"
        if catatan.startswith("CEK MANUAL"):
            # "TIDAK ADA YANG COCOK HARGA EXCEL" atau "BEDA HARGA ..." ->
            # sama artinya: jangan digabung otomatis, perlu dicek manual.
            return f"⚠ {n}x row (cek manual)"
        if catatan:
            return f"⚠ {n}x row (digabung: {x['status']})"
        return f"⚠ {n}x row"

    def print_summary_table(data):
        if not data:
            return

        status_label = {
            "Sudah": "🟢 Sudah",
            "Belum": "🟡 Belum",
            "Not Found": "🔴 Not Found",
        }

        headers = ["NO", "NOMOR FAKTUR", "KODE PESANAN", "CUSTOMER", "SALESMAN", "STATUS BAYAR", "VALIDASI HARGA (App vs Excel)", "DUPLIKAT ROW"]
        rows = []
        for i, x in enumerate(data, 1):
            no_faktur = x.get("no_faktur") or "-"
            kode = x["memo"] if x["memo"] else "-"
            customer = x.get("customer") or "-"
            salesman = x.get("salesman") or "-"
            status_text = status_label.get(x["status"], x["status"])

            validasi_raw = x.get("validasi", "-")
            harga_app = x.get("harga") or "-"
            harga_excel = x.get("harga_excel") or "-"
            if validasi_raw == "-":
                validasi_text = "-"
            elif validasi_raw == "OK":
                validasi_text = f"OK ({harga_app} = {harga_excel})"
            else:
                validasi_text = f"⚠ App:{harga_app} vs Excel:{harga_excel}"

            duplikat_text = teks_duplikat(x)

            rows.append([str(i), str(no_faktur), str(kode), str(customer), str(salesman), status_text, validasi_text, duplikat_text])

        col_widths = [
            max(len(headers[idx]), max((len(r[idx]) for r in rows), default=0))
            for idx in range(len(headers))
        ]

        def line(ch='-'):
            return "+" + "+".join(ch * (w + 2) for w in col_widths) + "+"

        def fmt_row(r):
            return "| " + " | ".join(cell.ljust(w) for cell, w in zip(r, col_widths)) + " |"

        print("\n" + "=" * 60)
        print("TABEL RINGKASAN HASIL SCAN")
        print("=" * 60)
        print(line())
        print(fmt_row(headers))
        print(line('='))
        for r in rows:
            print(fmt_row(r))
        print(line())

    # =============================
    # SCAN
    # =============================
    start_time = time.time()
    debug_notfound_shown = 0

    # OBSERVABILITY — metrik run INI (yang diproses sejak resume).
    # Counter `retry`/`research` ikut di-mutasi dari find_data_row /
    # fase_baca (nested function) lewat dict ini.
    metrik = {
        "diproses": 0,
        "sukses": 0,
        "not_found": 0,
        "retry": 0,
        "research": 0,
        "cek_manual": 0,
        "error": 0,
        "foto_retry": 0,  # internal: batas foto retry (bukan metrik tampil)
    }

    for index, nomor in enumerate(orders, start=1):
        spin = spinner[index % len(spinner)]
        elapsed = time.time() - start_time
        avg = elapsed / index if index else 0
        eta = avg * (len(orders) - index)
        print(
            f"{spin} [{index}/{len(orders)}] {nomor}  (avg {avg:.2f}s/baris, ETA {eta:.0f}s)",
            end="\r"
        )

        try:
            metrik["diproses"] += 1

            pyautogui.hotkey("ctrl", "a")
            pyperclip.copy(nomor)
            pyautogui.hotkey("ctrl", "v")
            pyautogui.press("enter")
            # Polling (bukan sleep statis): tunggu sampai aplikasi benar
            # respons (clipboard kebaca) sebelum lanjut, timeout di atur
            # POLL_GRID_TIMEOUT.
            tunggu_grid_respon(timeout=POLL_GRID_TIMEOUT)

            pyautogui.press("down")
            tunggu_grid_respon(timeout=POLL_GRID_TIMEOUT)

            rows, debug_info, extra_down = find_data_row(nomor)

            if rows is not None:
                metrik["sukses"] += 1

                # NEW: kalau 1 kode (Memo) muncul di >1 baris (split faktur),
                # tentukan baris 'asli' + jumlah baris duplikat + catatan buat
                # kolom REVISI (kalau berhasil digabung jadi Sudah / beda harga).
                # Return ke-4 = jumlah baris yang cocok harga Excel (buat teks
                # 🚨 duplikasi tervalidasi di tabel ringkasan).
                row, jumlah_duplikat_row, catatan_merge, jumlah_cocok_excel = pilih_baris_primary(rows, nomor)

                if catatan_merge.startswith("CEK MANUAL"):
                    metrik["cek_manual"] += 1

                customer = row[8].strip()
                memo = row[4].strip()
                no_faktur = row[0].strip()   # NEW: nomor faktur ASLI (kolom 'Nomor'), beda sama kode yang dicari
                status = row[17].strip().lower().replace(" ", "")

                if len(row) > SALESMAN_COLUMN_INDEX:
                    salesman = row[SALESMAN_COLUMN_INDEX].strip()
                else:
                    salesman = ""

                if len(row) > TANGGAL_COLUMN_INDEX:
                    tanggal = row[TANGGAL_COLUMN_INDEX].strip()
                else:
                    tanggal = ""

                if len(row) > PRICE_COLUMN_INDEX:
                    harga = row[PRICE_COLUMN_INDEX].strip()
                else:
                    harga = ""

                if len(row) > RETUR_COLUMN_INDEX:
                    retur = row[RETUR_COLUMN_INDEX].strip()
                else:
                    retur = ""

                # deteksi retur: kolom retur terisi DAN nilainya sama dengan harga
                if retur and to_number(retur) == to_number(harga) and to_number(harga) != 0:
                    status_retur = "Retur"
                else:
                    status_retur = "Berhasil"

                validasi_harga, harga_excel = cek_validasi_harga(nomor, harga)

                if status in ("sudah", "paid", "lunas"):
                    item_sudah = {"nomor": nomor, "no_faktur": no_faktur, "salesman": salesman, "customer": customer, "tanggal": tanggal, "memo": memo, "harga": harga, "retur": status_retur, "validasi": validasi_harga, "harga_excel": harga_excel, "jumlah_duplikat_row": jumlah_duplikat_row, "catatan_merge": catatan_merge, "jumlah_cocok_excel": jumlah_cocok_excel}
                    sudah.append(item_sudah)
                    hasil_urut.append({"nomor": nomor, "no_faktur": no_faktur, "salesman": salesman, "customer": customer, "tanggal": tanggal, "memo": memo, "status": "Sudah", "validasi": validasi_harga, "harga": harga, "harga_excel": harga_excel, "retur": status_retur, "jumlah_duplikat_row": jumlah_duplikat_row, "catatan_merge": catatan_merge, "jumlah_cocok_excel": jumlah_cocok_excel})
                    if SHOW_DETAIL_LOG:
                        tanda_validasi = f" | Validasi:{validasi_harga}" if validasi_harga != "-" else ""
                        tanda_dup = f" | {teks_duplikat(item_sudah)}" if jumlah_duplikat_row > 1 else ""
                        print(f"\n🟢 {no_faktur} | {tanggal} | {customer} | {salesman} | {memo} | Rp{harga} | SUDAH | {status_retur}{tanda_validasi}{tanda_dup}")
                else:
                    item_belum = {"nomor": nomor, "no_faktur": no_faktur, "salesman": salesman, "customer": customer, "tanggal": tanggal, "memo": memo, "harga": harga, "retur": status_retur, "validasi": validasi_harga, "harga_excel": harga_excel, "jumlah_duplikat_row": jumlah_duplikat_row, "catatan_merge": catatan_merge, "jumlah_cocok_excel": jumlah_cocok_excel}
                    belum.append(item_belum)
                    hasil_urut.append({"nomor": nomor, "no_faktur": no_faktur, "salesman": salesman, "customer": customer, "tanggal": tanggal, "memo": memo, "status": "Belum", "validasi": validasi_harga, "harga": harga, "harga_excel": harga_excel, "retur": status_retur, "jumlah_duplikat_row": jumlah_duplikat_row, "catatan_merge": catatan_merge, "jumlah_cocok_excel": jumlah_cocok_excel})
                    if SHOW_DETAIL_LOG:
                        tanda_validasi = f" | Validasi:{validasi_harga}" if validasi_harga != "-" else ""
                        tanda_dup = f" | {teks_duplikat(item_belum)}" if jumlah_duplikat_row > 1 else ""
                        print(f"\n🟡 {no_faktur} | {tanggal} | {customer} | {salesman} | {memo} | Rp{harga} | BELUM | {status_retur}{tanda_validasi}{tanda_dup}")

                # Balikin cursor ke search box. Dulu cuma 1 'up'; sekarang
                # 1 'up' + extra_down (yang ditekan pas ngumpulin baris
                # duplikat di find_data_row), biar posisi kembali persis ke
                # kotak search buat ctrl+a di kode berikutnya.
                for _ in range(1 + extra_down):
                    pyautogui.press("up")
                    time.sleep(DELAY_AFTER_UP)
            else:
                metrik["not_found"] += 1
                if FOTO_AKTIF:
                    ambil_screenshot(nomor, "NOT_FOUND", "final")

                # LANGSUNG lanjut ke kode berikutnya (retry ringan buat kasus
                # header udah dicoba di dalam find_data_row). 'up' tetap
                # ditekan biar cursor balik ke search box buat ctrl+a di kode
                # selanjutnya.
                pyautogui.press("up")
                not_found.append(nomor)
                hasil_urut.append({"nomor": nomor, "no_faktur": "-", "salesman": "-", "customer": "-", "tanggal": "", "memo": "-", "status": "Not Found", "validasi": "-", "harga": "", "harga_excel": "", "jumlah_duplikat_row": 1, "catatan_merge": "", "jumlah_cocok_excel": 0})

                if SHOW_DETAIL_LOG:
                    print(f"\n🔴 {nomor} | NOT FOUND")
                    if debug_notfound_shown < DEBUG_NOTFOUND_LIMIT:
                        debug_notfound_shown += 1
                        print(f"   [DEBUG] alasan gagal : {debug_info['reason']}")
                        print(f"   [DEBUG] raw clipboard: {debug_info['raw']!r}")

            if index % CHECKPOINT_EVERY == 0:
                save_checkpoint()
        except Exception as exc:
            # OBSERVABILITY: exception pas action pyautogui (termasuk
            # FailSafeException kalau mouse ke pojok layar). Foto keadaan
            # layar + simpan checkpoint, lalu STOP run biar user bisa
            # diagnosa & resume dari checkpoint (bukan lanjut scan dengan
            # cursor yang posisinya udah gak jelas).
            metrik["error"] += 1
            if FOTO_AKTIF:
                ambil_screenshot(nomor, "ERROR", type(exc).__name__)
            print(f"\n❌ [ERROR] di kode {nomor}: {type(exc).__name__}: {exc}")
            print("   Screenshot keadaan layar -> logs/screenshots/")
            try:
                save_checkpoint()
                print("   Checkpoint disimpan -> jalankan ulang & pilih 'y' buat lanjut dari sini.")
            except Exception:
                print("   ⚠ Gagal nyimpen checkpoint (file mungkin ke-lock).")
            sys.exit(1)

    print()
    runtime = round(time.time() - start_time, 2)

    save_checkpoint()  # simpan checkpoint terakhir juga

    # OBSERVABILITY — ringkasan metrik run ini ke CMD + logs/metrics.json
    # (durasi & rata-rata dihitung di sini, biar akurat ke detik).
    metrik["durasi"] = runtime
    metrik["rata_per_kode"] = round(runtime / max(metrik["diproses"], 1), 2)
    cetak_ringkasan("RINGKASAN METRIK (run ini, belum termasuk yang di-resume)", metrik)
    path_metrik = simpan_metrik("scan.py", metrik)
    if path_metrik:
        print(f"  -> metrik tersimpan: {path_metrik}")

    # =============================
    # OUTPUT
    # =============================
    print("=" * 60)
    print("HASIL SCAN")
    print("=" * 60)
    print()
    total_sudah = sum(to_number(x["harga"]) for x in sudah)
    total_belum = sum(to_number(x["harga"]) for x in belum)
    jumlah_retur = sum(1 for x in (sudah + belum) if x["retur"] == "Retur")
    jumlah_selisih = sum(1 for x in (sudah + belum) if x.get("validasi") == "SELISIH")
    jumlah_divalidasi = sum(1 for x in (sudah + belum) if x.get("validasi") in ("OK", "SELISIH"))
    jumlah_double = sum(1 for x in (sudah + belum) if x.get("jumlah_duplikat_row", 1) > 1)
    jumlah_double_beda_harga = sum(1 for x in (sudah + belum) if x.get("catatan_merge", "").startswith("CEK MANUAL"))
    jumlah_duplikasi_tervalidasi = sum(1 for x in (sudah + belum) if "TERDETEKSI DATA DUPLIKASI" in x.get("catatan_merge", ""))

    print(f"🟢 Sudah     : {len(sudah)}  (Rp{total_sudah:,})")
    print(f"🟡 Belum     : {len(belum)}  (Rp{total_belum:,})")
    print(f"🔴 Not Found : {len(not_found)}")
    print(f"↩️  Retur     : {jumlah_retur}")
    if jumlah_double:
        print(f"🔁 Double Faktur (baris duplikat digabung) : {jumlah_double}")
    if jumlah_double_beda_harga:
        print(f"❓ Double Faktur BEDA HARGA (perlu cek manual) : {jumlah_double_beda_harga}")
    if jumlah_duplikasi_tervalidasi:
        print(f"🚨 Duplikasi Tervalidasi (>1 row cocok harga Excel) : {jumlah_duplikasi_tervalidasi}")
    if jumlah_divalidasi > 0:
        print(f"⚠️  Selisih Harga (Excel vs Aplikasi) : {jumlah_selisih} dari {jumlah_divalidasi} yang divalidasi")
    print()
    total_aplikasi = total_sudah + total_belum
    total_excel = sum(to_number(x.get("harga_excel", "")) for x in (sudah + belum) if x.get("harga_excel"))
    total_ok = sum(to_number(x["harga"]) for x in (sudah + belum) if x.get("validasi") == "OK")

    print(f"💰 Total Harga Aplikasi   : Rp{total_aplikasi:,}")
    print(f"💰 Total Harga Excel      : Rp{total_excel:,}")
    print(f"💰 Total Harga Status OK  : Rp{total_ok:,}")
    print()
    print(f"⏱ Waktu      : {runtime} detik  (~{runtime/max(len(orders),1):.2f} detik/baris)")
    print()

    if SHOW_DETAIL_LOG and belum:
        print("=" * 40)
        print("BELUM BAYAR")
        print("=" * 40)
        for item in belum:
            print(f'{item["no_faktur"]} | {item["tanggal"]} | {item["customer"]} | {item["salesman"]} | {item["memo"]} | Rp{item["harga"]} | {item["retur"]}')
        print()

    if SHOW_DETAIL_LOG and not_found:
        print("=" * 40)
        print("NOT FOUND")
        print("=" * 40)
        for nomor in not_found:
            print(nomor)

    # =============================
    # TABEL RINGKASAN: NOMOR FAKTUR -> KODE PESANAN -> STATUS BAYAR
    # =============================
    print_summary_table(hasil_urut)

    # =============================
    # COPY SEMUA KODE/MEMO KE CLIPBOARD (nomor yang punya kode aja)
    # =============================
    all_items = sudah + belum
    memo_text = "\n".join(item["memo"] for item in all_items)
    pyperclip.copy(memo_text)

    print("\n📋 Semua kode pesanan (Memo) berhasil disalin ke clipboard.")

    nama_file_hasil = export_final()

    # hapus checkpoint kalau sudah selesai total & sukses
    if os.path.exists(CHECKPOINT_FILE):
        os.remove(CHECKPOINT_FILE)

    print()
    print(f"✔ {nama_file_hasil} berhasil dibuat")

input("\nENTER untuk keluar...")