"""Parsing MURNI clipboard grid aplikasi (tanpa pyautogui/pyperclip/window).

Alasan modul terpisah (bukan nested di scan.py/scan_bulanan.py):
scan.py & scan_bulanan.py adalah script yang MENJALANKAN seluruh alur saat
di-import (tidak ada if __name__ == "__main__"), jadi tidak bisa di-import
untuk test. Fungsi parsing murni di sini bisa dites langsung (lihat
test_gabungkan_baris_terpecah.py), dan dipakai DARI scan.py/scan_bulanan.py.

Isi:
1. gabungkan_baris_terpecah() — rekonstruksi baris grid yang terpecah karena
   ada NEWLINE literal di dalam isi sel (kasus nyata 2026-09-12: kolom
   NoPesanan berisi "260828HCWUBC3X\\n260828HCWUBC3X"). Tanpa ini, kode yang
   BENERAN ADA di grid di-cap NOT FOUND (murni bug parsing clipboard).
2. cari_baris_memo_terpecah() — rekonstruksi + cari baris yang kolom
   Memo-nya == expected (dipakai cari_baris_memo di scan.py/scan_bulanan.py).
3. deteksi_retur_shopee() — apakah baris income Shopee itu RETUR, dari kolom
   'Jumlah Pengembalian Dana Ke Pembeli' (+ Total Penghasilan & Harga Asli
   Produk). Dipakai SEBELUM pengecekan faktur, jadi retur yang faktur
   aslinya sudah tidak ada di aplikasi tetap tercatat RETUR.
"""

from __future__ import annotations


def gabungkan_baris_terpecah(lines, jumlah_kolom_header):
    """Rekonstruksi baris grid yang KEPECAH karena ada newline literal di
    dalam sel. Return (rows, n_gabung).

    Masalahnya: `text.splitlines()` memecah SATU baris logis grid jadi DUA
    physical line kalau ada sel berisi newline:
      - line pertama: kolom-kolom awal + potongan awal isi sel bermasalah
        -> jumlah kolomnya KURANG dari header (terlihat "belum lengkap").
      - line kedua  : potongan sisa isi sel tsb + kolom-kolom setelahnya
        -> posisi kolom (mis. Memo) jadi GESER dari index aslinya.
    Akibatnya baris ditolak (`len(cols) >= jumlah` gagal) padahal Memo-nya
    cocok, dan baris kedua tidak pernah match -> kode benar-ada jadi NOT FOUND.

    Cara kerja: iterasi tiap physical line, split by tab. Selama hasil split
    BELUM mencapai jumlah_kolom_header, baris itu DIANGGAP BELUM SELESAI ->
    sambung dengan physical line berikutnya: kolom TERAKHIR baris ini dengan
    kolom PERTAMA baris berikutnya disambung pakai separator '\\n' (isi asli
    sel yang terpotong newline pulih jadi satu), sisa kolom baris berikutnya
    ditempel apa adanya. Ulangi sampai jumlah kolom mencukupi, baru dianggap
    satu baris logis selesai.

    Baris yang di ujung clipboard tidak sempat lengkap TIDAK dibuang —
    dikembalikan apa adanya, supaya pola baru yang belum ke-cover tidak hilang
    senyap (terlihat dari metrik baris_terpecah / observability).

    Return: (rows, n_gabung)
      - rows    : list[list[str]] — tiap elemen SATU baris logis grid.
      - n_gabung: berapa kali 2 physical line digabung jadi 1 baris logis
                  (0 kalau semua baris normal) — buat metrik observability.
    """
    rows = []
    sisa = []
    n_gabung = 0
    for line in lines:
        if not line.strip():
            continue
        cols = line.split('\t')
        if not sisa:
            sisa = cols[:]
        else:
            sisa[-1] = sisa[-1] + '\n' + cols[0]
            sisa.extend(cols[1:])
            n_gabung += 1
        if len(sisa) >= jumlah_kolom_header:
            rows.append(sisa)
            sisa = []
    if sisa:
        rows.append(sisa)
    return rows, n_gabung


def cari_baris_memo_terpecah(lines, expected):
    """Rekonstruksi baris terpecah lalu cari baris yang kolom 'Memo'-nya
    == expected. Murni (tanpa GUI/klipboar) — testable tanpa pyautogui.

    lines = hasil `text.splitlines()` (+ strip baris kosong) — index 0
    adalah baris HEADER. This menggantikan pencarian Memo di scan.py yang
    lama (yang memecah cuma pakai split per-line tanpa rekonstruksi).

    Return (cols, n_gabung):
      - cols   : baris logis yang Memo-nya cocok (list kolom utuh), atau
                 None kalau tidak ketemu.
      - n_gabung: jumlah gabungan baris fisik yang terjadi saat rekonstruksi
                  (observability — 0 kalau tidak ada baris terpecah).
    """
    if len(lines) < 2:
        return None, 0
    header_cols = lines[0].split('\t')
    jumlah = len(header_cols)
    rows, n_gabung = gabungkan_baris_terpecah(lines[1:], jumlah)
    try:
        memo_idx = header_cols.index('Memo')
    except ValueError:
        memo_idx = 4  # fallback posisi default kalau nama kolom beda
    for row in rows:
        if len(row) > memo_idx and row[memo_idx].strip() == expected and len(row) >= jumlah:
            return row, n_gabung
    return None, n_gabung


def _angka(v) -> int:
    """Nilai uang dari export Excel income Shopee -> int.

    Nilai di file Excel Shopee sudah POLOS ('-17100', '150000', '0', '-')
    tanpa pemisah ribuan, jadi int() cukup. Fallback float() buat保险
    kalau ada desimal ('-17100.0').
    """
    s = str(v or "").strip().replace(" ", "")
    if not s or s in ("-", "--"):
        return 0
    try:
        return int(s)
    except ValueError:
        try:
            return int(float(s))
        except ValueError:
            return 0

def deteksi_retur_shopee(refund, total, harga_asli) -> bool:
    """True = baris income Shopee itu RETUR (ada dana balik ke pembeli).

    Dua syarat (mana saja cukup), sesuai format export income Shopee:
      1. Kolom 'Jumlah Pengembalian Dana Ke Pembeli' != 0. Ini yang
         dipakai untuk kasus nyata 260907DWRKTD19 (retur PENUH):
         refund -150000, Harga Asli 150000, tapi Total Penghasilan tetap
         -17100 karena biaya -8000 + -9100 masih terpotong.
      2. Kolom refund kosong/tidak terbaca, TAPI Total Penghasilan < 0
         dan Harga Asli Produk > 0 -> retur penuh yang nominal refundnya
         tidak tercatat di baris itu (kasus refund yg di-0-kan).

    Order NORMAL (refund 0, total > 0) -> False, jadi tidak berubah.

    PENTING: fungsi ini murni, dipakai SEBELUM pengecekan faktur, supaya
    retur tanpa faktur asal pun tetap dicatat RETUR (bukan 'TIDAK ADA
    FAKTUR').
    """
    if _angka(refund) != 0:
        return True
    return _angka(total) < 0 and _angka(harga_asli) > 0


def catatan_retur_shopee(refund, total, tanpa_faktur=False) -> str:
    """Teks kolom REVISI untuk baris RETUR.

    Memuat nominal refund + total penghasilan (biaya yang tetap terpotong)
    supaya nilainya tidak hilang di laporan. `tanpa_faktur` = retur yang
    faktur aslinya sudah tidak ada di aplikasi (flag supaya user tahu ini
    kasus refund penuh tanpa sisa baris penjualan).
    """
    r = _angka(refund)
    t = _angka(total)
    parts = []
    if r != 0:
        parts.append(f"refund={r}")
    parts.append(f"total={t}")
    if tanpa_faktur:
        parts.append("retur tanpa faktur asal")
    return " | ".join(parts)

