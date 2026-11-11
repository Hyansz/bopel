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
    # Backward compatibility wrapper for mode E (all formats) using salin_paket without caption
    try:
        return salin_paket('E', paths, "").get('ok', False)
    except Exception as exc:
        print(f"[WARN] Gagal menyalin ke clipboard (wrapper): {exc}")
        return False


def salin_teks(caption: str) -> dict:
    """Salin hanya teks caption (CF_UNICODETEXT) ke clipboard."""
    import time
    import win32clipboard
    import win32con

    retry = 5
    while retry:
        try:
            win32clipboard.OpenClipboard()
            break
        except Exception:
            retry -= 1
            time.sleep(0.1)
    else:
        return {'ok': False, 'formats': []}

    try:
        win32clipboard.EmptyClipboard()
        win32clipboard.SetClipboardData(win32con.CF_UNICODETEXT, caption)
    finally:
        win32clipboard.CloseClipboard()
    return {'ok': True, 'formats': ['CF_UNICODETEXT']}


def salin_paket(mode: str, paths: list[str], caption: str = "") -> dict:
    """Salin paket data ke clipboard sesuai mode.

    mode:
        A – 1 file (CF_HDROP) + CF_UNICODETEXT
        B – 1 gambar bitmap (CF_DIB/CF_DIBV5) + CF_UNICODETEXT
        C – CF_HTML (image + <p>caption</p>) + bitmap + CF_UNICODETEXT
        D – semua format sekaligus (HTML + PNG + DIB + HDROP + text)
        E – baseline lama: semua file (CF_HDROP) + teks gabungan satu baris per toko
    paths: list of file paths (for modes A‑D expect 1 file; E may be many)
    caption: teks caption (Unicode) – untuk mode A‑D dan HTML
    Returns dict {ok: bool, formats: [str, ...]}
    """
    import time
    import win32clipboard
    import win32con

    # Helper to register custom format name and return its integer id
    def register(name: str) -> int:
        return win32clipboard.RegisterClipboardFormat(name)

    # Prepare data per format
    data_map = {}
    mode = mode.upper()
    if mode in ('A', 'D', 'E'):
        # CF_HDROP for file list (use provided paths)
        if paths:
            data_map[win32con.CF_HDROP] = make_hdrop_bytes(paths)
    if mode in ('B', 'C', 'D'):
        # Assume first path is the image file for bitmap/PNG
        if paths:
            img_path = paths[0]
            dib_bytes = png_to_dib_bytes(img_path)
            data_map[win32con.CF_DIB] = dib_bytes
            # Windows also recognises CF_DIBV5 same id as CF_DIB (legacy), keep same data
            data_map[win32con.CF_DIBV5] = dib_bytes if hasattr(win32con, 'CF_DIBV5') else dib_bytes
            # PNG custom format
            fmt_png = register('PNG')
            with open(img_path, 'rb') as f:
                data_map[fmt_png] = f.read()
    if mode in ('C', 'D'):
        # Build CF_HTML fragment with image (data URI) and paragraph caption
        if paths:
            img_path = paths[0]
            data_uri = png_to_data_uri(img_path)
            html_frag = f'<img src="{data_uri}"><p>{caption}</p>'
            # Build CF_HTML header as per CF_HTML specification
            # Header fields are byte offsets from start of the entire byte string
            # We'll use UTF-8 encoding for the header and fragment.
            version = 'Version:0.9\r\n'
            start_html = len(version.encode('utf-8'))
            # placeholders will be replaced later
            header_template = (
                f'StartHTML:{start_html:010d}\r\n'
                f'EndHTML:{{end_html:010d}}\r\n'
                f'StartFragment:{start_html + len(html_frag.encode("utf-8")):010d}\r\n'
                f'EndFragment:{{end_frag:010d}}\r\n'
            )
            # Build full HTML string
            # For simplicity we embed the fragment directly after header
            html_bytes = (version + header_template + html_frag).encode('utf-8')
            # Compute final offsets
            end_html = len(html_bytes)
            end_frag = end_html
            # Replace placeholders
            html_bytes = html_bytes.replace(b'{{end_html:010d}}', f"{end_html:010d}".encode())
            html_bytes = html_bytes.replace(b'{{end_frag:010d}}', f"{end_frag:010d}".encode())
            fmt_html = register('HTML Format')
            data_map[fmt_html] = html_bytes
    # Add Unicode text only for modes that require it (A, C, D)
    if caption and mode in ('A', 'C', 'D'):
        data_map[win32con.CF_UNICODETEXT] = caption

    # Open clipboard with retry if busy
    retry = 5
    while retry:
        try:
            win32clipboard.OpenClipboard()
            break
        except Exception:
            retry -= 1
            time.sleep(0.1)
    else:
        return {'ok': False, 'formats': []}

    try:
        win32clipboard.EmptyClipboard()
        # Set each format data
        for fmt, blob in data_map.items():
            win32clipboard.SetClipboardData(fmt, blob)
    finally:
        win32clipboard.CloseClipboard()

    # Enumerate formats present (need to open clipboard again)
    fmt_list = []
    try:
        win32clipboard.OpenClipboard()
        fmt = 0
        while True:
            fmt = win32clipboard.EnumClipboardFormats(fmt)
            if not fmt:
                break
            # Try to get human readable name
            name = win32clipboard.GetClipboardFormatName(fmt)
            if not name:
                # Map known standard formats
                if fmt == win32con.CF_HDROP:
                    name = 'CF_HDROP'
                elif fmt == win32con.CF_UNICODETEXT:
                    name = 'CF_UNICODETEXT'
                elif fmt == win32con.CF_DIB:
                    name = 'CF_DIB'
                elif hasattr(win32con, 'CF_DIBV5') and fmt == win32con.CF_DIBV5:
                    name = 'CF_DIBV5'
                else:
                    # custom registered formats have names via RegisterClipboardFormat
                    name = win32clipboard.GetClipboardFormatName(fmt) or str(fmt)
            fmt_list.append(name)
    except Exception:
        pass
    finally:
        try:
            win32clipboard.CloseClipboard()
        except Exception:
            pass
    # Build list of format names we set (since enumeration may fail in headless env)
    fmt_list = []
    for fmt in data_map.keys():
        name = None
        try:
            name = win32clipboard.GetClipboardFormatName(fmt)
        except Exception:
            pass
        if not name:
            if fmt == win32con.CF_HDROP:
                name = 'CF_HDROP'
            elif fmt == win32con.CF_UNICODETEXT:
                name = 'CF_UNICODETEXT'
            elif fmt == win32con.CF_DIB:
                name = 'CF_DIB'
            elif hasattr(win32con, 'CF_DIBV5') and fmt == win32con.CF_DIBV5:
                name = 'CF_DIBV5'
            else:
                # Custom registered formats have names via RegisterClipboardFormat
                name = win32clipboard.GetClipboardFormatName(fmt) or str(fmt)
        fmt_list.append(name)
    return {'ok': True, 'formats': fmt_list}

