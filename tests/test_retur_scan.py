"""Self-check: deteksi retur di scan_bulanan.py sudah sama dengan scan.py.

Latar belakang: scan_bulanan.py adalah turunan scan.py, tapi blok retur
(Excel income Shopee) tidak ikut ter-porting. Akibatnya retur yang fakturnya
sudah dihapus tercatat "TIDAK ADA FAKTUR" di mode Bulanan.

Invarian yang dijaga file ini (scan_bulanan.py saja):
  1. `deteksi_retur_shopee` + `catatan_retur_shopee` di-import dari
     core.parsing (sumber yang sama dengan scan.py:20).
  2. `deteksi_retur_shopee` dipanggil di DUA titik: baris faktur ADA dan
     baris faktur TIDAK ADA (rows is None).
  3. `not_found.append(...)` ada di cabang `else` dari deteksi titik kedua
     -> RETUR menang atas "TIDAK ADA FAKTUR".
  4. Map refund/harga-asli/tanggal-pesanan di-assign SEBELUM blok
     `if RESUME:` (anti NameError, kelas bug yang sama dengan
     tanggal_dilepas_map).
  5. Parser Excel mengembalikan 6 nilai (kode, harga, tanggal, refund,
     harga asli, tanggal pesanan) -> cocok dengan unpack di caller.

Jalan: python test_retur_bulanan.py
"""

import ast
import pathlib

SUMBER = "scan.py"
MAP_RETUR = ("refund_excel_map", "harga_asli_excel_map", "tanggal_pesanan_excel_map")
FUNGSI_PARSER = "extract_kode_dan_harga_dari_excel_shopee"


def panggilan(tree, nama):
    return [
        n for n in ast.walk(tree)
        if isinstance(n, ast.Call)
        and isinstance(n.func, ast.Name)
        and n.func.id == nama
    ]


def cek(sumber):
    tree = ast.parse(pathlib.Path(sumber).read_text(encoding="utf-8"))

    # 1. import dari core.parsing
    impor = set()
    for n in tree.body:
        if isinstance(n, ast.ImportFrom) and n.module == "core.parsing":
            impor.update(a.name for a in n.names)
    for nama in ("deteksi_retur_shopee", "catatan_retur_shopee"):
        assert nama in impor, f"{sumber}: '{nama}' tidak di-import dari core.parsing"

    # 2. dua titik pemanggilan deteksi (bukan satu, bukan tiga)
    deteksi = panggilan(tree, "deteksi_retur_shopee")
    assert len(deteksi) == 2, (
        f"{sumber}: deteksi_retur_shopee dipanggil {len(deteksi)}x "
        f"(line {[c.lineno for c in deteksi]}) -> harus 2 titik"
    )
    for c in deteksi:
        assert len(c.args) == 3, f"{sumber}: line {c.lineno} bukan (refund, total, harga_asli)"
        dump = ast.dump(ast.Tuple(elts=c.args, ctx=ast.Load()))
        for nama in ("refund_excel_map", "harga_excel_map", "harga_asli_excel_map"):
            assert nama in dump, f"{sumber}: line {c.lineno} tidak pakai {nama}"

    # 3. cabang `else` titik kedua = not_found -> RETUR diprioritaskan
    titik_notfound = []
    for n in ast.walk(tree):
        if isinstance(n, ast.If) and "deteksi_retur_shopee" in ast.dump(n.test):
            for x in ast.walk(ast.Module(body=n.orelse, type_ignores=[])):
                if (isinstance(x, ast.Call)
                        and isinstance(x.func, ast.Attribute)
                        and x.func.attr == "append"
                        and isinstance(x.func.value, ast.Name)
                        and x.func.value.id == "not_found"):
                    titik_notfound.append(n.lineno)
    assert titik_notfound, (
        f"{sumber}: tidak ada 'not_found.append' di cabang else deteksi retur "
        f"-> retur bisa ketelan TIDAK ADA FAKTUR"
    )

    # 4. map retur dideklarasikan sebelum blok checkpoint
    blok_checkpoint = [
        n.lineno for n in tree.body
        if isinstance(n, ast.If) and isinstance(n.test, ast.Name) and n.test.id == "RESUME"
    ]
    assert len(blok_checkpoint) == 1, f"{sumber}: blok `if RESUME:` tidak tunggal"
    for nama in MAP_RETUR:
        assign = [
            t.lineno for t in ast.walk(tree)
            if isinstance(t, ast.Assign)
            and any(isinstance(x, ast.Name) and x.id == nama for x in t.targets)
        ]
        assert assign, f"{sumber}: {nama} tidak pernah di-assign"
        assert min(assign) < blok_checkpoint[0], (
            f"{sumber}: {nama} di-assign line {min(assign)} SETELAH blok checkpoint "
            f"line {blok_checkpoint[0]} -> NameError"
        )

    # 5. parser mengembalikan 6 nilai
    parser = [
        n for n in ast.walk(tree)
        if isinstance(n, ast.FunctionDef) and n.name == FUNGSI_PARSER
    ]
    assert len(parser) == 1, f"{sumber}: {FUNGSI_PARSER} tidak tunggal"
    returns = [
        n for n in ast.walk(parser[0])
        if isinstance(n, ast.Return) and isinstance(n.value, ast.Tuple)
    ]
    assert returns, f"{sumber}: {FUNGSI_PARSER} tidak return tuple"
    panjang = {len(r.value.elts) for r in returns}
    assert panjang == {6}, (
        f"{sumber}: {FUNGSI_PARSER} return {panjang} nilai -> caller unpack 6"
    )

    print(f"  {sumber}: 2 titik deteksi (line {[c.lineno for c in deteksi]}), "
          f"retur > not_found, map sebelum checkpoint (line {blok_checkpoint[0]})")


cek(SUMBER)
print("test_retur_scan: PASS")
