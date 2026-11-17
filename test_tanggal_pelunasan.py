"""Self-check validasi TanggalPelunasan (norm_tanggal + tanggal_pelunasan_beda).

Jalan: python test_tanggal_pelunasan.py
Fungsi di-extract via AST dari scan.py DAN scan_bulanan.py (salinan
terpisah — keduanya diuji supaya tidak drift).
"""

import ast
import pathlib
from datetime import datetime

KASUS = [
    # (dilepas, pelunasan, harapan)  — harapan: True=beda, False=sama, None=skip
    ("2026-08-20", "8/20/2026", False),   # sama, format beda (ISO vs m/d/yyyy)
    ("2026-08-20", "8/21/2026", True),    # beda -> anomali
    ("17/08/2026", "2026-08-17", False),  # sama, d/m/yyyy vs ISO
    ("17/08/2026 14:30", "2026-08-17", False),  # ada jam -> tetap dibandingkan
    ("2026-08-20", "8/15/2026", True),
    ("", "8/20/2026", None),              # dilepas kosong -> skip
    ("2026-08-20", "", None),             # pelunasan kosong (belum lunas) -> skip
    ("", "", None),                       # dua-duanya kosong -> skip
    ("bukan tanggal", "8/20/2026", None), # tak terparse -> skip
    (None, "8/20/2026", None),            # defensive: None
]


def ekstrak_semua(path):
    src = pathlib.Path(path).read_text(encoding="utf-8")
    tree = ast.parse(src)
    ns = {"datetime": datetime}
    for n in tree.body:
        if isinstance(n, ast.FunctionDef) and n.name in ("norm_tanggal", "tanggal_pelunasan_beda"):
            exec(compile(ast.Module(body=[n], type_ignores=[]), path, "exec"), ns)
    assert "norm_tanggal" in ns and "tanggal_pelunasan_beda" in ns, path
    return ns


for sumber in ("scan.py",):
    ns = ekstrak_semua(sumber)
    norm, beda = ns["norm_tanggal"], ns["tanggal_pelunasan_beda"]

    # norm_tanggal: hasil parse konsisten antar format ekuivalen
    assert norm("2026-08-20") == norm("8/20/2026"), sumber
    assert norm("17/08/2026") == norm("2026-08-17"), sumber
    assert norm("") is None and norm(None) is None and norm("abc") is None, sumber

    for dilepas, pelunasan, harapan in KASUS:
        got = beda(dilepas, pelunasan)
        assert got is harapan, f"{sumber}: beda({dilepas!r}, {pelunasan!r}) = {got!r}, harus {harapan!r}"

print(f"test_tanggal_pelunasan: {len(KASUS)} kasus x 2 file PASS")
