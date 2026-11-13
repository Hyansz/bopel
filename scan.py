import time
import os
import re
from datetime import datetime
import pyautogui
import pyperclip
import sys
from openpyxl import Workbook, load_workbook
from openpyxl.styles import PatternFill, Font

from core import validasi
from core import window
from core.observ import (
    ambil_screenshot,
    cetak_ringkasan,
    simpan_metrik,
    tunggu_grid_respon,
)
from core.parsing import cari_baris_memo_terpecah, gabungkan_baris_terpecah
from core.parsing import catatan_retur_shopee, deteksi_retur_shopee
from core import bsm
from core.parsing_bsm import parse_bsm_page

# =============================
# CONFIG — SILAKAN TUNING DI SINI
# =============================
# Mode UI (dijalankan dari BopelApp via launcher): semua prompt input()
# yang gak bisa dijawab dari terminal Textual di-skip / auto-continue,
# window warehouse di-aktivasi otomatis (core/window.py).
UI_MODE = os.environ.get("BOPEL_UI_MODE") == "1"
SCRIPT_NAME = os.path.basename(__file__)

# RESUME dari checkpoint = OPT-IN lewat flag CLI `--resume`
# (python scan.py --resume). Tanpa flag = scan SELALU dari nol, checkpoint
# lama diabaikan (ditimpa pas autosave pertama).
RESUME = "--resume" in sys.argv
CLICK_TEST = "--click-test" in sys.argv

# Grace delay baca clipboard di mode UI: user copy data Shopee DULU, lalu
# klik Start; clipboard dibaca otomatis N detik setelah Start (tanpa
# prompt 'Copy data -> ENTER').
GRACE_PASTE_DATA = 5
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

# SEMUA kolom grid aplikasi dicari DINAMIS dari NAMA di baris header hasil
# copy (baris pertama yang ke-copy dari grid). Alasan: layout/urutan kolom
# aplikasi BISA BERUBAH antar view/window — kasus nyata 2026-08-22: view
# 'Browse Faktur Penjualan' punya susunan kolom beda dari view lama, jadi
# index hardcode lama membaca kolom SALAH (harga kebaca 'Customer' ->
# semua baris jadi SELISIH; status kebaca 'Bayar' -> semua kecatet Belum).
# Nilai -1 = kolom tidak ada di grid ini -> kolom itu dianggap kosong.
KOLOM_GRID = {
    "Nomor": "nomor",              # No. Faktur (bukan kode pesanan)
    "Tanggal": "tanggal",
    "Memo": "memo",                # kode pesanan
    "Salesman": "salesman",
    "Customer": "customer",
    "Total": "harga",
    "Retur": "retur",
    "Status_Bayar": "status",      # Sudah/Belum/paid/lunas
    "TanggalPelunasan": "pelunasan",
}

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

# nama kolom tanggal dilepas di export Excel Shopee (mode skala besar).
# Dicari dari NAMA header juga (bukan hardcode posisi), isinya jadi
# kolom TGL di hasil scan.
SHOPEE_TANGGAL_HEADER_NAME = "Tanggal Dana Dilepaskan"

# Kolom tambahan untuk deteksi RETUR (mode skala besar).
# Nama header ini bisa bervariasi antar export; dicari secara LOOSE.
SHOPEE_REFUND_HEADER_NAME = "Jumlah Pengembalian Dana Ke Pembeli"
SHOPEE_HARGA_ASLI_HEADER_NAME = "Harga Asli Produk"
SHOPEE_TANGGAL_PESANAN_HEADER_NAME = "Waktu Pesanan Dibuat"
SHOPEE_TANGGAL_PESANAN_ALT = "Tanggal Pesanan Dibuat"

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
# RESUME DARI CHECKPOINT (OPT-IN: flag CLI --resume)
# =============================
sudah = []
belum = []
not_found = []

# NEW: nyimpen hasil dalam URUTAN SCAN (dipakai buat tabel ringkasan di cmd),
# beda sama sudah/belum/not_found yang kepisah per kategori.
hasil_urut = []

sudah_scan = set()

# Map2 di bawah DIDEKLARASIKAN DI SINI (bukan di blok parse Shopee nanti)
# karena blok checkpoint di bawah ini nulis hasil_urut duluan, sementara
# map-nya baru diisi setelah data Shopee di-paste. Dulu baris 'Not Found'
# di jalur checkpoint nge-access tanggal_dilepas_map sebelum ada ->
# NameError: name 'tanggal_dilepas_map' is not defined.
# Isi aslinya (hasil extract) tetap menimpa nilai kosong ini di bawah.

# nomor -> harga versi Excel (dari kolom AG / 'Total Penghasilan'). Cuma
# keisi kalau mode skala besar & kolomnya ketemu. Kosong = gak ada data
# pembanding -> validasi harga otomatis "-" (di-skip) buat nomor itu.
harga_excel_map = {}

# nomor -> data retur dari Excel income Shopee (mode besar)
refund_excel_map = {}
harga_asli_excel_map = {}
tanggal_pesanan_excel_map = {}

# nomor -> 'Tanggal Dana Dilepaskan' Shopee (mode kecil: blok Dana
# Dilepaskan; mode besar: kolom 'Tanggal Dana Dilepaskan' export Excel).
# Isi kolom TGL di hasil scan; fallback = tanggal transaksi dari grid
# aplikasi.
tanggal_dilepas_map = {}

if RESUME:
    if not os.path.exists(CHECKPOINT_FILE):
        print(f"\n⚠ --resume diberikan tapi checkpoint '{CHECKPOINT_FILE}' tidak ada -> scan dari nol.")
    else:
        print(f"\n→ Mode --resume: lanjut dari checkpoint '{CHECKPOINT_FILE}'.")
        wb_ck = load_workbook(CHECKPOINT_FILE)
        ws_ck = wb_ck.active
        for row in ws_ck.iter_rows(min_row=2, values_only=True):
            # dukung checkpoint format LAMA (9 kolom, sebelum ada
            # ValidasiHarga & HargaExcel), format SEDANG (11 kolom),
            # format BARU (13 kolom: + JumlahDuplikatRow & CatatanMerge
            # buat gabung row duplikat), maupun format TERBARU (14 kolom:
            # + JumlahCocokExcel buat notifikasi duplikasi tervalidasi),
            # dan format TERKINI (15 kolom: + TanggalPelunasanBeda), serta
            # format TERKINI+ (16 kolom: + TanggalPelunasan asli, buat kolom
            # REVISI pas status 'Tanggal Pelunasan Beda').
            if len(row) >= 16:
                nomor, no_faktur, salesman, customer, tanggal, memo, harga, retur, status, validasi, harga_excel_ck, jumlah_dupl_ck, catatan_ck, jumlah_cocok_ck, pelunasan_beda_ck, tgl_pelunasan_ck = row
            elif len(row) >= 15:
                nomor, no_faktur, salesman, customer, tanggal, memo, harga, retur, status, validasi, harga_excel_ck, jumlah_dupl_ck, catatan_ck, jumlah_cocok_ck, pelunasan_beda_ck = row
                tgl_pelunasan_ck = ""
            elif len(row) >= 14:
                nomor, no_faktur, salesman, customer, tanggal, memo, harga, retur, status, validasi, harga_excel_ck, jumlah_dupl_ck, catatan_ck, jumlah_cocok_ck = row
                pelunasan_beda_ck = False
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
                sudah.append({"nomor": nomor, "no_faktur": no_faktur, "salesman": salesman, "customer": customer, "tanggal": tanggal, "memo": memo, "harga": harga, "retur": retur, "validasi": validasi, "harga_excel": harga_excel_ck, "jumlah_duplikat_row": jumlah_dupl_ck, "catatan_merge": catatan_ck or "", "jumlah_cocok_excel": jumlah_cocok_ck or 0, "tanggal_pelunasan_beda": bool(pelunasan_beda_ck), "tgl_pelunasan": tgl_pelunasan_ck or ""})
                hasil_urut.append({"nomor": nomor, "no_faktur": no_faktur, "salesman": salesman, "customer": customer, "tanggal": tanggal, "memo": memo, "status": "Sudah", "validasi": validasi, "harga": harga, "harga_excel": harga_excel_ck, "retur": retur, "jumlah_duplikat_row": jumlah_dupl_ck, "catatan_merge": catatan_ck or "", "jumlah_cocok_excel": jumlah_cocok_ck or 0, "tanggal_pelunasan_beda": bool(pelunasan_beda_ck), "tgl_pelunasan": tgl_pelunasan_ck or ""})
            elif status == "Belum":
                belum.append({"nomor": nomor, "no_faktur": no_faktur, "salesman": salesman, "customer": customer, "tanggal": tanggal, "memo": memo, "harga": harga, "retur": retur, "validasi": validasi, "harga_excel": harga_excel_ck, "jumlah_duplikat_row": jumlah_dupl_ck, "catatan_merge": catatan_ck or "", "jumlah_cocok_excel": jumlah_cocok_ck or 0, "tanggal_pelunasan_beda": bool(pelunasan_beda_ck), "tgl_pelunasan": tgl_pelunasan_ck or ""})
                hasil_urut.append({"nomor": nomor, "no_faktur": no_faktur, "salesman": salesman, "customer": customer, "tanggal": tanggal, "memo": memo, "status": "Belum", "validasi": validasi, "harga": harga, "harga_excel": harga_excel_ck, "retur": retur, "jumlah_duplikat_row": jumlah_dupl_ck, "catatan_merge": catatan_ck or "", "jumlah_cocok_excel": jumlah_cocok_ck or 0, "tanggal_pelunasan_beda": bool(pelunasan_beda_ck), "tgl_pelunasan": tgl_pelunasan_ck or ""})
            else:
                not_found.append(nomor)
                # checkpoint lama tidak menyimpan tanggal utk baris Not
                # Found -> tidak bisa direkonstruksi mundur. Pakai map
                # tanggal_dilepas_map (sumber live) dengan fallback ke
                # tanggal dari baris checkpoint ("" utk checkpoint lama).
                hasil_urut.append({"nomor": nomor, "no_faktur": "-", "salesman": "-", "customer": "-", "tanggal": tanggal_dilepas_map.get(nomor, "") or tanggal, "memo": "-", "status": "Not Found", "validasi": "-", "harga": "", "harga_excel": "", "jumlah_duplikat_row": 1, "catatan_merge": "", "jumlah_cocok_excel": 0})
        print(f"-> Melanjutkan, {len(sudah_scan)} nomor sudah pernah di-scan.")

def norm_tanggal(s):
    """Parse string tanggal umum -> datetime.date | None.
    Format dikenali: ISO (2026-08-20), m/d/yyyy (grid inventory),
    d/m/yyyy (blok teks Shopee), dengan/tanpa jam. None = kosong atau
    format tak dikenali."""
    s = (s or "").strip()
    if not s:
        return None
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y",
                "%d/%m/%Y %H:%M:%S", "%d/%m/%Y %H:%M"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            pass
    return None


def tanggal_pelunasan_beda(tgl_dilepas, tgl_pelunasan):
    """True = keduanya terisi & tanggalnya BEDA (anomali input tanggal).
    False = sama. None = skip (ada yang kosong / tak terparse) -> jangan
    flag. Perbandingan SETELAH normalisasi, bukan string equality."""
    a, b = norm_tanggal(tgl_dilepas), norm_tanggal(tgl_pelunasan)
    if a is None or b is None:
        return None
    return a != b


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
       dibanding harga yang didapat bot pas scan di aplikasi. Kolom
       SHOPEE_TANGGAL_HEADER_NAME ('Tanggal Dana Dilepaskan') juga
       diambil -> jadi isi kolom TGL di hasil scan.
    3. Untuk tiap baris SETELAH header, split by tab, ambil isi kode di
       index kode, dan isi harga/tanggal di indexnya masing-masing
       (kalau kolomnya ketemu). Baris yang kodenya kosong (mis. pesanan
       batal/belum ada kode) otomatis di-skip karena gak ada yang mau
       dicari.

    Return (None, None, None) kalau baris header 'No. Pesanan' gak ketemu
    sama sekali (berarti bukan format yang diharapkan) -> caller bisa
    kasih pesan error yang jelas ke user, bukan diam-diam salah parse.

    Kalau kode ketemu tapi kolom harga ('Total Penghasilan') gak ketemu,
    tetap return kodenya, cuma harga_map-nya bakal kosong -> validasi
    harga otomatis di-skip (bukan bikin program berhenti). Sama halnya
    kalau kolom tanggal gak ketemu -> tanggal_map kosong (TGL fallback
    ke tanggal grid aplikasi).
    """
    lines = raw_text.splitlines()

    header_row_idx = None
    kode_col_idx = None
    harga_col_idx = None
    tanggal_col_idx = None
    for i, line in enumerate(lines):
        cols = [c.strip() for c in line.split("\t")]
        if SHOPEE_KODE_HEADER_NAME in cols:
            header_row_idx = i
            kode_col_idx = cols.index(SHOPEE_KODE_HEADER_NAME)
            if SHOPEE_HARGA_HEADER_NAME in cols:
                harga_col_idx = cols.index(SHOPEE_HARGA_HEADER_NAME)
            if SHOPEE_TANGGAL_HEADER_NAME in cols:
                tanggal_col_idx = cols.index(SHOPEE_TANGGAL_HEADER_NAME)

            # Kolom retur (cari fleksibel — beberapa export pakai nama berbeda)
            refund_col_idx = None
            harga_asli_col_idx = None
            tgl_pesan_col_idx = None
            for c in cols:
                cl = c.lower()
                if refund_col_idx is None and "pengembalian" in cl and "pembeli" in cl:
                    refund_col_idx = cols.index(c)
                if harga_asli_col_idx is None and ("harga asli" in cl or "harga produk" in cl):
                    harga_asli_col_idx = cols.index(c)
                if tgl_pesan_col_idx is None and ("pesanan dibuat" in cl or "tanggal pesanan" in cl):
                    tgl_pesan_col_idx = cols.index(c)
            break

    if header_row_idx is None:
        return None, None, None, None, None, None

    kodes = []
    harga_map = {}
    tanggal_map = {}
    refund_map = {}
    harga_asli_map = {}
    tanggal_pesan_map = {}
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
                if tanggal_col_idx is not None and len(cols) > tanggal_col_idx:
                    tanggal_map[kode] = cols[tanggal_col_idx].strip()
                if refund_col_idx is not None and len(cols) > refund_col_idx:
                    refund_map[kode] = cols[refund_col_idx].strip()
                if harga_asli_col_idx is not None and len(cols) > harga_asli_col_idx:
                    harga_asli_map[kode] = cols[harga_asli_col_idx].strip()
                if refund_col_idx is not None and len(cols) > refund_col_idx:
                    refund_map[kode] = cols[refund_col_idx].strip()
                if harga_asli_col_idx is not None and len(cols) > harga_asli_col_idx:
                    harga_asli_map[kode] = cols[harga_asli_col_idx].strip()
                if tgl_pesan_col_idx is not None and len(cols) > tgl_pesan_col_idx:
                    tanggal_pesan_map[kode] = cols[tgl_pesan_col_idx].strip()

    return kodes, harga_map, tanggal_map, refund_map, harga_asli_map, tanggal_pesan_map


def extract_kode_dan_harga_dari_daftar_shopee(raw_text):
    """
    Format baru scan kecil: copy halaman 'Dana Dilepaskan' Shopee
    (teks polos, bukan tabel tab-separated). Struktur: 5 baris header
    ('Pesanan', 'Tanggal Dana Dilepaskan', 'Status', 'Metode
    Pembayaran', 'Total Penghasilan') diikuti blok 6 baris per
    pesanan: kode, 'Pembeli:<nama>', tanggal, status, metode, harga
    ('Rp39.550').

    Return (kodes, harga_map, tanggal_map) — atau (None, None, None)
    kalau header 'Total Penghasilan' gak ketemu (bukan format ini) ->
    caller fallback ke daftar kode polos lama. tanggal_map = kolom
    'Tanggal Dana Dilepaskan' (baris ke-3 tiap blok), dipakai sebagai
    isi kolom TGL di hasil scan.
    """
    lines = [l.strip() for l in raw_text.splitlines() if l.strip()]
    try:
        start = lines.index("Total Penghasilan") + 1
    except ValueError:
        return None, None, None

    kodes = []
    harga_map = {}
    tanggal_map = {}
    i = start
    while i < len(lines):
        kode = lines[i]
        if re.fullmatch(r"26[A-Z0-9]{12,13}", kode):
            kodes.append(kode)
            if i + 5 < len(lines):
                harga_map[kode] = lines[i + 5]
            if i + 2 < len(lines):
                tanggal_map[kode] = lines[i + 2]
            i += 6
        else:
            i += 1  # baris tak dikenal -> lompat, cari blok kode berikutnya
    return kodes, harga_map, tanggal_map


# =============================
# STEP 1 — PILIH MODE INPUT
# =============================
if UI_MODE:
    print(
"""
STEP 1

Mode UI — clipboard dibaca OTOMATIS (tanpa prompt ENTER):
  - Isi clipboard = copy tabel Excel Shopee (ada kolom 'No. Pesanan')
    -> mode skala BESAR otomatis.
  - Isi clipboard = daftar kode polos (satu kode per baris) atau
    hasil copy 'Dana Dilepaskan' Shopee (blok 6 baris per pesanan)
    -> mode skala KECIL otomatis.

PASTIKAN data Shopee SUDAH di-copy ke clipboard sebelum klik Start.
"""
    )
    print(f"⏳ Membaca clipboard dalam {GRACE_PASTE_DATA} detik...")
    time.sleep(GRACE_PASTE_DATA)
    print("✔ Membaca clipboard...")

    # Deteksi otomatis format: kalau ada header 'No. Pesanan' -> mode besar.
    auto_raw = pyperclip.paste().strip()
    if not auto_raw:
        print("❌ Clipboard kosong! Pastikan data Shopee sudah di-copy ke clipboard sebelum klik Start.")
        sys.exit(1)
    kode_auto, _, _, _, _, _ = extract_kode_dan_harga_dari_excel_shopee(auto_raw)
    is_excel = kode_auto is not None

    scan_mode = os.environ.get("BOPEL_SCAN_MODE", "") # "kecil" or "detail"
    if scan_mode == "detail" and not is_excel:
        print("❌ Scan Detail butuh tabel Excel mutasi Shopee (kolom 'No. Pesanan'). Clipboard berisi daftar kode — pilih Scan Kode Pesanan atau copy tabel Excel lengkap.")
        sys.exit(1)
    if scan_mode == "kecil" and is_excel:
        print("❌ Scan Kode Pesanan butuh daftar kode polos atau hasil copy 'Dana Dilepaskan' Shopee. Clipboard berisi tabel Excel mutasi — pilih Scan Detail atau copy daftar kode.")
        sys.exit(1)

    mode_input = "2" if is_excel else "1"
    print(f"ℹ Format clipboard terdeteksi: {'tabel Excel Shopee (Scan Detail)' if mode_input == '2' else 'daftar kode (Scan Kode Pesanan)'}.")
else:
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
    sys.exit(1)


if mode_input == "2":
    kodes_hasil_extract, harga_map_hasil_extract, tanggal_map_hasil_extract, refund_map_hx, harga_asli_map_hx, tgl_pesan_map_hx = extract_kode_dan_harga_dari_excel_shopee(raw)

    if kodes_hasil_extract is None:
        print(f"\n❌ Kolom '{SHOPEE_KODE_HEADER_NAME}' tidak ditemukan di data yang di-paste.")
        print("   Pastikan kamu copy termasuk baris header tabel Excel-nya (bukan cuma datanya doang).")
        sys.exit(1)

    if not kodes_hasil_extract:
        print(f"\n❌ Kolom '{SHOPEE_KODE_HEADER_NAME}' ketemu, tapi semua barisnya kosong / gak ada kodenya.")
        sys.exit(1)

    print(f"\n✔ Ketemu kolom '{SHOPEE_KODE_HEADER_NAME}', berhasil ambil {len(kodes_hasil_extract)} kode pesanan dari data Excel.")

    if harga_map_hasil_extract:
        print(f"✔ Ketemu kolom '{SHOPEE_HARGA_HEADER_NAME}' (AG) -> harga dari Excel akan divalidasi otomatis vs harga hasil scan aplikasi.")
        harga_excel_map = harga_map_hasil_extract
    else:
        print(f"⚠ Kolom '{SHOPEE_HARGA_HEADER_NAME}' gak ketemu -> validasi harga di-skip, cuma kode pesanan aja yang dipakai buat scan.")

    if tanggal_map_hasil_extract:
        print(f"✔ Ketemu kolom '{SHOPEE_TANGGAL_HEADER_NAME}' -> TGL di hasil scan = tanggal dana dilepaskan.")
        tanggal_dilepas_map = tanggal_map_hasil_extract

    # map retur
    if refund_map_hx:
        refund_excel_map = refund_map_hx
    if harga_asli_map_hx:
        harga_asli_excel_map = harga_asli_map_hx
    if tgl_pesan_map_hx:
        tanggal_pesanan_excel_map = tgl_pesan_map_hx

    orders_raw = kodes_hasil_extract
else:
    kodes_baru, harga_baru, tanggal_baru = extract_kode_dan_harga_dari_daftar_shopee(raw)
    if kodes_baru:
        print(f"\n✔ Format daftar 'Dana Dilepaskan' Shopee terdeteksi — ambil {len(kodes_baru)} kode pesanan dari data.")
        if harga_baru:
            print("✔ Harga 'Total Penghasilan' ketemu -> harga dari Shopee akan divalidasi otomatis vs harga hasil scan aplikasi.")
        else:
            print("⚠ Harga gak ke-extract -> validasi harga di-skip, cuma kode pesanan aja yang dipakai buat scan.")
        orders_raw = kodes_baru
        harga_excel_map = harga_baru
        tanggal_dilepas_map = tanggal_baru
    else:
        orders_raw = []
        for line in raw.splitlines():
            line = line.strip()
            if line:
                orders_raw.append(line)

# =============================
# VALIDASI WAJIB (SEBELUM data dipakai / diketik ke aplikasi)
# =============================
# Fail-safe: SATU baris saja tidak match pola kode pesanan Shopee
# (26 + 12-13 alfanumerik) -> SELURUH data ditolak + proses STOP.
# Ini gerbang pertama — teks bebas/prompt yang nyasar ke clipboard
# TIDAK akan pernah sampai ke kotak SEARCH aplikasi warehouse.
validasi.validasi_daftar_kode(orders_raw, konteks=f"mode {mode_input}")

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
    if UI_MODE:
        # Preview data SEBELUM bot menyentuh aplikasi: user sempat lihat
        # & klik Stop kalau data yang terbaca salah.
        validasi.preview_sebelum_mulai(orders)
        print(f"⏳ Scan mulai dalam {GRACE_PASTE_DATA} detik — klik STOP sekarang kalau data di atas salah...")
        time.sleep(GRACE_PASTE_DATA)
        print("✔ Mulai scan otomatis (mode UI).")
    else:
        if input("\nMulai Scan? (y/n): ").lower() != "y":
            sys.exit()

    # =============================
    # STEP 2
    # =============================
    print("\nSTEP 2")
    # AUTO (mode UI): cari + aktifkan window warehouse dari config.yaml
    # (target_window_title). Kalau gak ketemu -> pesan error jelas + exit 1
    # (bukan crash; UI nampilin sebagai tool gagal). Di luar mode UI tetap
    # alt-tab manual seperti lama.
    # window.persiapkan_window_target(SCRIPT_NAME, required=UI_MODE)
    if not bsm.activate_and_refresh_bsm():
        sys.exit(1)
    if CLICK_TEST:
        coords = bsm.get_search_click_coords()
        if coords:
            pyautogui.click(coords)
            ambil_screenshot("click_test", "TEST")
        sys.exit(0)
    # print("Klik SEARCH NOMOR — window warehouse sudah dibawa ke depan otomatis")
    # print("Cursor harus berkedip")

    if UI_MODE:
        print(f"⏳ Mulai dalam {GRACE_PASTE_DATA} detik — klik kotak SEARCH sekarang...")
        time.sleep(GRACE_PASTE_DATA)
    else:
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
        coords = bsm.get_search_click_coords()
        if not coords:
            return None, {"reason": "Koordinat search box tidak ditemukan"}, 0

        pyautogui.click(coords)
        pyautogui.hotkey("ctrl", "a")
        pyperclip.copy(expected)
        pyautogui.hotkey("ctrl", "v")
        pyautogui.press("enter")

        # Polling tunggu grid load (berbasis perubahan clipboard)
        time.sleep(0.5)
        pyautogui.press("tab") # keluar dari search box
        time.sleep(0.5)

        # Copy All
        pyautogui.hotkey("ctrl", "a")
        time.sleep(0.5)
        pyautogui.hotkey("ctrl", "c")
        time.sleep(0.5)

        text = pyperclip.paste()
        rows, cols_map, valid = parse_bsm_page(text, expected)

        if valid:
            kolom_idx["v"] = cols_map
            if rows:
                return rows, None, 0
            else:
                return None, {"reason": "Kode tidak ditemukan di halaman valid"}, 0

        # Jika halaman tidak valid atau gagal
        return None, {"reason": "Halaman tidak valid"}, 0

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
            return to_number(ambil_kolom(r, "harga"))

        def status_sudah(r):
            return ambil_kolom(r, "status").lower().replace(" ", "") in ("sudah", "paid", "lunas")

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
        ws.append(["Nomor", "NoFaktur", "Salesman", "Customer", "Tanggal", "Memo", "Harga", "StatusRetur", "Status", "ValidasiHarga", "HargaExcel", "JumlahDuplikatRow", "CatatanMerge", "JumlahCocokExcel", "TanggalPelunasanBeda", "TanggalPelunasan"])
        for x in sudah:
            ws.append([x["nomor"], x["no_faktur"], x["salesman"], x["customer"], x["tanggal"], x["memo"], x["harga"], x["retur"], "Sudah", x.get("validasi", "-"), x.get("harga_excel", ""), x.get("jumlah_duplikat_row", 1), x.get("catatan_merge", ""), x.get("jumlah_cocok_excel", 0), x.get("tanggal_pelunasan_beda", False), x.get("tgl_pelunasan", "")])
        for x in belum:
            ws.append([x["nomor"], x["no_faktur"], x["salesman"], x["customer"], x["tanggal"], x["memo"], x["harga"], x["retur"], "Belum", x.get("validasi", "-"), x.get("harga_excel", ""), x.get("jumlah_duplikat_row", 1), x.get("catatan_merge", ""), x.get("jumlah_cocok_excel", 0), x.get("tanggal_pelunasan_beda", False), x.get("tgl_pelunasan", "")])
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
        1. Retur          -> kolom Retur ke-detect ATAU baris income
                             Shopee nandain refund. dicek DULU (sebelum
                             not_found) karena retur bisa terjadi tanpa
                             baris faktur di aplikasi — kasUS nyata
                             260907DWRKTD19 (refund penuh, faktur sudah
                             dihapus). Kalau dicek belakangan, baris itu
                             salah jadi 'TIDAK ADA FAKTUR'.
        2. Not found      -> gak ada datanya sama sekali di aplikasi
                             DAN bukan retur
        3. Beda Nilai     -> ketemu, tapi harga Excel vs Aplikasi beda,
                             ATAU 1 kode muncul di >1 baris dengan harga
                             BEDA (bukan split faktur, harus dicek manual)
        4. Belum bayar    -> ketemu, status bayar masih Belum
        5. Sudah, aman    -> ketemu, Sudah bayar, gak ada masalah lain
                             (termasuk yang baris duplikatnya berhasil
                             digabung jadi Sudah -> tercatat di REVISI)
        """
        if item.get("retur") == "Retur":
            catatan = item.get("catatan_merge", "")
            return "RETUR", "CEK", catatan or "RETUR"

        if kind == "not_found":
            return "TIDAK ADA FAKTUR", "CEK", ""

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
        ws.append(["SALES", "TGL CAIR", "KODE PESANAN", "NO. FAKTUR", "KETERANGAN", "STATUS", "REVISI"])

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
            "Tanggal Pelunasan Beda": (PatternFill("solid", fgColor="DDEBF7"), Font(color="1F4E79")),  # biru muda
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
            # Anomali tanggal pelunasan: jadi KETERANGAN sendiri (bukan
            # cuma timpa STATUS) supaya dapat warna baris sendiri juga.
            # STATUS turun jadi CEK. REVISI diisi tanggal pelunasan dari
            # grid inventory (ISO YYYY-MM-DD kalau terparse, teks mentah
            # kalau tidak); catatan lain (DOUBLE FAKTUR dll) tetap
            # digabung " | ".
            if r.get("tanggal_pelunasan_beda"):
                keterangan = "Tanggal Pelunasan Beda"
                status_txt = "CEK"
                d_p = norm_tanggal(r.get("tgl_pelunasan") or "")
                tgl_revisi = d_p.isoformat() if d_p else (r.get("tgl_pelunasan") or "")
                revisi = " | ".join(x for x in (revisi, tgl_revisi) if x)

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
        # CEK MANUAL (multi-item genuin / harga beda antar baris) TIDAK ikut
        # total utama: harga yang dipakai = harga baris pertama (belum tentu
        # benar — mis. item multi harga 50rb padahal total order 200rb).
        # Dipisah + di-flag, supaya angka SELISIH/total tidak menyesatkan.
        cek_manual_items = [x for x in all_items if x.get("catatan_merge", "").startswith("CEK MANUAL")]
        verified_items = [x for x in all_items if not x.get("catatan_merge", "").startswith("CEK MANUAL")]
        rekap_total_aplikasi = sum(to_number(x["harga"]) for x in verified_items)
        rekap_total_excel = sum(to_number(x.get("harga_excel", "")) for x in verified_items if x.get("harga_excel"))
        rekap_total_ok = sum(to_number(x["harga"]) for x in verified_items if x.get("validasi") == "OK")
        rekap_total_selisih = sum(to_number(x["harga"]) for x in verified_items if x.get("validasi") == "SELISIH")
        rekap_cek_count = len(cek_manual_items)
        rekap_cek_excel = sum(to_number(x.get("harga_excel", "")) for x in cek_manual_items if x.get("harga_excel"))

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
        ws3.append(["Status OK", sum(1 for x in verified_items if x.get("validasi") == "OK")])
        ws3.append(["Status SELISIH", sum(1 for x in verified_items if x.get("validasi") == "SELISIH")])
        ws3.append(["Double Faktur (duplikat row digabung)", sum(1 for x in all_items if x.get("jumlah_duplikat_row", 1) > 1)])
        ws3.append(["Duplikasi Tervalidasi (>1 row cocok harga Excel)", sum(1 for x in all_items if "TERDETEKSI DATA DUPLIKASI" in x.get("catatan_merge", ""))])
        if cek_manual_items:
            # Blok terpisah: item yang butuh verifikasi manual TIDAK masuk
            # total utama (harga-nya belum pasti). Nilai Excel = acuan
            # berapa yang seharusnya, biar user tahu ukurannya.
            ws3.append(["", ""])
            ws3.append(["CEK MANUAL (belum terverifikasi — TIDAK termasuk total di atas)", ""])
            ws3.append(["Jumlah Item CEK MANUAL", rekap_cek_count])
            ws3.append(["Nilai acuan per Excel (cek manual)", rekap_cek_excel if rekap_cek_excel else "tanpa data harga Excel"])
            ws3.cell(row=ws3.max_row - 2, column=1).font = Font(bold=True, color="9C0006")

        # format header rekap
        ws3["A1"].font = Font(bold=True, size=14)
        ws3["A3"].font = Font(bold=True)
        ws3["B3"].font = Font(bold=True)
        ws3["A9"].font = Font(bold=True)
        # format angka kolom B untuk SEMUA baris numerik (bukan range
        # hardcode — jumlah baris berubah kalau ada blok CEK MANUAL)
        for row in ws3.iter_rows(min_row=4, max_row=ws3.max_row, min_col=1, max_col=2):
            for cell in row:
                if cell.column == 2 and isinstance(cell.value, int):
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
            kode = x["nomor"]
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
        "baris_terpecah": 0,  # observability: baris grid rekonstruksi newline-dalam-sel
        "retur_tanpa_faktur": 0,  # retur dari Excel income yg fakturnya udah dihapus
    }

    # Index kolom grid (by nama, lihat KOLOM_GRID) — diisi SEKALI dari
    # baris header yang ikut ke-copy tiap baca clipboard. None = header
    # belum kebaca. Pola sama dgn pencarian 'Memo' by nama.
    kolom_idx = {"v": None}

    def ambil_kolom(row, kunci):
        """Isi kolom `kunci` (nama logis di KOLOM_GRID) dari satu baris
        grid, sudah strip. "" kalau header belum kebaca / kolom tak ada."""
        i = (kolom_idx["v"] or {}).get(kunci, -1)
        return row[i].strip() if 0 <= i < len(row) else ""

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

            # SAFETY-NET: sebelum paste ke kotak SEARCH, pastikan teks
            # beneran kode pesanan (panjang wajar + pola). Kalau ada yang
            # mencoba mengetik teks mencurigakan -> ABORT seluruh proses.
            nomor = validasi.cegah_ketik_tidak_aman(nomor, konteks=f"loop scan [{index}/{len(orders)}]")

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

                customer = ambil_kolom(row, "customer")
                memo = ambil_kolom(row, "memo")
                no_faktur = ambil_kolom(row, "nomor")   # nomor faktur ASLI (kolom 'Nomor'), beda sama kode yang dicari
                status = ambil_kolom(row, "status").lower().replace(" ", "")
                salesman = ambil_kolom(row, "salesman")

                # TGL di hasil = 'Tanggal Dana Dilepaskan' Shopee (kalau
                # datanya ada, mode kecil); fallback = tanggal transaksi
                # dari grid aplikasi.
                tanggal = tanggal_dilepas_map.get(nomor) or ambil_kolom(row, "tanggal")
                harga = ambil_kolom(row, "harga")
                retur = ambil_kolom(row, "retur")

                # deteksi retur: (1) dari Excel income (refund ke pembeli),
                # ATAU (2) kolom Retur di grid sama dengan harga
                if deteksi_retur_shopee(
                    refund_excel_map.get(nomor, "0"),
                    harga_excel_map.get(nomor, "0"),
                    harga_asli_excel_map.get(nomor, "0"),
                ):
                    status_retur = "Retur"
                elif retur and to_number(retur) == to_number(harga) and to_number(harga) != 0:
                    status_retur = "Retur"
                else:
                    status_retur = "Berhasil"

                validasi_harga, harga_excel = cek_validasi_harga(nomor, harga)

                # Validasi TanggalPelunasan (grid inventory) vs Tanggal Dana
                # Dilepaskan (Excel Shopee): keduanya terisi tapi beda setelah
                # normalisasi = indikasi input tanggal salah. Salah satu
                # kosong / kolom grid tidak ada -> skip (bukan anomali).
                tgl_pelunasan = ambil_kolom(row, "pelunasan")
                pelunasan_beda = tanggal_pelunasan_beda(tanggal_dilepas_map.get(nomor, ""), tgl_pelunasan)
                if pelunasan_beda:
                    print(f"\n⚠ {no_faktur} | {nomor} | Tanggal pencairan beda: dilepas {tanggal_dilepas_map.get(nomor)} vs pelunasan {tgl_pelunasan}")

                if status in ("sudah", "paid", "lunas"):
                    item_sudah = {"nomor": nomor, "no_faktur": no_faktur, "salesman": salesman, "customer": customer, "tanggal": tanggal, "memo": memo, "harga": harga, "retur": status_retur, "validasi": validasi_harga, "harga_excel": harga_excel, "jumlah_duplikat_row": jumlah_duplikat_row, "catatan_merge": catatan_merge, "jumlah_cocok_excel": jumlah_cocok_excel, "tanggal_pelunasan_beda": bool(pelunasan_beda), "tgl_pelunasan": tgl_pelunasan}
                    sudah.append(item_sudah)
                    hasil_urut.append({"nomor": nomor, "no_faktur": no_faktur, "salesman": salesman, "customer": customer, "tanggal": tanggal, "memo": memo, "status": "Sudah", "validasi": validasi_harga, "harga": harga, "harga_excel": harga_excel, "retur": status_retur, "jumlah_duplikat_row": jumlah_duplikat_row, "catatan_merge": catatan_merge, "jumlah_cocok_excel": jumlah_cocok_excel, "tanggal_pelunasan_beda": bool(pelunasan_beda), "tgl_pelunasan": tgl_pelunasan})
                    if SHOW_DETAIL_LOG:
                        tanda_validasi = f" | Validasi:{validasi_harga}" if validasi_harga != "-" else ""
                        tanda_dup = f" | {teks_duplikat(item_sudah)}" if jumlah_duplikat_row > 1 else ""
                        print(f"\n🟢 {no_faktur} | {tanggal} | {customer} | {salesman} | {memo} | Rp{harga} | SUDAH | {status_retur}{tanda_validasi}{tanda_dup}")
                else:
                    item_belum = {"nomor": nomor, "no_faktur": no_faktur, "salesman": salesman, "customer": customer, "tanggal": tanggal, "memo": memo, "harga": harga, "retur": status_retur, "validasi": validasi_harga, "harga_excel": harga_excel, "jumlah_duplikat_row": jumlah_duplikat_row, "catatan_merge": catatan_merge, "jumlah_cocok_excel": jumlah_cocok_excel, "tanggal_pelunasan_beda": bool(pelunasan_beda), "tgl_pelunasan": tgl_pelunasan}
                    belum.append(item_belum)
                    hasil_urut.append({"nomor": nomor, "no_faktur": no_faktur, "salesman": salesman, "customer": customer, "tanggal": tanggal, "memo": memo, "status": "Belum", "validasi": validasi_harga, "harga": harga, "harga_excel": harga_excel, "retur": status_retur, "jumlah_duplikat_row": jumlah_duplikat_row, "catatan_merge": catatan_merge, "jumlah_cocok_excel": jumlah_cocok_excel, "tanggal_pelunasan_beda": bool(pelunasan_beda), "tgl_pelunasan": tgl_pelunasan})
                    if SHOW_DETAIL_LOG:
                        tanda_validasi = f" | Validasi:{validasi_harga}" if validasi_harga != "-" else ""
                        tanda_dup = f" | {teks_duplikat(item_belum)}" if jumlah_duplikat_row > 1 else ""
                        print(f"\n🟡 {no_faktur} | {tanggal} | {customer} | {salesman} | {memo} | Rp{harga} | BELUM | {status_retur}{tanda_validasi}{tanda_dup}")

                # Posisi cursor sudah terfokus di search box karena klik koordinat.
                # Tidak perlu press up lagi.
            else:
                if FOTO_AKTIF:
                    ambil_screenshot(nomor, "NOT_FOUND", "final")

                # LANGSUNG lanjut ke kode berikutnya. Tidak perlu press up lagi.

                # FIX BUG "RETUR tercatat TIDAK ADA FAKTUR": baris income
                # Shopee yang retur (kolom 'Jumlah Pengembalian Dana Ke
                # Pembeli' != 0) TIDAK PUNYA baris faktur penjualan di
                # aplikasi (barisnya sudah dihapus waktu refund). Detection
                # retur harus dievaluasi dari data Excel SEBELUM/INDEPENDEN
                # dari temuan faktur — kalau tidak, retur seperti
                # 260907DWRKTD19 (refund -150000, total -17100) salah
                # masuk kategori Not Found.
                #
                # Di sini: 'rows is None' (faktur tidak ada) TETAP dicatat
                # sebagai Retur kalau data Excel-nya menandai refund. Nominal
                # refund + total (biaya yang tetap terpotong) disimpan di
                # catatan_merge supaya tidak hilang di laporan.
                if deteksi_retur_shopee(
                    refund_excel_map.get(nomor, "0"),
                    harga_excel_map.get(nomor, "0"),
                    harga_asli_excel_map.get(nomor, "0"),
                ):
                    # retur tanpa faktur asal -> dicatat Retur dengan flag
                    catatan_retur = catatan_retur_shopee(
                        refund_excel_map.get(nomor, "0"),
                        harga_excel_map.get(nomor, "0"),
                        tanpa_faktur=True,
                    )
                    hasil_urut.append({
                        "nomor": nomor, "no_faktur": "-", "salesman": "-", "customer": "-",
                        "tanggal": tanggal_dilepas_map.get(nomor, "") or tanggal_pesanan_excel_map.get(nomor, ""),
                        "memo": "-", "status": "Belum", "retur": "Retur",
                        "validasi": "-", "harga": harga_excel_map.get(nomor, ""),
                        "harga_excel": harga_excel_map.get(nomor, ""),
                        "jumlah_duplikat_row": 1, "catatan_merge": catatan_retur,
                        "jumlah_cocok_excel": 0,
                        "tanggal_pelunasan_beda": False, "tgl_pelunasan": "",
                    })
                    belum.append(hasil_urut[-1])
                    metrik["retur_tanpa_faktur"] += 1
                    if SHOW_DETAIL_LOG:
                        print(f"\n↩️  {nomor} | RETUR (tanpa faktur asal) | {catatan_retur}")
                else:
                    metrik["not_found"] += 1
                    not_found.append(nomor)
                    hasil_urut.append({"nomor": nomor, "no_faktur": "-", "salesman": "-", "customer": "-", "tanggal": tanggal_dilepas_map.get(nomor, ""), "memo": "-", "status": "Not Found", "validasi": "-", "harga": "", "harga_excel": "", "jumlah_duplikat_row": 1, "catatan_merge": "", "jumlah_cocok_excel": 0})

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
    # CEK MANUAL TIDAK ikut total harga utama (harga yang dipakai = baris
    # pertama, belum tentu benar) — dipisah + di-flag eksplisit di bawah.
    cek_manual_items = [x for x in (sudah + belum) if x.get("catatan_merge", "").startswith("CEK MANUAL")]
    verified_items = [x for x in (sudah + belum) if not x.get("catatan_merge", "").startswith("CEK MANUAL")]

    total_sudah = sum(to_number(x["harga"]) for x in sudah if not x.get("catatan_merge", "").startswith("CEK MANUAL"))
    total_belum = sum(to_number(x["harga"]) for x in belum if not x.get("catatan_merge", "").startswith("CEK MANUAL"))
    jumlah_retur = sum(1 for x in (sudah + belum) if x["retur"] == "Retur")
    jumlah_selisih = sum(1 for x in verified_items if x.get("validasi") == "SELISIH")
    jumlah_divalidasi = sum(1 for x in verified_items if x.get("validasi") in ("OK", "SELISIH"))
    # Status OK = sama dengan kolom STATUS 'OK' di Excel: SUDAH bayar,
    # bukan retur, bukan CEK MANUAL, harga validasi bukan SELISIH.
    jumlah_status_ok = sum(1 for x in sudah if x.get("retur") != "Retur" and not x.get("catatan_merge", "").startswith("CEK MANUAL") and x.get("validasi") != "SELISIH")
    # Beda/Cek Manual (card UI): semua item berstatus CEK di Excel =
    # belum bayar + selisih + retur + cek manual. Sukses+Beda+Not Found
    # = total item.
    jumlah_beda_cek = len(sudah) + len(belum) - jumlah_status_ok
    jumlah_double = sum(1 for x in (sudah + belum) if x.get("jumlah_duplikat_row", 1) > 1)
    jumlah_double_beda_harga = len(cek_manual_items)
    jumlah_duplikasi_tervalidasi = sum(1 for x in (sudah + belum) if "TERDETEKSI DATA DUPLIKASI" in x.get("catatan_merge", ""))

    print(f"🟢 Sudah     : {len(sudah)}  (Rp{total_sudah:,})")
    print(f"🟡 Belum     : {len(belum)}  (Rp{total_belum:,})")
    print(f"🔴 Not Found : {len(not_found)}")
    print(f"↩️  Retur     : {jumlah_retur}")
    if metrik["retur_tanpa_faktur"]:
        print(f"   ↳️  retur tanpa faktur asal (dari Excel income) : {metrik['retur_tanpa_faktur']}")
    if jumlah_double:
        print(f"🔁 Double Faktur (baris duplikat digabung) : {jumlah_double}")
    if jumlah_double_beda_harga:
        print(f"❓ Double Faktur BEDA HARGA (perlu cek manual) : {jumlah_double_beda_harga}")
    if jumlah_duplikasi_tervalidasi:
        print(f"🚨 Duplikasi Tervalidasi (>1 row cocok harga Excel) : {jumlah_duplikasi_tervalidasi}")
    if jumlah_divalidasi > 0:
        print(f"⚠️  Selisih Harga (Excel vs Aplikasi) : {jumlah_selisih} dari {jumlah_divalidasi} yang divalidasi")
    print(f"✔ Status OK  : {jumlah_status_ok}")
    print(f"≠ Beda   : {jumlah_beda_cek} (belum/selisih/retur/cek manual)")
    print()
    total_aplikasi = total_sudah + total_belum
    total_excel = sum(to_number(x.get("harga_excel", "")) for x in verified_items if x.get("harga_excel"))
    total_ok = sum(to_number(x["harga"]) for x in verified_items if x.get("validasi") == "OK")

    print(f"💰 Total Harga Aplikasi   : Rp{total_aplikasi:,}")
    print(f"💰 Total Harga Excel      : Rp{total_excel:,}")
    print(f"💰 Total Harga Status OK  : Rp{total_ok:,}")
    if cek_manual_items:
        total_cek_excel = sum(to_number(x.get("harga_excel", "")) for x in cek_manual_items if x.get("harga_excel"))
        if total_cek_excel:
            print(f"❓ CEK MANUAL ({len(cek_manual_items)} item, belum terverifikasi, TIDAK termasuk total di atas): nilai Excel Rp{total_cek_excel:,}")
        else:
            print(f"❓ CEK MANUAL ({len(cek_manual_items)} item, belum terverifikasi, TIDAK termasuk total di atas — tanpa data harga Excel)")
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
    # COPY SEMUA KODE/MEMO KE CLIPBOARD (termasuk yang NOT FOUND,
    # biar bisa discan ulang / dicek manual)
    # =============================
    all_items = sudah + belum
    memo_text = "\n".join(item["memo"] for item in all_items)
    if not_found:
        memo_text += ("\n" if memo_text else "") + "\n".join(not_found)
    pyperclip.copy(memo_text)

    if not_found:
        print(f"\n📋 Semua kode pesanan (Memo) + {len(not_found)} kode NOT FOUND berhasil disalin ke clipboard.")
    else:
        print("\n📋 Semua kode pesanan (Memo) berhasil disalin ke clipboard.")

    nama_file_hasil = export_final()

    # hapus checkpoint kalau sudah selesai total & sukses
    if os.path.exists(CHECKPOINT_FILE):
        os.remove(CHECKPOINT_FILE)

    print()
    print(f"✔ {nama_file_hasil} berhasil dibuat")

# Di mode UI, proses harus KELUAR sendiri (ToolFinished di UI nunggu
# exit). "ENTER untuk keluar" cuma buat mode manual (jalan langsung dari
# terminal, biar window CMD gak langsung nutup).
if not UI_MODE:
    input("\nENTER untuk keluar...")