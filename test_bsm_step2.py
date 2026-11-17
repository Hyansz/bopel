import pytest
import sys
import time
from decimal import Decimal
import check_new
import pyperclip


def test_match_numbers_definition(monkeypatch):
    # Tes definisi baru ringkasan angka: Total = jumlah kode Shopee
    fake_res = {
        "total_baris_app": 55,
        "total_shopee": 2,
        "found": [{"baris": 1, "kode": "26000000000001", "invoice": "x", "net": 100, "nilai": Decimal("100")}] * 2,
        "missing": ["26000000000002"],
        "extra": [{}],
        "parser_problems": []
    }
    monkeypatch.setattr(check_new.bsm_match, "match_codes", lambda *a: fake_res)
    monkeypatch.setattr(check_new.bsm_match, "print_report", lambda *a: None)
    monkeypatch.setattr(check_new, "bsm_window_exists", lambda: True)
    monkeypatch.setattr(check_new, "STEP2_MODE", "off")
    monkeypatch.setattr(check_new.win32gui, "GetWindowRect", lambda hwnd: (0, 0, 1000, 800))
    monkeypatch.setattr(check_new.pyautogui, "click", lambda x, y: None)
    monkeypatch.setattr(check_new.pyautogui, "hotkey", lambda *a: None)
    monkeypatch.setattr(check_new, "safe_copy", lambda *a, **kw: "data")
    monkeypatch.setattr(check_new.pyautogui, "press", lambda *a: None)
    monkeypatch.setattr(pyperclip, "paste", lambda: "26000000000001 26000000000002")
    # Simulate Shopee prices for the fake codes
    monkeypatch.setattr(check_new, "parse_shopee_prices", lambda raw, orders: {"26000000000001": 100})

    printed = []
    monkeypatch.setattr("builtins.print", lambda *args, **kwargs: printed.append(" ".join(str(x) for x in args)))

    with pytest.raises(SystemExit) as exc_info:
        check_new.main()
    assert exc_info.value.code == 0

    combined_printed = " ".join(printed)
    assert "Total: 2" in combined_printed
    assert "Ketemu: 2" in combined_printed
    assert "Tidak: 1" in combined_printed
