import sys
from pathlib import Path
import pytest
import app

def test_apply_window_icon_success(monkeypatch):
    """Test _apply_window_icon when icon exists and hwnd is found."""
    # Mock sys.platform to win32
    monkeypatch.setattr(sys, "platform", "win32")

    # Mock Path.exists to return True
    monkeypatch.setattr(Path, "exists", lambda self: True)

    class MockUser32:
        def __init__(self):
            self.send_message_calls = []

        def FindWindowW(self, lpClassName, lpWindowName):
            return 12345

        def LoadImageW(self, hInst, lpszName, uType, cxDesired, cyDesired, fuLoad):
            return 99999

        def SendMessageW(self, hWnd, Msg, wParam, lParam):
            self.send_message_calls.append((hWnd, Msg, wParam, lParam))
            return 0

    mock_user32 = MockUser32()

    class MockWindll:
        user32 = mock_user32

    class MockCtypes:
        windll = MockWindll()
        def __init__(self):
            pass

    import ctypes
    monkeypatch.setattr(app, "sys", sys)

    # Mock ctypes.windll.user32 in app or via ctypes patch
    monkeypatch.setattr(ctypes, "windll", MockWindll())

    app._apply_window_icon()

    # Should call SendMessageW with WM_SETICON (0x0080) twice (ICON_SMALL=0, ICON_BIG=1)
    wm_seticon = 0x0080
    seticon_calls = [c for c in mock_user32.send_message_calls if c[1] == wm_seticon]
    assert len(seticon_calls) == 2
    assert seticon_calls[0][2] == 0  # ICON_SMALL
    assert seticon_calls[1][2] == 1  # ICON_BIG


def test_apply_window_icon_missing_ico(monkeypatch):
    """Test _apply_window_icon when .ico file does not exist (should not raise)."""
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setattr(Path, "exists", lambda self: False)

    # Should return early without error
    app._apply_window_icon()


def test_apply_window_icon_no_hwnd(monkeypatch):
    """Test _apply_window_icon when window hwnd is not found (should not raise)."""
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setattr(Path, "exists", lambda self: True)

    class MockUser32:
        def FindWindowW(self, lpClassName, lpWindowName):
            return 0  # Not found

    class MockWindll:
        user32 = MockUser32()

    import ctypes
    monkeypatch.setattr(ctypes, "windll", MockWindll())

    app._apply_window_icon()
