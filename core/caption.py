"""Helper untuk membuat caption teks clipboard (CF_UNICODETEXT)."""

import os


def bangun_teks_caption(items: list[dict | str]) -> str:
    """Format caption teks untuk clipboard (CF_UNICODETEXT).

    items: list of dict (dengan 'name', 'toko', atau 'store') atau list of store names (str).
    Menghasilkan satu baris per toko: "Shopee Ads <Nama Toko> <MM> <DD> <YYYY>".
    """
    from datetime import datetime
    today = datetime.now()
    month = f"{today.month:02d}"
    day = f"{today.day:02d}"
    year = f"{today.year:04d}"
    names = []
    # Resolve each item to a store name using the shared helper
    from core.store_name import nama_toko_dari_file
    for item in items:
        if isinstance(item, dict):
            n = item.get("name") or item.get("toko") or item.get("store")
            if n:
                names.append(n)
        elif isinstance(item, str):
            # If the string looks like a filename, try to extract store name
            if os.path.sep in item or '_' in item:
                extracted = nama_toko_dari_file(item)
                names.append(extracted if extracted else item)
            else:
                names.append(item)
    return "\n".join(f"Shopee Ads {n} {month} {day} {year}" for n in names if n)
