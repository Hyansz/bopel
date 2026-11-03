"""Helper untuk membuat caption teks clipboard (CF_UNICODETEXT)."""

from __future__ import annotations


def bangun_teks_caption(items: list[dict | str]) -> str:
    """Format caption teks untuk clipboard (CF_UNICODETEXT).

    items: list of dict (with 'name' / 'toko') atau list of store names (str).
    Menghasilkan satu baris per toko: "Shopee Ads [<nama toko>]", dipisah newline.
    """
    names = []
    for item in items:
        if isinstance(item, dict):
            n = item.get("name") or item.get("toko") or item.get("store")
            if n:
                names.append(n)
        elif isinstance(item, str):
            names.append(item)
    return "\n".join(f"Shopee Ads [{n}]" for n in names if n)
