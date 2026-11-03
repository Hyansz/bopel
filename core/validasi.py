"""Validasi data clipboard sebelum dipakai bot (check.py / scan.py).

LATAR BELAKANG (bug keamanan data 2026-08-13): mode UI baca clipboard
otomatis 5 detik setelah Start. Kalau clipboard berisi teks bebas (mis.
sisa prompt/instruksi), scan.py mode kecil memperlakukan SETIAP baris
sebagai kode pesanan lalu MENGETIKnya ke kotak SEARCH aplikasi warehouse
produksi lewat pyautogui. Tidak ada validasi format sama sekali.

Modul ini = gerbang wajib:
1. `validasi_daftar_kode()` — validasi input clipboard SEBELUM dipakai
   (fail-safe: ada satu baris tidak valid -> TOLAK SEMUA + exit).
2. `cegah_ketik_tidak_aman()` — safety-net kedua, dipanggil PERSIS
   sebelum SETIAP pyautogui copy+paste ke kotak search (abort seluruh
   proses kalau ada yang mencoba ketik teks mencurigakan).
3. `preview_sebelum_mulai()` — tampilkan preview data di log/UI mode
   UI + jeda, supaya user sempat lihat & klik Stop kalau data salah.

Pola kode pesanan Shopee diambil dari logic existing (check.py
CODE_PATTERN): `26` + 12-13 karakter alfanumerik huruf besar.
"""

from __future__ import annotations

import re
import sys

# pola yang dipakai logic existing check.py (CODE_PATTERN)
KODE_PATTERN = re.compile(r"\b26[A-Z0-9]{12,13}\b")

# versi anchored: satu baris HARUS persis satu kode (strip whitespace)
KODE_ANCHORED = re.compile(r"^26[A-Z0-9]{12,13}$")

# panjang kode pesanan Shopee = 14-15 karakter ("26" + 12-13). Margin
# kecil >5 (20) buat jaga-jaga format lain yang masih wajar. Teks lebih
# panjang dari ini = PASTI bukan kode pesanan -> abort.
KODE_MAX_LEN = 20

# batas kewajaran jumlah baris daftar kode (anti paste tabel raksasa /
# teks bebas berbaris-baris panjang yang ke-salah-artikan sebagai kode).
MAX_BARIS_KODE = 10000

# preview: berapa kode pertama yang ditampilkan
PREVIEW_JUMLAH = 3


def kode_valid(kode: str) -> bool:
    """Satu kode valid? (strip dulu, harus persis pola anchored)."""
    return bool(KODE_ANCHORED.match(str(kode).strip()))


def validasi_daftar_kode(daftar: list, konteks: str = "clipboard") -> None:
    """Validasi daftar kode input. Kalau ada SATU saja yang tidak valid ->
    print pesan jelas + sys.exit(1) (STOP total, jangan lanjut, jangan
    skip baris). Fail-safe: kalau ragu, STOP.

    `daftar` string kosong -> skip (extract mode besar sudah skip baris
    kosong; mode kecil tidak pernah menghasilkan baris kosong).
    """
    if not daftar:
        print("❌ Clipboard kosong! Copy data pesanan dulu, lalu klik Start lagi.")
        sys.exit(1)

    if len(daftar) > MAX_BARIS_KODE:
        print(
            f"❌ Format clipboard tidak dikenali sebagai data pesanan: "
            f"{len(daftar)} baris (melebihi batas {MAX_BARIS_KODE}).\n"
            "   Cek ulang copy Anda — jangan copy teks bebas/prompt ke clipboard."
        )
        sys.exit(1)

    for baris in daftar:
        teks = str(baris).strip()
        if not teks:
            continue
        if len(teks) > KODE_MAX_LEN or not kode_valid(teks):
            print(
                f"❌ Format clipboard tidak dikenali sebagai data pesanan, cek ulang copy Anda.\n"
                f"   Baris bermasalah ({konteks}): {teks[:80]!r}\n"
                "   Kode pesanan Shopee format: '26' + 12-13 huruf/angka (mis. 2608113PS5JD38).\n"
                "   Kalau ada satu baris salah, SEMUA data ditolak (fail-safe) — proses DISTOP."
            )
            sys.exit(1)


def cegah_ketik_tidak_aman(teks, konteks: str = "") -> str:
    """Safety-net sebelum SETIAP ketik/paste ke GUI aplikasi warehouse.

    Return teks (strip) kalau aman; kalau tidak -> print error jelas +
    sys.exit(1) (ABORT SELURUH PROSES — tanda bug logic/data di hulu).
    """
    teks = str(teks).strip()
    if not teks:
        print(f"❌ ABORT: percobaan mengetik teks KOSONG ke aplikasi ({konteks}). Proses dihentikan.")
        sys.exit(1)
    if len(teks) > KODE_MAX_LEN or not kode_valid(teks):
        print(
            f"❌ ABORT: teks akan diketik ke aplikasi TIDAK dikenali sebagai kode pesanan "
            f"({konteks}): {teks[:80]!r} — panjang {len(teks)} karakter (maks {KODE_MAX_LEN}).\n"
            "   Ini tanda kuat ada bug logic/salah data di hulu. SELURUH PROSES DIHENTIKAN."
        )
        sys.exit(1)
    return teks


def preview_sebelum_mulai(daftar: list) -> None:
    """Preview singkat data yang akan diproses (dipanggil SEBELUM bot
    menyentuh aplikasi warehouse). Return jumlah kode valid."""
    total = len(daftar)
    contoh = ", ".join(str(x).strip() for x in daftar[:PREVIEW_JUMLAH])
    sisa = max(total - PREVIEW_JUMLAH, 0)
    teks_sisa = f" (+{sisa} lainnya)" if sisa else ""
    print(
        f"\n📋 PREVIEW DATA (mode UI): terdeteksi {total} kode pesanan.\n"
        f"   Contoh {min(total, PREVIEW_JUMLAH)} baris pertama: {contoh}{teks_sisa}\n"
        "   Kalau data ini SALAH, klik STOP di UI sekarang — bot belum menyentuh aplikasi."
    )