import time
import pyautogui
import pyperclip
import re
import sys
from collections import deque

from core.observ import (
    ambil_screenshot,
    cetak_ringkasan,
    simpan_metrik,
)

# =============================
# CONFIG
# =============================
DELAY = 0.25      # diperbesar
FAST = 0.12
MAX_LOOP = 500

# tampilkan teks mentah hasil Ctrl+A (buat debug kalau parsing meleset)
DEBUG_PRICE = True

# OBSERVABILITY — auto-screenshot ke logs/screenshots/. Retry difoto
# tapi DI-BATASI biar gak banjir file. Matiin total: FOTO_AKTIF = False.
FOTO_AKTIF = True
FOTO_RETRY_BATAS = 5

spinner = ["|", "/", "-", "\\"]

CODE_PATTERN = re.compile(r'\b26[A-Z0-9]{12,13}\b')

# sentinel unik untuk validasi clipboard (lihat safe_copy)
CLIP_SENTINEL = "__CLIP_EMPTY_SENTINEL__"


# =============================
# HELPER: COPY CLIPBOARD YANG AMAN (FIX BUG FALSE DUPLICATE)
# =============================
def safe_copy(delay=FAST, retries=4, settle=0.05, metrik=None):
    """
    Ctrl+C ke clipboard TAPI divalidasi supaya gak kebaca data BASI.

    Root cause bug 'DUPLIKAT VALID' palsu: kadang Ctrl+C ditekan sebelum
    aplikasi target benar-benar siap (misalnya belum masuk mode edit di
    F2, atau UI belum update), jadi clipboard OS masih berisi teks LAMA
    (contoh nyata: sisa data Shopee dari STEP 1). Fungsi regex pencari
    kode lalu ketemu kode pertama di teks basi itu -> dianggap "row
    ketemu" padahal row aslinya belum pernah kebaca. Saat scan beneran
    sampai ke row asli, kode itu terbaca LAGI -> dikira duplikat.

    Fix: sebelum Ctrl+C, clipboard di-set ke sentinel unik dulu. Setelah
    Ctrl+C, kalau isi clipboard MASIH sentinel (atau kosong), berarti
    copy belum kejadian -> retry dengan delay lebih lama. Return None
    kalau semua percobaan gagal (caller wajib handle None).

    OBSERVABILITY: kalau `metrik` dikasih (dict), tiap percobaan retry
    dihitung, dan kalau SEMUA percobaan gagal difoto keadaan layarnya
    (event COPY_GAGAL, biar ketahuan kenapa copy mentok).
    """
    for attempt in range(retries):
        if metrik is not None and attempt > 0:
            metrik["retry"] += 1
        pyperclip.copy(CLIP_SENTINEL)
        time.sleep(settle)
        pyautogui.hotkey('ctrl', 'c')
        time.sleep(delay + attempt * 0.05)  # delay makin nambah tiap retry
        text = pyperclip.paste()
        if text is not None and text != CLIP_SENTINEL and text.strip() != "":
            return text
    if metrik is not None and FOTO_AKTIF and metrik["foto_retry"] < FOTO_RETRY_BATAS:
        metrik["foto_retry"] += 1
        ambil_screenshot("", "COPY_GAGAL")
    return None


# =============================
# HELPER: PARSE HARGA
# =============================
def parse_price(text):
    """
    Ambil angka HARGA dari sebuah teks/sel.
    Support 2 format:
        Shopee   : Rp77.950        -> titik = ribuan
        Aplikasi : 299,877.00      -> koma = ribuan, titik = desimal
    """
    if not text:
        return None

    first = re.split(r'[\t\n\r]+', text.strip())[0].strip()
    if not first:
        return None

    cleaned = re.sub(r'[^\d.,]', '', first)
    if cleaned == '':
        return None

    if ',' in cleaned and '.' in cleaned:
        cleaned = cleaned.replace(',', '')
        cleaned = cleaned.split('.')[0]
    elif ',' in cleaned:
        cleaned = cleaned.replace(',', '')
    elif '.' in cleaned:
        parts = cleaned.split('.')
        if len(parts[-1]) == 3:
            cleaned = cleaned.replace('.', '')
        else:
            cleaned = parts[0]

    if cleaned == '':
        return None

    try:
        return int(cleaned)
    except ValueError:
        return None


def parse_app_table(text):
    """
    Parse hasil Ctrl+A dari aplikasi (tab-separated, baris pertama = header)
    jadi dict {kode_memo: harga_nilai}.

    Posisi kolom dihitung dari KANAN (jarak dari kolom terakhir/'Memo'),
    BUKAN dari kiri. Ini penting karena kolom paling kiri ('No') kadang
    kosong dan tidak menghasilkan tab sama sekali di sebagian baris,
    sehingga kalau dihitung dari kiri semua kolom jadi geser. Menghitung
    dari kanan aman karena 'Memo' selalu kolom paling terakhir.
    """
    if not text:
        return {}

    lines = [l for l in re.split(r'\r\n|\n|\r', text) if l.strip() != '']
    if len(lines) < 2:
        return {}

    header = lines[0].split('\t')
    try:
        memo_idx = header.index('Memo')
        nilai_idx = header.index('Nilai')
    except ValueError:
        print("⚠️ Kolom 'Memo' atau 'Nilai' tidak ditemukan di header hasil Ctrl+A.")
        print(f"   Header terbaca: {header}")
        return {}

    n_header_cols = len(header)
    memo_from_end = n_header_cols - 1 - memo_idx    # biasanya 0 (paling kanan)
    nilai_from_end = n_header_cols - 1 - nilai_idx

    result = {}
    debug_shown = 0
    for line in lines[1:]:
        cols = line.split('\t')
        needed = max(memo_from_end, nilai_from_end) + 1
        if len(cols) < needed:
            continue

        kode = cols[len(cols) - 1 - memo_from_end].strip()
        if not kode:
            continue

        harga_raw = cols[len(cols) - 1 - nilai_from_end]
        harga = parse_price(harga_raw)
        result[kode] = harga

        if DEBUG_PRICE and debug_shown < 5:
            print(f"[DEBUG] app row -> kode={kode!r} nilai_raw={harga_raw!r} parsed={harga}")
            debug_shown += 1

    return result


def parse_shopee_prices(raw_text, target_codes):
    """
    Dari teks yang di-paste di STEP 1 (hasil copy dari Shopee), cari harga
    (baris 'RpXXX.XXX' / Total Penghasilan) yang muncul di bawah tiap kode pesanan.
    """
    result = {}
    matches = list(CODE_PATTERN.finditer(raw_text))

    for i, m in enumerate(matches):
        kode = m.group(0)
        if kode not in target_codes or kode in result:
            continue

        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(raw_text)
        block = raw_text[start:end]

        price_match = re.search(r'Rp\s*([\d.,]+)', block)
        if price_match:
            harga = parse_price(price_match.group(1))
            if harga is not None:
                result[kode] = harga

    return result


def print_price_table(codes, app_prices, shopee_prices):
    """Cetak tabel kode pesanan + harga aplikasi vs harga Shopee ke cmd."""
    headers = ["NO", "KODE PESANAN", "HARGA APLIKASI", "HARGA SHOPEE", "COCOK"]
    rows = []
    total_app = 0
    total_shopee = 0
    total_cocok = 0
    count_ok = 0
    mismatch = 0
    missing_app = 0

    for i, c in enumerate(codes, 1):
        p1 = app_prices.get(c)
        p2 = shopee_prices.get(c)

        p1_str = f"Rp {p1:,}".replace(",", ".") if p1 is not None else "-"
        p2_str = f"Rp {p2:,}".replace(",", ".") if p2 is not None else "-"

        if p1 is not None:
            total_app += p1
        else:
            missing_app += 1

        if p2 is not None:
            total_shopee += p2

        if p1 is not None and p2 is not None:
            cocok = "OK" if p1 == p2 else "BEDA"
            if p1 == p2:
                total_cocok += p1
                count_ok += 1
            else:
                mismatch += 1
        else:
            cocok = "?"

        rows.append([str(i), c, p1_str, p2_str, cocok])

    col_widths = [
        max(len(headers[idx]), max((len(r[idx]) for r in rows), default=0))
        for idx in range(len(headers))
    ]

    def line(ch='-'):
        return "+" + "+".join(ch * (w + 2) for w in col_widths) + "+"

    def fmt_row(r):
        return "| " + " | ".join(cell.ljust(w) for cell, w in zip(r, col_widths)) + " |"

    print("\n" + "=" * 60)
    print("TABEL KODE PESANAN + HARGA (APLIKASI vs SHOPEE)")
    print("=" * 60)
    print(line())
    print(fmt_row(headers))
    print(line('='))
    for r in rows:
        print(fmt_row(r))
    print(line())

    print(f"TOTAL HARGA APLIKASI : Rp {total_app:,}".replace(",", "."))
    print(f"TOTAL HARGA SHOPEE   : Rp {total_shopee:,}".replace(",", "."))
    print(f"TOTAL HARGA COCOK    : Rp {total_cocok:,} ({count_ok} item OK)".replace(",", "."))

    if missing_app:
        print(f"⚠️ {missing_app} kode tidak ketemu harganya di tabel aplikasi.")
    if mismatch:
        print(f"⚠️ Ada {mismatch} kode dengan harga TIDAK COCOK antara aplikasi & Shopee!")
    elif missing_app == 0:
        print("✅ Semua harga yang berhasil dibandingkan COCOK.")


# =============================
# HEADER
# =============================
print("=" * 50)
print("BOT VALIDASI + AUTO CHECKLIST + HARGA (STABLE)")
print("=" * 50)

# =============================
# STEP 1 - AMBIL DATA SHOPEE
# =============================
input("\nSTEP 1:\nCopy data Shopee → ENTER...\n")

raw = pyperclip.paste()

if not raw.strip():
    print("❌ Clipboard kosong!")
    sys.exit()

orders = CODE_PATTERN.findall(raw)
orders = list(dict.fromkeys(orders))

print("\nORDER TERBACA:")
for o in orders:
    print(f"- {o}")

print(f"\nTotal: {len(orders)}")

if not orders:
    print("❌ Tidak ada data!")
    sys.exit()

if input("\nLanjut scan + checklist? (y/n): ").lower() != "y":
    sys.exit()

# FIX BUG: hitung harga Shopee di sini, SEBELUM loop scan mulai. `raw` dan
# `orders` udah lengkap dari STEP 1, jadi gak perlu nunggu scan aplikasi
# selesai buat tau harga Shopee-nya. Sebelumnya baris ini ada di PALING
# BAWAH (setelah loop scan) padahal `shopee_prices.get(kode)` udah dipakai
# DI DALAM loop -> NameError: name 'shopee_prices' is not defined, karena
# variabelnya belum pernah dibikin pas baris itu dieksekusi.
shopee_prices = parse_shopee_prices(raw, set(orders))

# FIX BUG: bersihkan clipboard di sini supaya teks Shopee dari STEP 1 gak
# ketinggalan di clipboard dan kebaca ulang secara gak sengaja saat scan mulai.
pyperclip.copy("")

# =============================
# STEP 2
# =============================
print("\nSTEP 2:")
print("Klik kolom MEMO (baris paling atas)")
print("Cursor harus berkedip")
input("ENTER jika siap...")

print("\n⏳ Persiapan scan dimulai...")

for i in range(5, 0, -1):
    for j in range(4):
        spin = spinner[j % len(spinner)]
        print(f"{spin} Mulai dalam {i} detik...", end="\r")
        time.sleep(0.25)

print("🚀 MULAI SCAN!            \n")

# =============================
# RESET KE ATAS (ANTI START TENGAH)
# =============================
for _ in range(20):
    pyautogui.press('up')
    time.sleep(0.01)

# FIX BUG: kasih jeda ekstra + bersihkan clipboard lagi sebelum loop utama
# mulai, supaya F2+Ctrl+C pertama di iterasi ke-0 benar-benar membaca cell
# yang baru (bukan sisa clipboard lama).
pyperclip.copy("")
time.sleep(0.3)

# OBSERVABILITY — metrik run ini. `retry` diisi dari safe_copy (pakai
# metrik=metrik di tiap pemanggilan); sisanya dihitung di bawah.
metrik = {
    "diproses": len(orders),
    "sukses": 0,
    "not_found": 0,
    "retry": 0,
    "cek_manual": 0,
    "error": 0,
    "foto_retry": 0,  # internal: batas foto retry (bukan metrik tampil)
}
start_time = time.time()

found = set()
app_prices = {}
same_count = 0
last_kode = ""

duplicate_scan = set()

# jumlah kemunculan kode selama scan
scan_count = {}

# kode terakhir yang dibaca
last_row_kode = None

end_buffer = deque(maxlen=6)

for i in range(MAX_LOOP):
    try:
        spin = spinner[i % len(spinner)]
        print(f"{spin} Scanning... Ketemu: {len(found)}/{len(orders)}", end="\r")

        # =============================
        # COPY DATA (FIX: pakai safe_copy biar gak kebaca clipboard basi)
        # =============================
        pyautogui.press('f2')
        time.sleep(0.25)   # 🔥 penting

        text = safe_copy(delay=FAST, metrik=metrik)
        if text is None:
            # gagal total baca clipboard, anggap kosong & skip iterasi ini
            pyautogui.press('esc')
            time.sleep(0.1)
            pyautogui.press('down')
            time.sleep(DELAY)
            continue
        text = text.strip()

        match = re.search(r'26[A-Z0-9]{12,13}', text)
        kode = match.group(0) if match else ""

        if kode:
            # =============================
            # 🔥 FIX: DETEKSI END TABLE
            # =============================
            end_buffer.append(kode)

            if len(end_buffer) == 6 and len(set(end_buffer)) == 1:
                print(f"\n⛔ END OF TABLE TERDETEKSI")
                print(f"Stop di: {kode}")
                break

            # =============================
            # DETEKSI DUPLIKAT VALID
            # =============================
            if kode in orders:

                # hanya hitung jika pindah baris
                if kode != last_row_kode:

                    scan_count[kode] = scan_count.get(kode, 0) + 1

                    if scan_count[kode] == 2:
                        duplicate_scan.add(kode)
                        print(f"\n⚠️ DUPLIKAT VALID: {kode}")

            last_row_kode = kode

            # =============================
            # DETEKSI MENTOK (LEBIH AMAN)
            # =============================
            if kode == last_kode:
                same_count += 1
            else:
                same_count = 0

            last_kode = kode

            # =============================
            # BACA HARGA + CHECKLIST (harga dibaca DULU, baru putuskan checklist)
            # =============================
            if kode in orders:

                if kode not in found:
                    found.add(kode)

                    pyautogui.press('esc')
                    time.sleep(FAST)

                    # === BACA HARGA APLIKASI (Ctrl+A baca 1 baris penuh) ===
                    # FIX BUG: sebelumnya di sini dipakai F2 + copy di CELL
                    # AKTIF, dengan asumsi cell aktif = kolom harga. Padahal
                    # cursor masih di KOLOM MEMO (tempat kita scan kode dari
                    # atas), jadi yang ke-copy ya KODE PESANAN itu sendiri
                    # lagi -> parse_price() ngambil digit-digit dari kode
                    # (mis. '260714MBKPQ4PE' -> '2607144'), bukan harga asli.
                    # Makanya di cmd kelihatan "harga aplikasi" ngaco banget
                    # gede-gede tapi angkanya mirip-mirip sama kodenya.
                    #
                    # Sekarang dibetulin pakai teknik yang SAMA kayak yang
                    # udah kepake & TERBUKTI BENER di bagian checklist di
                    # bawah: Ctrl+A buat baca satu baris penuh (tab
                    # separated), terus di-parse pakai parse_app_table()
                    # yang nyari kolom 'Memo' dan 'Nilai' dari NAMA header,
                    # jadi gak peduli cursor lagi di kolom mana.
                    pyautogui.hotkey('ctrl', 'a')
                    time.sleep(FAST)
                    row_text = safe_copy(delay=FAST, metrik=metrik)
                    pyautogui.press('esc')
                    time.sleep(FAST)

                    app_harga = None
                    if row_text is not None:
                        row_prices = parse_app_table(row_text)
                        app_harga = row_prices.get(kode)
                        if app_harga is not None:
                            app_prices[kode] = app_harga
                            if DEBUG_PRICE:
                                print(f"\n[DEBUG] {kode} -> harga aplikasi: {app_harga}")
                        elif DEBUG_PRICE:
                            print(f"\n[DEBUG] {kode} -> kode gak ketemu di hasil Ctrl+A. raw: {row_text!r}")
                    elif DEBUG_PRICE:
                        print(f"\n[DEBUG] {kode} -> Ctrl+A gagal baca clipboard (row_text kosong)")

                    # === CEK HARGA SHOPEE ===
                    shopee_harga = shopee_prices.get(kode)

                    # === PUTUSKAN CHECKLIST ===
                    if app_harga is not None and shopee_harga is not None and app_harga == shopee_harga:
                        # Harga cocok → checklist
                        pyautogui.press('left')
                        time.sleep(FAST)

                        pyautogui.press('space')
                        time.sleep(FAST)
                        pyautogui.press('space')
                        time.sleep(FAST)

                        pyautogui.press('right')
                        time.sleep(FAST)
                    else:
                        # Harga beda / tidak diketahui → SKIP checklist, langsung ke bawah
                        if app_harga is not None and shopee_harga is not None:
                            print(f"\n⚠️ SKIP CHECKLIST: {kode} (Aplikasi: {app_harga} ≠ Shopee: {shopee_harga})")
                        elif DEBUG_PRICE:
                            print(f"\n[DEBUG] {kode} -> skip checklist (harga tidak lengkap)")

            else:
                pyautogui.press('esc')
                time.sleep(0.1)

        # =============================
        # STOP semua ketemu
        # =============================
        if len(found) == len(orders):
            print(f"\n✔ Final: {len(found)}/{len(orders)} data ditemukan")
            print("🔍 Lanjut scan sebentar untuk deteksi duplikat...\n")

            for _ in range(10):
                pyautogui.press('down')
                time.sleep(DELAY)

                pyautogui.press('f2')
                time.sleep(0.2)

                extra_text = safe_copy(delay=FAST, metrik=metrik)
                if extra_text is None:
                    continue
                text = extra_text.strip()
                match = re.search(r'26[A-Z0-9]{12,13}', text)
                extra_kode = match.group(0) if match else ""

                if extra_kode in orders:
                    if extra_kode != last_row_kode:
                        scan_count[extra_kode] = scan_count.get(extra_kode, 0) + 1
                        if scan_count[extra_kode] == 2:
                            duplicate_scan.add(extra_kode)
                            print(f"\n⚠️ DUPLIKAT VALID: {extra_kode}")
                    last_row_kode = extra_kode
            break

        # =============================
        # FIX MENTOK PALSU
        # =============================
        if same_count >= 8:
            print(f"\n⛔ MENTOK TERDETEKSI (tidak ada perubahan)")
            break

        # =============================
        # NEXT ROW (LEBIH SANTAI)
        # =============================
        pyautogui.press('down')
        time.sleep(DELAY)
    except Exception as exc:
        # OBSERVABILITY: exception pas action pyautogui (termasuk
        # FailSafeException kalau mouse ke pojok layar). Foto keadaan
        # layar, catat di metrik, lalu STOP scan (break) biar hasil
        # yang udah ketemu tetap di-output & bisa dilihat user.
        metrik["error"] += 1
        if FOTO_AKTIF:
            ambil_screenshot("", "ERROR", type(exc).__name__)
        print(f"\n❌ [ERROR] iterasi ke-{i}: {type(exc).__name__}: {exc}")
        print("   Screenshot keadaan layar -> logs/screenshots/")
        print("   Scan dihentikan; hasil parsial tetap di-output di bawah.")
        break

# =============================
# OUTPUT
# =============================
valid = []
invalid = []

for o in orders:
    if o in found:
        valid.append(o)
    else:
        invalid.append(o)

print("\n" + "=" * 40)
print("HASIL VALIDASI")
print("=" * 40)

for v in valid:
    print(f"✔ {v}")

if invalid:
    # OBSERVABILITY: kode yang gak ketemu -> foto kondisi layar buat
    # diagnosa (kenapa scan berhenti / kodenya beneran gak ada).
    if FOTO_AKTIF:
        ambil_screenshot(invalid[0], "NOT_FOUND", f"{len(invalid)}_kode")
    print("\n" + "=" * 40)
    print("DATA TIDAK DITEMUKAN ❌")
    print("=" * 40)

    for x in invalid:
        print(f"- {x}")

# =============================
# OUTPUT DUPLIKAT
# =============================
if duplicate_scan:
    print("\n" + "=" * 40)
    print("DATA DUPLIKAT VALID ⚠️")
    print("=" * 40)

    for d in duplicate_scan:
        print(f"- {d}")

# =============================
# OUTPUT HARGA TIDAK COCOK
# =============================
harga_beda = []
for o in orders:
    p1 = app_prices.get(o)
    p2 = shopee_prices.get(o)
    if p1 is not None and p2 is not None and p1 != p2:
        harga_beda.append((o, p1, p2))

if harga_beda:
    print("\n" + "=" * 40)
    print("HARGA TIDAK COCOK ❌")
    print("=" * 40)

    for kode, p1, p2 in harga_beda:
        p1_str = f"Rp {p1:,}".replace(",", ".")
        p2_str = f"Rp {p2:,}".replace(",", ".")
        print(f"- {kode}  |  Aplikasi: {p1_str}  ≠  Shopee: {p2_str}")

# =============================
# TABEL HARGA (APLIKASI vs SHOPEE)
# =============================
print_price_table(orders, app_prices, shopee_prices)

# =============================
# SUMMARY
# =============================
print("\nSUMMARY:")
print(f"✔ Ketemu : {len(valid)} / {len(orders)}")
print(f"✘ Tidak  : {len(invalid)}")
if harga_beda:
    print(f"≠ Beda   : {len(harga_beda)} (tidak di-checklist)")

if len(found) == len(orders):
    print("\nSEMUA VALID + CHECKLIST SELESAI ✅")
else:
    print("\n⚠️ Scan berhenti sebelum semua data ketemu")

    print("\n📌 Pastikan data berikut ada di aplikasi:")
    for x in invalid:
        print(f"→ {x}")

# =============================
# OBSERVABILITY — RINGKASAN METRIK (CMD + logs/metrics.json)
# =============================
metrik["sukses"] = len(valid)
metrik["not_found"] = len(invalid)
# check.py gak punya konsep CEK MANUAL; yang paling mirip = kode dengan
# harga beda (skip checklist).
metrik["cek_manual"] = len(harga_beda)
metrik["durasi"] = round(time.time() - start_time, 2)
metrik["rata_per_kode"] = round(metrik["durasi"] / max(metrik["diproses"], 1), 2)
cetak_ringkasan("RINGKASAN METRIK", metrik)
path_metrik = simpan_metrik("check.py", metrik)
if path_metrik:
    print(f"  -> metrik tersimpan: {path_metrik}")

input("\nENTER untuk keluar...")