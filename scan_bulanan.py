import time
import re
import pyautogui
import pyperclip
import sys
import os
from openpyxl import Workbook, load_workbook
from openpyxl.styles import PatternFill, Font

# =============================
# CONFIG — SILAKAN TUNING DI SINI
# =============================
# pyautogui secara default punya jeda 0.1 detik di SETIAP pemanggilan
# fungsi (hotkey/press/dll). Ini "pajak tersembunyi" yang paling besar
# pengaruhnya kalau scan ratusan baris. Diturunkan ke 0.02.
pyautogui.PAUSE = 0.02
pyautogui.FAILSAFE = True  # gerakkan mouse ke pojok layar buat emergency stop

DELAY_AFTER_ENTER = 0.5    # dinaikkan dari 0.35 - grid butuh waktu buat load hasil search
DELAY_AFTER_DOWN  = 0.20   # tadinya 0.40
DELAY_AFTER_UP    = 0.08   # tadinya 0.15

# NOTE: SEARCH_RETRY & COPY_RETRY (retry berlapis kalau data gak ketemu)
# udah DIHAPUS. Dulu kalau kode gak ada datanya, bot ngulang search
# sampai 3x, dan tiap ngulang nyoba copy sampai 4x dengan delay makin
# lama -> boros waktu banget buat kode yang emang gak ada. Sekarang:
# sekali search, sekali panah bawah, sekali cek -> kalau gak ada,
# LANGSUNG lanjut ke kode berikutnya, gak ada delay tambahan.

# =============================
# TAMPILAN LOG DI CMD
# =============================
# Default False -> cmd cuma nampilin progress bar + ringkasan akhir (bersih,
# gak berisik). Ganti ke True kapan aja kalau butuh lihat detail tiap baris
# (🟢/🟡/🔴 satu-satu) + info [DEBUG] pas ada yang NOT FOUND.
SHOW_DETAIL_LOG = False
DEBUG_NOTFOUND_LIMIT = 8   # batasi biar cmd gak kebanjiran pas SHOW_DETAIL_LOG aktif

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

# nama kolom harga/total di export Excel Shopee FORMAT LAMA (mode skala
# besar) -> ini yang secara posisi ada di kolom AG. Dicari dari NAMA
# header (bukan hardcode huruf kolom AG), soalnya kalau user cuma copy
# sebagian tabel (gak mulai dari kolom A), posisi huruf kolomnya bakal
# geser tapi nama headernya tetap sama.
SHOPEE_HARGA_HEADER_NAME = "Total Penghasilan"

# FORMAT BARU export Shopee (varian lain) TIDAK PUNYA kolom siap pakai
# kayak 'Total Penghasilan' di atas. Harganya harus DIHITUNG SENDIRI
# dengan jumlahin semua kolom dari 'Harga Produk' sampai 'PPh 22'
# (posisi kolom K s/d AL di export ini) -- itu semua komponen yang di
# format lama udah dijumlahin Shopee jadi 'Total Penghasilan'. Bot
# otomatis deteksi format mana yang lagi di-paste dari nama header yang
# ketemu, gak perlu pilih manual.
SHOPEE_SUM_HARGA_START_HEADER = "Harga Produk"   # kolom AWAL rentang (inklusif)
SHOPEE_SUM_HARGA_END_HEADER   = "PPh 22"         # kolom AKHIR rentang (inklusif)

CHECKPOINT_FILE = "checkpoint_scan_bulanan.xlsx"
CHECKPOINT_EVERY = 25   # autosave tiap 25 baris, biar aman kalau 800 baris macet di tengah

# Satu kode pesanan bisa berisi beberapa item -> di grid aplikasi tiap item
# tampil sebagai 1 baris (kolom Memo-nya sama). MAX_ITEM_PER_ORDER = batas
# amar baris yang dikumpulin per kode, biar gak muter terus kalau ada yang
# aneh (misal grid nyangkut / nge-scroll ke data lain).
MAX_ITEM_PER_ORDER = 15

spinner = ["|", "/", "-", "\\"]


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

    NOTE: dipindah ke level modul (bukan nested di dalam blok scan lagi)
    supaya bisa dipakai juga oleh extract_kode_dan_harga_dari_excel_shopee()
    -- fungsi itu butuh to_number() buat jumlahin kolom 'Harga Produk'
    s/d 'PPh 22' pas mode Excel format baru, dan itu jalan SEBELUM blok
    scan (jadi sebelum to_number versi lama yang nested kebentuk).
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


# =============================
# HEADER
# =============================
print("=" * 60)
print(" INVENTORY PAYMENT CHECKER - SCAN BULANAN (OPTIMIZED) ")
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
            # ValidasiHarga & HargaExcel) maupun format BARU (11 kolom)
            if len(row) >= 11:
                nomor, no_faktur, salesman, customer, tanggal, memo, harga, retur, status, validasi, harga_excel_ck = row
            else:
                nomor, no_faktur, salesman, customer, tanggal, memo, harga, retur, status = row
                validasi, harga_excel_ck = "-", ""

            sudah_scan.add(nomor)
            if status == "Sudah":
                sudah.append({"nomor": nomor, "no_faktur": no_faktur, "salesman": salesman, "customer": customer, "tanggal": tanggal, "memo": memo, "harga": harga, "retur": retur, "validasi": validasi, "harga_excel": harga_excel_ck})
                hasil_urut.append({"nomor": nomor, "no_faktur": no_faktur, "salesman": salesman, "customer": customer, "tanggal": tanggal, "memo": memo, "status": "Sudah", "validasi": validasi, "harga": harga, "harga_excel": harga_excel_ck, "retur": retur})
            elif status == "Belum":
                belum.append({"nomor": nomor, "no_faktur": no_faktur, "salesman": salesman, "customer": customer, "tanggal": tanggal, "memo": memo, "harga": harga, "retur": retur, "validasi": validasi, "harga_excel": harga_excel_ck})
                hasil_urut.append({"nomor": nomor, "no_faktur": no_faktur, "salesman": salesman, "customer": customer, "tanggal": tanggal, "memo": memo, "status": "Belum", "validasi": validasi, "harga": harga, "harga_excel": harga_excel_ck, "retur": retur})
            else:
                not_found.append(nomor)
                hasil_urut.append({"nomor": nomor, "no_faktur": "-", "salesman": "-", "customer": "-", "tanggal": "", "memo": "-", "status": "Not Found", "validasi": "-", "harga": "", "harga_excel": ""})
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
    2. Dari baris header yang sama, sekalian deteksi format harganya
       -- ADA 2 VARIAN export Shopee yang beda struktur:

       FORMAT LAMA: ada kolom siap pakai bernama SHOPEE_HARGA_HEADER_NAME
       ('Total Penghasilan', biasanya di kolom AG) -> harga tinggal
       diambil langsung dari kolom itu.

       FORMAT BARU: TIDAK PUNYA kolom 'Total Penghasilan'. Harganya harus
       DIHITUNG SENDIRI dengan jumlahin semua kolom dari
       SHOPEE_SUM_HARGA_START_HEADER ('Harga Produk') sampai
       SHOPEE_SUM_HARGA_END_HEADER ('PPh 22') -- itu semua komponen yang
       di format lama udah dijumlahin Shopee jadi 'Total Penghasilan'.

       Bot cek 'Total Penghasilan' dulu; kalau gak ketemu, baru cek
       pasangan 'Harga Produk' + 'PPh 22'. Jadi otomatis pilih format
       yang cocok, gak perlu tanya user tiap kali paste.
    3. Untuk tiap baris SETELAH header, split by tab, ambil isi kode di
       index kode, dan hitung/ambil harga sesuai format yang kedeteksi.
       Baris yang kodenya kosong (mis. pesanan batal/belum ada kode)
       otomatis di-skip karena gak ada yang mau dicari.

       SATU KODE PESANAN BISA MUNCUL DI BEBERAPA BARIS (mis. 1 pesanan
       berisi 3 item = 3 baris dengan 'No. Pesanan' yang sama). Karena
       semua baris itu = 1 orderan, harga_map-nya DIJUMLAH per kode
       (bukan ditimpa baris terakhir). Jadi harga_excel nanti = TOTAL
       harga semua item dalam 1 pesanan.

    Return (None, None) kalau baris header 'No. Pesanan' gak ketemu sama
    sekali (berarti bukan format yang diharapkan) -> caller bisa kasih
    pesan error yang jelas ke user, bukan diam-diam salah parse.

    Kalau kode ketemu tapi gak ada format harga yang kedeteksi (bukan
    format lama maupun baru), tetap return kodenya, cuma harga_map-nya
    bakal kosong -> validasi harga otomatis di-skip (bukan bikin program
    berhenti).
    """
    lines = raw_text.splitlines()

    header_row_idx = None
    kode_col_idx = None
    harga_col_idx = None        # format LAMA: 1 kolom siap pakai
    sum_start_idx = None        # format BARU: jumlah rentang kolom
    sum_end_idx = None
    format_terdeteksi = None    # cuma buat pesan info ke user

    for i, line in enumerate(lines):
        cols = [c.strip() for c in line.split("\t")]
        if SHOPEE_KODE_HEADER_NAME in cols:
            header_row_idx = i
            kode_col_idx = cols.index(SHOPEE_KODE_HEADER_NAME)

            if SHOPEE_HARGA_HEADER_NAME in cols:
                harga_col_idx = cols.index(SHOPEE_HARGA_HEADER_NAME)
                format_terdeteksi = "lama"
            elif SHOPEE_SUM_HARGA_START_HEADER in cols and SHOPEE_SUM_HARGA_END_HEADER in cols:
                sum_start_idx = cols.index(SHOPEE_SUM_HARGA_START_HEADER)
                sum_end_idx = cols.index(SHOPEE_SUM_HARGA_END_HEADER)
                format_terdeteksi = "baru"
            break

    if header_row_idx is None:
        return None, None, None

    kodes = []
    harga_map = {}
    for line in lines[header_row_idx + 1:]:
        if not line.strip():
            continue
        cols = line.split("\t")
        if len(cols) > kode_col_idx:
            kode = cols[kode_col_idx].strip()
            if not kode:
                continue
            kodes.append(kode)

            if harga_col_idx is not None and len(cols) > harga_col_idx:
                harga_map[kode] = harga_map.get(kode, 0) + to_number(cols[harga_col_idx].strip())
            elif sum_start_idx is not None and sum_end_idx is not None and len(cols) > sum_end_idx:
                total = sum(to_number(c) for c in cols[sum_start_idx:sum_end_idx + 1])
                harga_map[kode] = harga_map.get(kode, 0) + total

    return kodes, harga_map, format_terdeteksi


# nomor -> harga versi Excel (TOTAL semua item dalam 1 kode pesanan, karena
# 1 kode bisa muncul di beberapa baris export). Cuma keisi kalau mode skala
# besar & format harganya (lama ATAU baru) kedeteksi. Kosong = gak ada data
# pembanding -> validasi harga otomatis "-" (di-skip) buat nomor itu.
harga_excel_map = {}

if mode_input == "2":
    kodes_hasil_extract, harga_map_hasil_extract, format_excel = extract_kode_dan_harga_dari_excel_shopee(raw)

    if kodes_hasil_extract is None:
        print(f"\n❌ Kolom '{SHOPEE_KODE_HEADER_NAME}' tidak ditemukan di data yang di-paste.")
        print("   Pastikan kamu copy termasuk baris header tabel Excel-nya (bukan cuma datanya doang).")
        sys.exit()

    if not kodes_hasil_extract:
        print(f"\n❌ Kolom '{SHOPEE_KODE_HEADER_NAME}' ketemu, tapi semua barisnya kosong / gak ada kodenya.")
        sys.exit()

    print(f"\n✔ Ketemu kolom '{SHOPEE_KODE_HEADER_NAME}', berhasil ambil {len(kodes_hasil_extract)} kode pesanan dari data Excel.")

    if harga_map_hasil_extract and format_excel == "lama":
        print(f"✔ Format LAMA terdeteksi (kolom '{SHOPEE_HARGA_HEADER_NAME}') -> harga dari Excel akan divalidasi otomatis vs harga hasil scan aplikasi.")
        harga_excel_map = harga_map_hasil_extract
    elif harga_map_hasil_extract and format_excel == "baru":
        print(f"✔ Format BARU terdeteksi (kolom '{SHOPEE_SUM_HARGA_START_HEADER}' s/d '{SHOPEE_SUM_HARGA_END_HEADER}') -> harga dihitung otomatis dari jumlah rentang kolom itu, lalu divalidasi vs harga hasil scan aplikasi.")
        harga_excel_map = harga_map_hasil_extract
    else:
        print(f"⚠ Kolom harga (baik '{SHOPEE_HARGA_HEADER_NAME}' maupun rentang '{SHOPEE_SUM_HARGA_START_HEADER}'...'{SHOPEE_SUM_HARGA_END_HEADER}') gak ketemu -> validasi harga di-skip, cuma kode pesanan aja yang dipakai buat scan.")

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
    print(f"\n⚠ Ada {len(duplikat)} kode pesanan yang muncul lebih dari 1x di data input (berarti 1 pesanan berisi beberapa item):")
    for nomor, jumlah in duplikat.items():
        print(f"  - {nomor}  ({jumlah} item)")
    print("-> Dianggap 1 orderan: total harga Excel per kode dijumlah dari semua item-nya (dipakai pembanding validasi). Discan SEKALI per kode; di aplikasi dipakai baris yang Status_Bayar-nya Sudah (baris Belum dianggap noise).")
else:
    print("\n✔ Semua kode pesanan unik (1 item per pesanan).")

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

    def pilih_baris_primary(rows):
        """
        Pilih baris grid yang dianggap 'data asli' untuk 1 kode pesanan.

        TIDAK ADA penjumlahan harga (FIX BUG SELISIH palsu 2x lipat):
        kalau 1 kode pesanan muncul di >1 baris grid, itu BUKAN beberapa
        item yang harus dijumlah, tapi order yang SAMA ke-invoice lebih
        dari 1x (biasanya ada faktur yang Status_Bayar 'Sudah' + faktur
        lain 'Belum' dengan total yang sama). Baris 'Belum' itu cuma
        noise dan diabaikan.

        Aturan:
        - Kalau cuma 1 baris -> baris itu yang dipakai.
        - Kalau >1 baris -> cari baris pertama yang Status_Bayar-nya
          'sudah'/'paid'/'lunas'. Kalau gak ada yang Sudah (semuanya
          Belum), pakai baris pertama apa adanya.
        """
        if len(rows) == 1:
            return rows[0]
        for r in rows:
            if len(r) > 17 and r[17].strip().lower().replace(" ", "") in ("sudah", "paid", "lunas"):
                return r
        return rows[0]

    def find_data_rows(expected):
        """
        Setelah search + Enter + down, kumpulin SEMUA baris di grid yang
        kolom Memo-nya sama dengan `expected`.

        BARU: 1 kode pesanan bisa muncul di >1 baris grid (order yang sama
        ke-invoice lebih dari 1x, biasanya 1 faktur Sudah + 1 faktur
        Belum). Jadi fungsi ini gak cuma ambil baris pertama, tapi terus
        turun (down) + copy sampai gak ada lagi baris baru yang cocok.
        Tiap copy di-dedupe (baris yang sama gak dihitung 2x). Baris mana
        yang 'asli' diputuskan di caller (pilih yang Status_Bayar Sudah,
        yang Belum dianggap noise).

        Gak ada retry/delay tambahan (sama kayak versi sebelumnya): kalau
        copy pertama cuma header doang, gak ada baris yang cocok, ATAU
        clipboard kosong -> langsung dianggap NOT FOUND dan return None,
        biar bot langsung lanjut ke kode berikutnya.

        Return: (rows, debug_info, extra_down)
          - rows       : list baris grid yang cocok (bisa lebih dari 1
                         kalau order ke-invoice dobel), atau None kalau
                         NOT FOUND
          - debug_info : info alasan gagal (cuma kepake pas NOT FOUND)
          - extra_down : jumlah 'down' tambahan yang ditekan pas
                         ngumpulin baris item lain. Caller wajib nekan
                         'up' sebanyak 1 + extra_down buat balikin cursor
                         ke search box.
        """
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

        if len(lines) < 2:
            if len(lines) == 1:
                reason = "cuma HEADER yang ke-copy (dianggap NOT FOUND, gak diretry)"
            else:
                reason = "clipboard KOSONG (Ctrl+C gak nyalin apa-apa)"
            return None, {"reason": reason, "raw": text}, 0

        # Cari index kolom 'Memo' dari header (baris pertama) biar
        # gak hardcode posisi kalau urutan kolom beda-beda.
        header_cols = lines[0].split('\t')
        try:
            memo_idx = header_cols.index('Memo')
        except ValueError:
            memo_idx = 4  # fallback posisi default kalau nama kolom beda

        rows = []
        seen = set()

        def ambil_baris_cocok(raw_lines):
            """Tambah baris yang Memo-nya == expected. Dedupe by baris
            mentah (2 baris fisik yang isinya sama persis tetap dihitung
            keduanya). Return True kalau ada baris baru yang ke-tambah."""
            baru = False
            for raw_line in raw_lines:
                if not raw_line or raw_line in seen:
                    continue
                cols = raw_line.split('\t')
                if len(cols) > memo_idx and cols[memo_idx].strip() == expected:
                    if len(cols) >= 18:
                        seen.add(raw_line)
                        rows.append(cols)
                        baru = True
            return baru

        ambil_baris_cocok(lines[1:])

        if not rows:
            return None, {"reason": f"ada {len(lines)} baris ke-copy, tapi kolom Memo-nya TIDAK ADA yang sama dengan '{expected}'", "raw": text}, 0

        # Turun terus buat ambil baris item lain dari kode yang sama,
        # sampai gak ada baris baru yang cocok atau mentok batas aman.
        extra_down = 0
        while len(rows) < MAX_ITEM_PER_ORDER:
            pyautogui.press("down")
            time.sleep(DELAY_AFTER_DOWN)
            extra_down += 1

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
            if not ambil_baris_cocok(lines[1:] if len(lines) >= 2 else []):
                break

        return rows, None, extra_down

    def save_checkpoint():
        wb = Workbook()
        ws = wb.active
        ws.title = "Checkpoint"
        ws.append(["Nomor", "NoFaktur", "Salesman", "Customer", "Tanggal", "Memo", "Harga", "StatusRetur", "Status", "ValidasiHarga", "HargaExcel"])
        for x in sudah:
            ws.append([x["nomor"], x["no_faktur"], x["salesman"], x["customer"], x["tanggal"], x["memo"], x["harga"], x["retur"], "Sudah", x.get("validasi", "-"), x.get("harga_excel", "")])
        for x in belum:
            ws.append([x["nomor"], x["no_faktur"], x["salesman"], x["customer"], x["tanggal"], x["memo"], x["harga"], x["retur"], "Belum", x.get("validasi", "-"), x.get("harga_excel", "")])
        for x in not_found:
            ws.append([x, "", "", "", "", "", "", "", "NotFound", "-", ""])

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
        3. Beda Nilai     -> ketemu, tapi harga Excel vs Aplikasi beda
        4. Belum bayar    -> ketemu, status bayar masih Belum
        5. Sudah, aman    -> ketemu, Sudah bayar, gak ada masalah lain
        """
        if kind == "not_found":
            return "TIDAK ADA FAKTUR", "CEK", ""

        if item.get("retur") == "Retur":
            return "RETUR", "CEK", "RETUR"

        if item.get("validasi") == "SELISIH":
            return "BEDA NILAI", "CEK", ""

        if kind == "belum":
            return "BELUM", "CEK", ""

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

        # sheet khusus laporan kode pesanan multi-item dari data input
        if duplikat:
            ws2 = wb.create_sheet("Multi-Item")
            ws2.append(["Nomor", "Jumlah Item"])
            for nomor, jumlah in duplikat.items():
                ws2.append([nomor, jumlah])
            ws2.auto_filter.ref = f"A1:B{ws2.max_row}"

        # FIX BUG: wb.save() bisa gagal PermissionError kalau file
        # 'hasil_scan_bulanan.xlsx' lagi KEBUKA di Excel (Excel ngunci
        # file pas dibuka), atau kalau folder-nya read-only. Sebelumnya
        # ini bikin program CRASH di baris terakhir -> padahal semua
        # hasil scan udah kepegang di memory, sayang banget kalau hilang
        # gitu aja. Sekarang: kalau nama utama gagal, coba nama
        # alternatif (hasil_scan_bulanan_1.xlsx, dst) sampai berhasil.
        nama_file = "hasil_scan_bulanan.xlsx"
        percobaan = 0
        while True:
            try:
                wb.save(nama_file)
                if percobaan > 0:
                    print(f"\n⚠ 'hasil_scan_bulanan.xlsx' kayaknya lagi kebuka/kekunci -> hasil disimpan sebagai '{nama_file}' sebagai gantinya.")
                    print("  Tutup dulu file Excel yang lama kalau mau nama file balik ke 'hasil_scan_bulanan.xlsx'.")
                return nama_file
            except PermissionError:
                percobaan += 1
                nama_file = f"hasil_scan_bulanan_{percobaan}.xlsx"
                if percobaan > 20:
                    print("\n❌ Gagal nyimpen hasil_scan_bulanan.xlsx berkali-kali (kemungkinan folder read-only atau ke-lock terus).")
                    print("   Tutup semua file 'hasil_scan_bulanan*.xlsx' yang lagi kebuka, atau cek izin folder ini, lalu coba lagi.")
                    raise

    # =============================
    # NEW: CETAK TABEL RINGKASAN DI CMD
    # NOMOR FAKTUR | KODE PESANAN | STATUS BAYAR
    # =============================
    def print_summary_table(data):
        if not data:
            return

        status_label = {
            "Sudah": "🟢 Sudah",
            "Belum": "🟡 Belum",
            "Not Found": "🔴 Not Found",
        }

        headers = ["NO", "NOMOR FAKTUR", "KODE PESANAN", "CUSTOMER", "SALESMAN", "STATUS BAYAR", "VALIDASI HARGA (App vs Excel)"]
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

            rows.append([str(i), str(no_faktur), str(kode), str(customer), str(salesman), status_text, validasi_text])

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

    for index, nomor in enumerate(orders, start=1):
        spin = spinner[index % len(spinner)]
        elapsed = time.time() - start_time
        avg = elapsed / index if index else 0
        eta = avg * (len(orders) - index)
        print(
            f"{spin} [{index}/{len(orders)}] {nomor}  (avg {avg:.2f}s/baris, ETA {eta:.0f}s)",
            end="\r"
        )

        pyautogui.hotkey("ctrl", "a")
        pyperclip.copy(nomor)
        pyautogui.hotkey("ctrl", "v")
        pyautogui.press("enter")
        time.sleep(DELAY_AFTER_ENTER)

        pyautogui.press("down")
        time.sleep(DELAY_AFTER_DOWN)

        rows, debug_info, extra_down = find_data_rows(nomor)

        if rows is not None:
            # 1 kode pesanan bisa muncul di beberapa baris grid (order yang
            # sama ke-invoice lebih dari 1x, biasanya 1 faktur Sudah + 1
            # faktur Belum). TIDAK ADA penjumlahan harga. Baris 'asli' =
            # yang Status_Bayar-nya 'Sudah'; baris 'Belum' dianggap noise.
            primary = pilih_baris_primary(rows)

            harga = primary[PRICE_COLUMN_INDEX].strip() if len(primary) > PRICE_COLUMN_INDEX else ""

            first = primary
            customer = first[8].strip()
            memo = first[4].strip()
            no_faktur = first[0].strip()   # nomor faktur ASLI (kolom 'Nomor'), beda sama kode yang dicari

            if len(first) > SALESMAN_COLUMN_INDEX:
                salesman = first[SALESMAN_COLUMN_INDEX].strip()
            else:
                salesman = ""

            if len(first) > TANGGAL_COLUMN_INDEX:
                tanggal = first[TANGGAL_COLUMN_INDEX].strip()
            else:
                tanggal = ""

            # status bayar orderan = status baris 'asli'-nya (baris Belum
            # duplikat dianggap noise, gak bikin orderan jadi 'Belum').
            status_set = set()
            s = primary[17].strip().lower().replace(" ", "") if len(primary) > 17 else ""
            if s:
                status_set.add(s)
            status = "sudah" if status_set and status_set <= {"sudah", "paid", "lunas"} else "belum"

            # deteksi retur: cek kolom retur di baris 'asli'-nya aja.
            retur_detected = False
            if len(primary) > RETUR_COLUMN_INDEX:
                harga_item = to_number(primary[PRICE_COLUMN_INDEX].strip()) if len(primary) > PRICE_COLUMN_INDEX else 0
                retur_val = primary[RETUR_COLUMN_INDEX].strip()
                if retur_val and to_number(retur_val) == harga_item and harga_item != 0:
                    retur_detected = True
            status_retur = "Retur" if retur_detected else "Berhasil"

            validasi_harga, harga_excel = cek_validasi_harga(nomor, harga)

            if status in ("sudah", "paid", "lunas"):
                sudah.append({"nomor": nomor, "no_faktur": no_faktur, "salesman": salesman, "customer": customer, "tanggal": tanggal, "memo": memo, "harga": harga, "retur": status_retur, "validasi": validasi_harga, "harga_excel": harga_excel})
                hasil_urut.append({"nomor": nomor, "no_faktur": no_faktur, "salesman": salesman, "customer": customer, "tanggal": tanggal, "memo": memo, "status": "Sudah", "validasi": validasi_harga, "harga": harga, "harga_excel": harga_excel, "retur": status_retur})
                if SHOW_DETAIL_LOG:
                    tanda_validasi = f" | Validasi:{validasi_harga}" if validasi_harga != "-" else ""
                    print(f"\n🟢 {no_faktur} | {tanggal} | {customer} | {salesman} | {memo} | Rp{harga} | SUDAH | {status_retur}{tanda_validasi}")
            else:
                belum.append({"nomor": nomor, "no_faktur": no_faktur, "salesman": salesman, "customer": customer, "tanggal": tanggal, "memo": memo, "harga": harga, "retur": status_retur, "validasi": validasi_harga, "harga_excel": harga_excel})
                hasil_urut.append({"nomor": nomor, "no_faktur": no_faktur, "salesman": salesman, "customer": customer, "tanggal": tanggal, "memo": memo, "status": "Belum", "validasi": validasi_harga, "harga": harga, "harga_excel": harga_excel, "retur": status_retur})
                if SHOW_DETAIL_LOG:
                    tanda_validasi = f" | Validasi:{validasi_harga}" if validasi_harga != "-" else ""
                    print(f"\n🟡 {no_faktur} | {tanggal} | {customer} | {salesman} | {memo} | Rp{harga} | BELUM | {status_retur}{tanda_validasi}")

            # balikin cursor ke search box: 'up' harus sebanyak jumlah
            # 'down' yang ditekan (1 awal + extra_down pas ngumpulin item).
            for _ in range(1 + extra_down):
                pyautogui.press("up")
                time.sleep(DELAY_AFTER_UP)
        else:
            # LANGSUNG lanjut ke kode berikutnya, gak ada retry/delay lagi.
            # 'up' tetap ditekan (praktis instan, cuma PAUSE bawaan
            # pyautogui 0.02 detik) biar cursor balik ke search box buat
            # ctrl+a di kode selanjutnya.
            pyautogui.press("up")
            not_found.append(nomor)
            hasil_urut.append({"nomor": nomor, "no_faktur": "-", "salesman": "-", "customer": "-", "tanggal": "", "memo": "-", "status": "Not Found", "validasi": "-", "harga": "", "harga_excel": ""})

            if SHOW_DETAIL_LOG:
                print(f"\n🔴 {nomor} | NOT FOUND")
                if debug_notfound_shown < DEBUG_NOTFOUND_LIMIT:
                    debug_notfound_shown += 1
                    print(f"   [DEBUG] alasan gagal : {debug_info['reason']}")
                    print(f"   [DEBUG] raw clipboard: {debug_info['raw']!r}")

        if index % CHECKPOINT_EVERY == 0:
            save_checkpoint()

    print()
    runtime = round(time.time() - start_time, 2)

    save_checkpoint()  # simpan checkpoint terakhir juga

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

    print(f"🟢 Sudah     : {len(sudah)}  (Rp{total_sudah:,})")
    print(f"🟡 Belum     : {len(belum)}  (Rp{total_belum:,})")
    print(f"🔴 Not Found : {len(not_found)}")
    print(f"↩️  Retur     : {jumlah_retur}")
    if jumlah_divalidasi > 0:
        print(f"⚠️  Selisih Harga (Excel vs Aplikasi) : {jumlah_selisih} dari {jumlah_divalidasi} yang divalidasi")
    print()
    print(f"💰 Total Nilai Belum Bayar : Rp{total_belum:,}")
    print(f"💰 Total Nilai Keseluruhan : Rp{(total_sudah + total_belum):,}")
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