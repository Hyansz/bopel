"""Helper untuk membuat clipboard clipboard payload (CF_HDROP & CF_UNICODETEXT / CF_DIB) untuk TUI & bridge."""

from __future__ import annotations

import ctypes
from ctypes import wintypes


def _dropfiles_header() -> bytes:
    """Header DROPFILES (20 byte) untuk CF_HDROP: offset data + fWide=1
    (path berikutnya UTF-16)."""
    class DROPFILES(ctypes.Structure):
        _fields_ = [
            ("pFiles", wintypes.DWORD),
            ("pt", wintypes.POINT),
            ("fNC", wintypes.BOOL),
            ("fWide", wintypes.BOOL),
        ]

    df = DROPFILES()
    df.pFiles = ctypes.sizeof(df)
    df.fWide = True
    return bytes(df)


def make_hdrop_bytes(paths: list[str]) -> bytes:
    """Bangun payload CF_HDROP (file drop) dari daftar path file."""
    if not paths:
        raise ValueError("butuh minimal 1 path file")
    data = ("\0".join(paths) + "\0").encode("utf-16-le") + b"\0\0"
    return _dropfiles_header() + data


def png_to_dib_bytes(path) -> bytes:
    """Baca gambar (PNG/JPG/etc) → byte DIB siap kirim ke clipboard CF_DIB."""
    from io import BytesIO
    from PIL import Image
    img = Image.open(path).convert("RGB")
    with BytesIO() as buf:
        img.save(buf, "BMP")
        data = buf.getvalue()
    if data[:2] != b"BM":
        raise ValueError("hasil konversi BMP tidak valid (kurang magic 'BM')")
    return data[14:]


def png_to_data_uri(path: str) -> str:
    """Convert PNG file to base64 data URI."""
    import base64
    with open(path, "rb") as f:
        encoded = base64.b64encode(f.read()).decode("utf-8")
    return f"data:image/png;base64,{encoded}"


def copy_files_with_caption(paths: list[str], caption: str = "") -> bool:
    """Salin file (CF_HDROP) dan teks caption (CF_UNICODETEXT) ke clipboard Windows sekaligus."""
    try:
        import win32clipboard
        import win32con

        win32clipboard.OpenClipboard()
        try:
            win32clipboard.EmptyClipboard()
            
            # 1. CF_HDROP
            hdrop_data = make_hdrop_bytes(paths)
            win32clipboard.SetClipboardData(win32con.CF_HDROP, hdrop_data)

            # 2. CF_UNICODETEXT
            if caption:
                win32clipboard.SetClipboardData(win32con.CF_UNICODETEXT, caption)
        finally:
            win32clipboard.CloseClipboard()
        return True
    except Exception as exc:
        print(f"⚠ Gagal menyalin ke clipboard: {exc}")
        return False
