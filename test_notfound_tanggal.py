"""Self-check FIX: kolom TGL CAIR utk baris "TIDAK ADA FAKTUR" (Not Found).

Regresi dari bug produksi nyata: tanggal_dilepas_map (Excel mutasi Shopee)
TIDAK bergantung pada hasil scan aplikasi, tapi blok not_found di scan.py /
scan_bulanan.py meng-hardcode "tanggal": "" -> TGL CAIR selalu kosong utk
kode yang Not Found di app.

Jalan: python test_notfound_tanggal.py
Dicek via AST extract dari scan.py DAN scan_bulanan.py (salinan terpisah —
keduanya diuji supaya tidak drift): literal dict baris not_found harus
mengambil tanggal dari tanggal_dilepas_map.get(nomor, ...), bukan string
kosong hardcode. Plus eksekusi literal tsb terhadap 2 kode bukti nyata
user sebagai simulasinya (kode dgn tanggal berarti = seolah-olah Not Found).

Bukti nyata (data produksi user):
  - 2608258E5HBPH9 -> Tanggal Dana Dilepaskan 2026-08-29
  - 2607303HMEMTDG -> Tanggal Dana Dilepaskan 2026-08-10
"""

import ast
import pathlib

# (kode, tanggal_dilepas dari Excel)  — kode sengaja dianggap Not Found di app
BUKTI = [
    ("2608258E5HBPH9", "2026-08-29"),
    ("2607303HMEMTDG", "2026-08-10"),
]

imports = {"tanggal_dilepas_map": {}}


def ekstrak_blok_notfound(path):
    src = pathlib.Path(path).read_text(encoding="utf-8")
    tree = ast.parse(src)
    for n in ast.walk(tree):
        if (isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                and n.func.attr == "append" and n.args
                and isinstance(n.args[0], ast.Dict)):
            keys = [ast.literal_eval(k) for k in n.args[0].keys]
            if keys and keys[0] == "nomor" and "status" in keys and ast.literal_eval(n.args[0].values[keys.index("status")]) == "Not Found":
                yield n.args[0]


for sumber in ("scan.py",):
    blok = list(ekstrak_blok_notfound(sumber))
    # Harus ada dua: satu di resume-checkpoint, satu di loop scan utama.
    assert len(blok) == 2, f"{sumber}: jumlah blok Not Found = {len(blok)}, harus 2"
    for lit in blok:
        keys = [ast.literal_eval(k) for k in lit.keys]
        # Ekspresi field 'tanggal' TIDAK boleh hardcode string kosong.
        expr = lit.values[keys.index("tanggal")]
        assert not (isinstance(expr, ast.Constant) and expr.value == ""), \
            f"{sumber}: tanggal masih hardcode '' -> BUG BELUM DIFIX"
        # Harus membaca dari tanggal_dilepas_map (direct get atau
        # get(...) or <checkpoint fallback>) — bukan string kosong.
        assert "tanggal_dilepas_map" in ast.dump(expr), \
            f"{sumber}: tanggal tidak diambil dari tanggal_dilepas_map -> {ast.dump(expr)}"
        # Eksekusi literal dgn mock map berisi 2 kode bukti -> tanggal terisi.
        imports["tanggal_dilepas_map"].update(dict(BUKTI))
        for k, _tgl in BUKTI:
            got = eval(compile(ast.Expression(lit), f"{sumber}:{k}", "eval"), {**imports, "nomor": k})
            assert got["tanggal"] != "", f"{sumber}: {k} TGL CAIR kosong -> BUG"
        # Tanggal yg dipakai = tanggal_dilepas_map (sumber live), bukan dari
        # checkpoint. Pastikan nilai tertangkap benar.
        got = eval(compile(ast.Expression(lit), f"{sumber}", "eval"), {**imports, "nomor": BUKTI[0][0]})
        assert got["tanggal"] in {t for _k, t in BUKTI}, f"{sumber}: tanggal salah"

    # Verifikasi nilai persis utk 2 kode bukti.
    imports["tanggal_dilepas_map"].clear()
    for k, tgl in BUKTI:
        imports["tanggal_dilepas_map"][k] = tgl
    got = eval(compile(ast.Expression(blok[1]), f"{sumber}:main", "eval"), {**imports, "nomor": "2608258E5HBPH9"})
    got2 = eval(compile(ast.Expression(blok[0]), f"{sumber}:resume", "eval"), {**imports, "nomor": "2608258E5HBPH9", "tanggal": ""})
    assert got["tanggal"] == "2026-08-29" and got2["tanggal"] == "2026-08-29"

print(f"test_notfound_tanggal: 2 blok x 2 file x {len(BUKTI)} kode bukti PASS")
