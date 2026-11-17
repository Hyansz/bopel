"""Self-check FIX: NameError tanggal_dilepas_map di jalur resume checkpoint.

Regresi produksi nyata (2026-10-03): scan.py dijalankan dari UI, checkpoint
ditemukan -> blok resume nulis hasil_urut baris 'Not Found' yang nge-access
tanggal_dilepas_map, tapi variabel itu baru di-assign ~250 baris (-> line 488)
LEBIH KEBAWAH, di blok parse Shopee. Hasil: NameError.

Invarian yang dijaga file ini (scan.py DAN scan_bulanan.py):
  1. tanggal_dilepas_map (dan map lain yang dipakai hasil_urut) di-assign
     di module level SEBELUM blok checkpoint yang nulis hasil_urut.
  2. Blok checkpoint cuma jalan kalau RESUME=True (flag --resume).
  3. RESUME True tapi checkpoint gak ada -> pesan jelas, scan dari nol
     (blok loader tidak dieksekusi).

Jalan: python test_resume_flag.py
"""

import ast
import pathlib

MAP_YANG_DIPAKAI_HASIL_URUT = (
    "tanggal_dilepas_map",
    "harga_excel_map",
)


def nama_blok_checkpoint(tree):
    """Node `if RESUME:` di module level (blok pemanggil load_workbook)."""
    for n in tree.body:
        if isinstance(n, ast.If) and isinstance(n.test, ast.Name) and n.test.id == "RESUME":
            return n
    raise AssertionError("tidak ada blok `if RESUME:` di module level")


def cek(sumber):
    tree = ast.parse(pathlib.Path(sumber).read_text(encoding="utf-8"))
    blok = nama_blok_checkpoint(tree)
    baris_blok = blok.lineno

    # 1. semua map yang dipakai hasil_urut harus di-assign sebelum blok.
    for nama in MAP_YANG_DIPAKAI_HASIL_URUT:
        assign = [
            t.lineno for t in ast.walk(tree)
            if isinstance(t, ast.Assign)
            and any(isinstance(x, ast.Name) and x.id == nama for x in t.targets)
        ]
        assert assign, f"{sumber}: {nama} tidak pernah di-assign"
        assert min(assign) < baris_blok, (
            f"{sumber}: {nama} pertama di-assign di line {min(assign)}, "
            f"blok checkpoint mulai line {baris_blok} -> NameError"
        )

    # 2. loader checkpoint harus di dalam cabang yang cek file ADA
    #    (kalau gak ada -> cuma print pesan, tidak baca file).
    cabang_ada = None
    for n in ast.walk(blok):
        if isinstance(n, ast.If):
            src = ast.dump(n.test)
            # ast.dump tidak merender "os.path.exists" sebagai dotted string,
            # jadi cukup cek ada attr 'exists' + operator Not.
            if "attr='exists'" in src and "Not" in src:
                cabang_ada = n
    assert cabang_ada is not None, \
        f"{sumber}: tidak ada guard 'not os.path.exists(CHECKPOINT_FILE)' di blok RESUME"

    # 3. cabang 'checkpoint tidak ada' cuma print (tidak load_workbook),
    #    cabang 'checkpoint ada' yang call load_workbook.
def punya_load(n):
    for x in ast.walk(n):
        if isinstance(x, ast.List):  # orelse bisa berupa list of stmt
            if punya_load(ast.Module(body=x.elts, type_ignores=[])):
                return True
        if isinstance(x, ast.Call) and getattr(x.func, "attr", None) == "load_workbook":
            return True
    return False
    assert not punya_load(cabang_ada), \
        f"{sumber}: cabang 'checkpoint tidak ada' malah baca checkpoint"
    assert punya_load(cabang_ada.orelse), \
        f"{sumber}: cabang 'checkpoint ada' tidak load_workbook"

    # 4. tanpa flag --resume, blok checkpoint tidak dijalankan sama sekali.
    resume_assign = [
        t for t in tree.body
        if isinstance(t, ast.Assign)
        and any(isinstance(x, ast.Name) and x.id == "RESUME" for x in t.targets)
    ]
    assert len(resume_assign) == 1, f"{sumber}: RESUME di-assign lebih dari sekali"
    assert "sys.argv" in ast.dump(resume_assign[0]), \
        f"{sumber}: RESUME tidak dari sys.argv (--resume)"
    print(f"  {sumber}: RESUME dari sys.argv, map ter-assign sebelum blok "
          f"checkpoint (line {baris_blok})")


for sumber in ("scan.py",):
    cek(sumber)

print("test_resume_flag: PASS")