import time
import os
import re
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
UI_MODE = os.environ.get("BOPEL_UI_MODE") == "1"
SCRIPT_NAME = os.path.basename(__file__)

RESUME = "--resume" in sys.argv
CLICK_TEST = "--click-test" in sys.argv

GRACE_PASTE_DATA = 5
pyautogui.PAUSE = 0.02
pyautogui.FAILSAFE = True

DELAY_AFTER_ENTER = 0.7
DELAY_AFTER_DOWN  = 0.22
DELAY_AFTER_UP    = 0.08

POLL_GRID_TIMEOUT = 1.5

HEADER_RETRY = 2
HEADER_RETRY_DELAY = 0.18
RE_SEARCH_KONFIRMASI = True
GABUNG_ROW_DUPLIKAT = True
MAX_ROW_DUPLIKAT = 10

SHOW_DETAIL_LOG = False
DEBUG_NOTFOUND_LIMIT = 8
FOTO_AKTIF = True
FOTO_RETRY_BATAS = 5

KOLOM_GRID = {
    "Nomor": "nomor",
    "Tanggal": "tanggal",
    "Memo": "memo",
    "Salesman": "salesman",
    "Customer": "customer",
    "Total": "harga",
    "Retur": "retur",
    "Status_Bayar": "status",
    "TanggalPelunasan": "pelunasan",
}

SHOPEE_KODE_HEADER_NAME = "No. Pesanan"
SHOPEE_HARGA_HEADER_NAME = "Total Penghasilan"
SHOPEE_TANGGAL_HEADER_NAME = "Tanggal Dana Dilepaskan"
SHOPEE_REFUND_HEADER_NAME = "Jumlah Pengembalian Dana Ke Pembeli"
SHOPEE_HARGA_ASLI_HEADER_NAME = "Harga Asli Produk"
SHOPEE_TANGGAL_PESANAN_HEADER_NAME = "Waktu Pesanan Dibuat"
SHOPEE_TANGGAL_PESANAN_ALT = "Tanggal Pesanan Dibuat"

CHECKPOINT_FILE = "checkpoint_scan.xlsx"
CHECKPOINT_EVERY = 25

spinner = ["|", "/", "-", "\\"]

print("=" * 60)
print(" INVENTORY PAYMENT CHECKER (OPTIMIZED) ")
print("=" * 60)

sudah = []
belum = []
not_found = []
hasil_urut = []
sudah_scan = set()

harga_excel_map = {}
refund_excel_map = {}
harga_asli_excel_map = {}
tanggal_pesanan_excel_map = {}
tanggal_dilepas_map = {}

if RESUME:
    if not os.path.exists(CHECKPOINT_FILE):
        print(f"\n⚠ --resume diberikan tapi checkpoint '{CHECKPOINT_FILE}' tidak ada -> scan dari nol.")
    else:
        print(f"\n→ Mode --resume: lanjut dari checkpoint '{CHECKPOINT_FILE}'.")
        wb_ck = load_workbook(CHECKPOINT_FILE)
        ws_ck = wb_ck.active
        for row in ws_ck.iter_rows(min_row=2, values_only=True):
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
                hasil_urut.append({"nomor": nomor, "no_faktur": "-", "salesman": "-", "customer": "-", "tanggal": tanggal_dilepas_map.get(nomor, "") or tanggal, "memo": "-", "status": "Not Found", "validasi": "-", "harga": "", "harga_excel": "", "jumlah_duplikat_row": 1, "catatan_merge": "", "jumlah_cocok_excel": 0})
        print(f"-> Melanjutkan, {len(sudah_scan)} nomor sudah pernah di-scan.")

def norm_tanggal(s):
    s = (s or "").strip()
    if not s: return None
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y", "%d/%m/%Y %H:%M:%S", "%d/%m/%Y %H:%M"):
        try: return datetime.strptime(s, fmt).date()
        except ValueError: pass
    return None

def tanggal_pelunasan_beda(tgl_dilepas, tgl_pelunasan):
    a, b = norm_tanggal(tgl_dilepas), norm_tanggal(tgl_pelunasan)
    if a is None or b is None: return None
    return a != b

def extract_kode_dan_harga_dari_excel_shopee(raw_text):
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
            if SHOPEE_HARGA_HEADER_NAME in cols: harga_col_idx = cols.index(SHOPEE_HARGA_HEADER_NAME)
            if SHOPEE_TANGGAL_HEADER_NAME in cols: tanggal_col_idx = cols.index(SHOPEE_TANGGAL_HEADER_NAME)
            refund_col_idx = None
            harga_asli_col_idx = None
            tgl_pesan_col_idx = None
            for c in cols:
                cl = c.lower()
                if refund_col_idx is None and "pengembalian" in cl and "pembeli" in cl: refund_col_idx = cols.index(c)
                if harga_asli_col_idx is None and ("harga asli" in cl or "harga produk" in cl): harga_asli_col_idx = cols.index(c)
                if tgl_pesan_col_idx is None and ("pesanan dibuat" in cl or "tanggal pesanan" in cl): tgl_pesan_col_idx = cols.index(c)
            break

    if header_row_idx is None: return None, None, None, None, None, None

    kodes, harga_map, tanggal_map, refund_map, harga_asli_map, tanggal_pesan_map = [], {}, {}, {}, {}, {}
    for line in lines[header_row_idx + 1:]:
        if not line.strip(): continue
        cols = line.split("\t")
        if len(cols) > kode_col_idx:
            kode = cols[kode_col_idx].strip()
            if kode:
                kodes.append(kode)
                if harga_col_idx is not None and len(cols) > harga_col_idx: harga_map[kode] = cols[harga_col_idx].strip()
                if tanggal_col_idx is not None and len(cols) > tanggal_col_idx: tanggal_map[kode] = cols[tanggal_col_idx].strip()
                if refund_col_idx is not None and len(cols) > refund_col_idx: refund_map[kode] = cols[refund_col_idx].strip()
                if harga_asli_col_idx is not None and len(cols) > harga_asli_col_idx: harga_asli_map[kode] = cols[harga_asli_col_idx].strip()
                if tgl_pesan_col_idx is not None and len(cols) > tgl_pesan_col_idx: tanggal_pesan_map[kode] = cols[tgl_pesan_col_idx].strip()
    return kodes, harga_map, tanggal_map, refund_map, harga_asli_map, tanggal_pesan_map

def extract_kode_dan_harga_dari_daftar_shopee(raw_text):
    lines = [l.strip() for l in raw_text.splitlines() if l.strip()]
    try: start = lines.index("Total Penghasilan") + 1
    except ValueError: return None, None, None
    kodes, harga_map, tanggal_map = [], {}, {}
    i = start
    while i < len(lines):
        kode = lines[i]
        if re.fullmatch(r"26[A-Z0-9]{12,13}", kode):
            kodes.append(kode)
            if i + 5 < len(lines): harga_map[kode] = lines[i + 5]
            if i + 2 < len(lines): tanggal_map[kode] = lines[i + 2]
            i += 6
        else: i += 1
    return kodes, harga_map, tanggal_map

# STEP 1
if UI_MODE:
    print("⏳ Membaca clipboard...")
    time.sleep(GRACE_PASTE_DATA)
    auto_raw = pyperclip.paste().strip()
    kode_auto, _, _, _, _, _ = extract_kode_dan_harga_dari_excel_shopee(auto_raw)
    is_excel = kode_auto is not None
    mode_input = "2" if is_excel else "1"
else:
    mode_input = input("Pilih 1 (Kecil) / 2 (Besar): ").strip()
    input("Copy data, ENTER...")

raw = pyperclip.paste().strip()
if not raw: sys.exit(1)

if mode_input == "2":
    kodes_hasil_extract, harga_map_hasil_extract, tanggal_map_hasil_extract, refund_map_hx, harga_asli_map_hx, tgl_pesan_map_hx = extract_kode_dan_harga_dari_excel_shopee(raw)
    orders_raw = kodes_hasil_extract
    harga_excel_map = harga_map_hasil_extract
    tanggal_dilepas_map = tanggal_map_hasil_extract
    refund_excel_map = refund_map_hx
    harga_asli_excel_map = harga_asli_map_hx
    tanggal_pesanan_excel_map = tgl_pesan_map_hx
else:
    kodes_baru, harga_baru, tanggal_baru = extract_kode_dan_harga_dari_daftar_shopee(raw)
    if kodes_baru:
        orders_raw = kodes_baru
        harga_excel_map = harga_baru
        tanggal_dilepas_map = tanggal_baru
    else:
        orders_raw = [line.strip() for line in raw.splitlines() if line.strip()]

validasi.validasi_daftar_kode(orders_raw, konteks=f"mode {mode_input}")
orders = list(dict.fromkeys(orders_raw))
orders = [o for o in orders if o not in sudah_scan]

print(f"\nTotal nomor unik tersisa untuk discan : {len(orders)}")
if orders:
    if UI_MODE: validasi.preview_sebelum_mulai(orders)
    else:
        if input("\nMulai Scan? (y/n): ").lower() != "y": sys.exit()

    # STEP 2
    if not bsm.activate_and_refresh_bsm():
        sys.exit(1)
    if CLICK_TEST:
        coords = bsm.get_search_click_coords()
        if coords:
            pyautogui.click(coords)
            ambil_screenshot("click_test", "TEST")
        sys.exit(0)

    print("\n🚀 MULAI\n")

    def to_number(harga_str):
        s = str(harga_str).strip()
        if not s: return 0
        negative = s.startswith("-") or s.startswith("(")
        s = re.sub(r"[^0-9.,]", "", s)
        if not s: return 0
        if "," in s and "." in s:
            if s.rfind(",") > s.rfind("."): s = s.replace(".", "").replace(",", ".")
            else: s = s.replace(",", "")
        elif "," in s:
            head, _, tail = s.rpartition(",")
            if "," not in head and len(tail) == 2: s = head + "." + tail
            else: s = s.replace(",", "")
        elif "." in s:
            head, _, tail = s.rpartition(".")
            if "." not in head and len(tail) == 2: s = head + "." + tail
            else: s = s.replace(".", "")
        try: value = float(s)
        except ValueError: value = 0.0
        hasil = int(round(value))
        return -hasil if negative else hasil

    def cek_validasi_harga(nomor, harga_aplikasi):
        harga_excel = harga_excel_map.get(nomor)
        if not harga_excel: return "-", ""
        if to_number(harga_excel) == to_number(harga_aplikasi): return "OK", harga_excel
        return "SELISIH", harga_excel

    def find_data_row(expected):
        coords = bsm.get_search_click_coords()
        if not coords: return None, {"reason": "Koordinat search box tidak ditemukan"}, 0
        pyautogui.click(coords)
        pyautogui.hotkey("ctrl", "a")
        pyperclip.copy(expected)
        pyautogui.hotkey("ctrl", "v")
        pyautogui.press("enter")
        time.sleep(0.5)
        pyautogui.press("tab")
        time.sleep(0.5)
        pyautogui.hotkey("ctrl", "a")
        time.sleep(0.5)
        pyautogui.hotkey("ctrl", "c")
        time.sleep(0.5)
        text = pyperclip.paste()
        rows, cols_map, info = parse_bsm_page(text, expected)
        if info["valid"]:
            kolom_idx["v"] = cols_map
            return rows, None, 0
        return None, {"reason": "Halaman tidak valid"}, 0

    def pilih_baris_primary(rows, nomor):
        n = len(rows)
        if n == 1: return rows[0], 1, "", 0
        def harga_row(r): return to_number(ambil_kolom(r, "harga"))
        def status_sudah(r): return ambil_kolom(r, "status").lower().replace(" ", "") in ("sudah", "paid", "lunas")
        harga_excel = harga_excel_map.get(nomor, "")
        if harga_excel:
            rows_cocok_excel = [r for r in rows if harga_row(r) == to_number(harga_excel)]
            jumlah_cocok = len(rows_cocok_excel)
            if jumlah_cocok == 0: return rows[0], n, f"CEK MANUAL - {n} ROW", 0
            primary_row = None
            for r in rows_cocok_excel:
                if status_sudah(r):
                    primary_row = r; break
            if primary_row is None: primary_row = rows_cocok_excel[0]
            return primary_row, n, f"DOUBLE FAKTUR ({n} row)", jumlah_cocok
        return rows[0], n, f"CEK MANUAL - {n} ROW", 0

    def save_checkpoint():
        wb = Workbook()
        ws = wb.active
        ws.append(["Nomor", "NoFaktur", "Salesman", "Customer", "Tanggal", "Memo", "Harga", "StatusRetur", "Status", "ValidasiHarga", "HargaExcel", "JumlahDuplikatRow", "CatatanMerge", "JumlahCocokExcel"])
        for x in sudah + belum:
            ws.append([x["nomor"], x["no_faktur"], x["salesman"], x["customer"], x["tanggal"], x["memo"], x["harga"], x["retur"], x["status"], x.get("validasi", "-"), x.get("harga_excel", ""), x.get("jumlah_duplikat_row", 1), x.get("catatan_merge", ""), x.get("jumlah_cocok_excel", 0)])
        for x in not_found:
            ws.append([x, "", "", "", "", "", "", "", "NotFound", "-", "", 1, "", 0])
        try: wb.save(CHECKPOINT_FILE)
        except PermissionError: pass

    def save_final():
        wb = Workbook()
        ws = wb.active
        ws.append(["SALES", "TGL", "KODE PESANAN", "NO. FAKTUR", "KETERANGAN", "STATUS", "REVISI"])
        for r in hasil_urut:
            sales = r.get("customer") or "-"
            tgl = r.get("tanggal") or ""
            kode = r["nomor"]
            no_faktur = r.get("no_faktur") or ""
            ws.append([sales, tgl, kode, no_faktur, r.get("status"), r.get("status"), ""])
        nama = "hasil_scan.xlsx"
        try: wb.save(nama)
        except PermissionError: pass
        return nama

    # =============================
    # TABEL RINGKASAN HASIL SCAN
    # =============================
    def print_summary_table(data):
        if not data:
            return

        status_label = {
            "Sudah": "🟢 Sudah",
            "Belum": "🟡 Belum",
            "Not Found": "🔴 Not Found",
        }

        # Hitung salesman terbanyak
        sales_counts = {}
        for x in data:
            s = x.get("salesman", "-")
            sales_counts[s] = sales_counts.get(s, 0) + 1
        common_salesman = max(sales_counts, key=sales_counts.get) if sales_counts else None

        headers = ["NO", "SALESMAN", "KODE PESANAN", "NOMOR FAKTUR", "STATUS BAYAR", "KETERANGAN"]
        rows = []
        for i, x in enumerate(data, 1):
            no_faktur = x.get("no_faktur") or "-"
            kode = x["nomor"]
            salesman = x.get("salesman") or "-"
            status = x.get("status")
            status_text = status_label.get(status, status)

            # Logika Keterangan
            if status == "Not Found":
                keterangan = "-"
            elif status == "Belum":
                keterangan = "CEK"
            elif salesman != common_salesman:
                keterangan = "SLH CUST"
            else:
                keterangan = "OK"

            rows.append([str(i), str(salesman), str(kode), str(no_faktur), status_text, keterangan])

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

    start_time = time.time()

    metrik = {"diproses": 0, "sukses": 0, "not_found": 0}
    kolom_idx = {"v": None}

    def ambil_kolom(row, kunci):
        i = (kolom_idx["v"] or {}).get(kunci, -1)
        return row[i].strip() if 0 <= i < len(row) else ""

    for index, nomor in enumerate(orders, start=1):
        try:
            metrik["diproses"] += 1
            rows, debug_info, _ = find_data_row(nomor)
            if rows:
                metrik["sukses"] += 1
                row = rows[0]

                # Fungsi lokal untuk ambil data berdasarkan mapping parser baru
                def get_val(key):
                    # kolom_idx["v"] diset di find_data_row
                    idx = kolom_idx["v"].get(key, -1)
                    if 0 <= idx < len(row):
                        return row[idx]
                    return ""

                # Ambil data pakai mapping yang dikembalikan parser
                customer = get_val("customer")
                no_faktur = get_val("nomor")
                status = get_val("status").lower() # Parser baru sudah set status di kolom yang tepat
                salesman = get_val("salesman")
                tanggal = get_val("tanggal")
                harga = get_val("total")

                # Cek status bayar
                hasil_status = "Sudah" if status in ("sudah", "paid", "lunas") else "Belum"

                item = {
                    "nomor": nomor, "no_faktur": no_faktur, "salesman": salesman,
                    "customer": customer, "tanggal": tanggal, "memo": nomor,
                    "harga": harga, "retur": "-", "status": hasil_status
                }
                if hasil_status == "Sudah": sudah.append(item)
                else: belum.append(item)
                hasil_urut.append(item)

                print(f"✔ {nomor} -> {hasil_status}")
            else:
                metrik["not_found"] += 1
                not_found.append(nomor)
                hasil_urut.append({"nomor": nomor, "no_faktur": "-", "status": "Not Found"})
                print(f"🔴 {nomor} -> NOT FOUND")
        except Exception as e:
            print(f"❌ Error scan {nomor}: {e}")
            metrik["error"] += 1

    # =============================
    # RINGKASAN AKHIR
    # =============================
    total_sudah = len(sudah)
    total_belum = len(belum)
    total_not_found = len(not_found)
    runtime = round(time.time() - start_time, 2)

    print("\n" + "=" * 60)
    print("HASIL SCAN")
    print("=" * 60)
    print()
    print(f"🟢 Sukses    : {total_sudah}")
    print(f"🟡 Cek manual: {total_belum}")
    print(f"🔴 Not Found : {total_not_found}")
    print(f"⏱ Waktu      : {runtime} detik  (~{runtime/max(len(orders),1):.2f} detik/baris)")
    print()

    print_summary_table(hasil_urut)

    save_final()
    print("Scan Selesai")
