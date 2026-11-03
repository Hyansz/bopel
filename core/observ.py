"""Observability helpers buat tools automation (scan.py / check.py).

Isi:
1. ambil_screenshot()  — auto-foto layar tiap event kegagalan ke
   logs/screenshots/. Nama file berisi timestamp + kode pesanan + jenis
   event biar gampang ditelusuri.
2. tunggu_grid_respon()— polling PENGganti sleep statis: tunggu sampai
   clipboard berisi hasil copy (bukan sisa kosong) dengan batas timeout.
   Dipakai di titik paling rawan NOT FOUND palsu (setelah search Enter /
   setelah turun ke baris data).
3. simpan_metrik()     — ringkasan metrik tiap run di-append 1 baris JSON
   ke logs/metrics.json.
4. cetak_ringkasan()   — cetak metrik ke CMD dengan format rapi.

Semua fungsi aman dipanggil kapan aja: gagal (mis. headless tanpa display
-> pyautogui.screenshot() error) => return None / print warning, TIDAK
pernah menimbulkan exception di caller.
"""

from __future__ import annotations

import json
import re
import time
from datetime import datetime
from pathlib import Path

_BASE = Path(__file__).resolve().parent.parent
_SCREENSHOT_DIR = _BASE / "logs" / "screenshots"
_METRICS_FILE = _BASE / "logs" / "metrics.json"

# ── Cap global foto per run (fix banjir 2026-09-12) ─────────────────────
# Sebelumnya cuma RETRY/COPY_GAGAL yang punya batas (FOTO_RETRY_BATAS di
# tiap tool); RE_SEARCH / NOT_FOUND final / ERROR TIDAK — nyata: 2244 PNG,
# RE_SEARCH 1031 + NOT_FOUND 1035. Semua event share SATU budget di sini
# (choke point: semua caller scan.py/scan_bulanan.py/check.py lewat
# ambil_screenshot), jadi 3 file tool tak perlu diedit satupun. Angka 5
# sengaja SAMA dengan FOTO_RETRY_BATAS (core ini tak boleh import modul tool
# — circular; biar konsisten ubah di dua tempat kalau mau naikkan).
_BUDGET_FOTO_PER_RUN = 5
_foto_pakai = 0            # counter foto yang BENAR-BENAR tersimpan di run ini
_foto_fp_terakhir = None   # fingerprint frame terakhir yang disimpan (dedupe)
_foto_budget_diingatkan = False


def foto_slot_tersedia(fp: str) -> bool:
    """Gate foto run: True kalau budget belum habis DAN fp bukan frame
    identik berturut-turut (burst COPY_GAGAL/RETRY merekam layar yang sama
    5x). Kalau True, slot terpakai (counter naik, fp terakhir di-update).
    Murni + deterministik -> bisa di-assert di self-check (__main__)."""
    global _foto_pakai, _foto_fp_terakhir
    if _foto_pakai >= _BUDGET_FOTO_PER_RUN:
        return False
    if fp == _foto_fp_terakhir:
        return False
    _foto_pakai += 1
    _foto_fp_terakhir = fp
    return True


def _sanitize(teks, maks=60):
    """Nama file aman: cuma huruf/angka/underscore/hyphen/titik."""
    bersih = re.sub(r"[^A-Za-z0-9_.-]", "_", str(teks))
    return (bersih[:maks] or "unknown")


def ambil_screenshot(kode: str, event: str, extra: str = "") -> str | None:
    """Foto layar penuh. Return path PNG, None kalau gagal (mis. headless).

    Nama file: <YYYYMMDD_HHMMSS_mmm>_<EVENT>_<kode>[_extra].png
    - timestamp pakai milidetik biar 2 event di detik yang sama gak
      tabrakan namanya.
    - kode pesanan DISANITIZE (kode asli kadang ada karakter aneh).
    """
    try:
        import hashlib
        import pyautogui
        _SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
        img = pyautogui.screenshot()
        fp = hashlib.md5(img.tobytes()).hexdigest()
        if not foto_slot_tersedia(fp):
            if _foto_pakai >= _BUDGET_FOTO_PER_RUN and not _foto_budget_diingatkan:
                _foto_budget_diingatkan = True
                print(f"  [screenshot] budget {_BUDGET_FOTO_PER_RUN}/run tercapai — "
                      "event berikutnya difoto SKIP (naikkan: core/observ.py _BUDGET_FOTO_PER_RUN)")
            return None
        ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
        nama = f"{ts}_{_sanitize(event)}_{_sanitize(kode)}"
        if extra:
            nama += f"_{_sanitize(extra)}"
        path = _SCREENSHOT_DIR / f"{nama}.png"
        img.save(str(path))
        return str(path)
    except Exception as exc:
        try:
            print(f"  [screenshot] GAGAL ({event}): {type(exc).__name__}: {exc}")
        except Exception:
            pass
        return None


def tunggu_grid_respon(timeout: float = 1.5, interval: float = 0.05) -> bool:
    """Polling pengganti sleep statis (DELAY_AFTER_ENTER / DELAY_AFTER_DOWN).

    Cara kerja: kosongkan clipboard -> Ctrl+C -> baca ulang. Kalau hasil
    copy BUKAN kosong berarti aplikasi sudah merespons (grid ke-load /
    baris ke-copy). Loop sampai dapet atau timeout.

    Return True kalau dapet data, False kalau timeout (caller lanjut
    seperti biasa -- retry & re-search di find_data_row yang mutusin NOT
    FOUND bener/palsu).

    Kenapa aman: isi clipboard DIKOSONGKAN dulu tiap iterasi, jadi yang
    dianggap "respon" beneran hasil copy baru (bukan sisa data basi).
    Kenapa cepat: grid yang responsif kebaca di iterasi pertama (~0.1s),
    gak perlu nunggu delay statis penuh.
    """
    import pyautogui
    import pyperclip
    mulai = time.time()
    while time.time() - mulai < timeout:
        try:
            pyperclip.copy("")
            pyautogui.hotkey("ctrl", "c")
        except Exception:
            return False
        time.sleep(interval)
        try:
            if pyperclip.paste().strip():
                return True
        except Exception:
            return False
    return False


# Label tampilan ringkas di CMD (dipakai cetak_ringkasan). Key-nya harus
# SAMA dengan key yang dipakai skrip (scan.py/check.py) di dict metrik.
_LABEL_METRIK = {
    "diproses": "Total kode diproses",
    "sukses": "Sukses",
    "not_found": "Not Found",
    "retry": "Retry terpicu (klip kosong/header doang)",
    "research": "Re-search konfirmasi",
    "cek_manual": "CEK MANUAL / skip checklist",
    "error": "Exception/error",
    "baris_terpecah": "Baris grid terpecah (newline di sel) — direkonstruksi",
    "durasi": "Durasi total (detik)",
    "rata_per_kode": "Waktu rata-rata per kode (detik)",
}


def cetak_ringkasan(judul: str, metrik: dict) -> None:
    """Cetak ringkasan metrik ke CMD. Baris yang gak dikenal labelnya
    dilewati (biar skrip bebas nambah field internal tanpa tampil)."""
    print("\n" + "=" * 60)
    print(judul)
    print("=" * 60)
    for k, v in metrik.items():
        label = _LABEL_METRIK.get(k)
        if label:
            print(f"  {label:<42}: {v}")
    print()


def simpan_metrik(tool: str, metrik: dict) -> str | None:
    """Append 1 baris JSON metrik run ke logs/metrics.json (riwayat semua
    run, urutan waktu). Return path file, None kalau gagal."""
    try:
        _METRICS_FILE.parent.mkdir(parents=True, exist_ok=True)
        baris = {
            "waktu": datetime.now().isoformat(timespec="seconds"),
            "tool": tool,
            **metrik,
        }
        with open(_METRICS_FILE, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(baris, ensure_ascii=False) + "\n")
        return str(_METRICS_FILE)
    except Exception as exc:
        try:
            print(f"  [metrik] GAGAL disimpan: {type(exc).__name__}: {exc}")
        except Exception:
            pass
        return None


if __name__ == "__main__":
    def _self_check():
        global _foto_pakai, _foto_fp_terakhir
        _foto_pakai = 0
        _foto_fp_terakhir = None
        assert foto_slot_tersedia("frame-a")                      # 1/5
        assert not foto_slot_tersedia("frame-a")                  # identik -> skip
        for i in "bcde":
            assert foto_slot_tersedia(f"frame-{i}")               # 2/5..5/5
        assert _foto_pakai == 5
        assert not foto_slot_tersedia("frame-f")                  # budget habis
        assert not foto_slot_tersedia("frame-a")                  # budget habis menang
        print("OK observ.py self-check (cap 5 + dedupe)")
    _self_check()