"""Tests for paste_macro and clipboard enhancements."""

from __future__ import annotations

import pytest
from core.paste_macro import _parse_hotkey
from core.store_name import nama_toko_dari_file
from core.clipboard import salin_teks, salin_paket


def test_parse_hotkey():
    mods, vk = _parse_hotkey("Ctrl+Alt+V")
    assert mods > 0
    assert vk > 0


def test_nama_toko_dari_file(tmp_path):
    p = tmp_path / "Toko_3___Alkes_Medika_Solo_2026-11-03.png"
    p.write_bytes(b"fake")
    name = nama_toko_dari_file(p)
    assert name == "Alkes Medika Solo"


def test_pilih_screenshot_paste_regression(tmp_path):
    from core.paste_macro import pilih_screenshot_paste
    # Create 3 files matching 2026-11-06, 12 old files, and dummies
    (tmp_path / "Toko_1___Toko_Alkes_Solo_2026-11-06_sd_2026-11-06.png").write_bytes(b"new1")
    (tmp_path / "Toko_2___Toko_Alkes_BSM_2026-11-06_sd_2026-11-06.png").write_bytes(b"new2")
    (tmp_path / "Toko_3___Alkes_Medika_Solo_2026-11-06_sd_2026-11-06.png").write_bytes(b"new3")
    
    # Dummy to be ignored
    (tmp_path / "Toko_Alpha_dummy.png").write_bytes(b"dummy")
    (tmp_path / "Fallback_dummy.png").write_bytes(b"dummy")

    items = pilih_screenshot_paste(folder=str(tmp_path))
    assert len(items) == 3
    assert "Toko 1" not in items[0][1] # Caption uses cleaned store name
    assert "Toko Alkes Solo" in items[0][1]
    assert "Toko Alkes BSM" in items[1][1]
    assert "Alkes Medika Solo" in items[2][1]


def test_pilih_screenshot_paste_empty_or_old(tmp_path):
    from core.paste_macro import pilih_screenshot_paste
    # Only old file
    (tmp_path / "Toko_1___Toko_Alkes_Solo_2026-11-03.png").write_bytes(b"old")
    items = pilih_screenshot_paste(folder=str(tmp_path))
    assert len(items) == 1
    assert "Toko Alkes Solo" in items[0][1]

    # No matching files
    empty_dir = tmp_path / "empty"
    empty_dir.mkdir()
    items_empty = pilih_screenshot_paste(folder=str(empty_dir))
    assert len(items_empty) == 0

