import pytest
import sys
import time
import check_new
import pyperclip


def test_match_numbers_definition(monkeypatch):
    # Tes definisi baru ringkasan angka: Total = jumlah kode Shopee
    fake_res = {
        "total_baris_app": 55,
        "total_shopee": 6,
        "found": [{"baris": 1, "kode": "A", "invoice": "x", "net": 100}] * 5,
        "missing": ["B"],
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
    monkeypatch.setattr(pyperclip, "paste", lambda: "2611027AA02JVM 261106KHN0VWSB")

    printed = []
    monkeypatch.setattr("builtins.print", lambda *args, **kwargs: printed.append(" ".join(str(x) for x in args)))

    with pytest.raises(SystemExit) as exc_info:
        check_new.main()
    assert exc_info.value.code == 0

    assert "Total: 6" in printed
    assert "Ketemu: 5 / 6" in printed
    assert "Tidak: 1" in printed
