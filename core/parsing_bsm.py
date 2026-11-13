"""Parser untuk halaman Inventory BSM versi baru.
Menerima teks halaman (dari Ctrl+A + Ctrl+C) dan kode pesanan yang dicari,
mengembalikan (rows, kolom_idx, halaman_valid).
"""
import re

def parse_bsm_page(text: str, expected_code: str):
    """Parse teks halaman Inventory BSM."""
    if not text or not text.strip():
        return [], {}, False

    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if len(lines) < 1:
        return [], {}, False

    header_idx = -1
    cols_map = {}
    expected_headers = ["nomor", "tanggal", "memo", "salesman", "customer", "total", "retur", "status", "pelunasan"]

    for i, line in enumerate(lines):
        parts = [p.strip() for p in re.split(r'\t+|\s{2,}', line)]
        lower_parts = [p.lower() for p in parts]
        matches = sum(1 for h in expected_headers if any(h in p for p in lower_parts))
        if matches >= 2 or "memo" in lower_parts or "pesanan" in lower_parts:
            header_idx = i
            for idx, p in enumerate(parts):
                pl = p.lower()
                if "nomor" in pl or "faktur" in pl: cols_map["nomor"] = idx
                elif "tanggal" in pl and "cair" not in pl and "lepas" not in pl: cols_map["tanggal"] = idx
                elif "memo" in pl or "pesanan" in pl or "kode" in pl: cols_map["memo"] = idx
                elif "sales" in pl: cols_map["salesman"] = idx
                elif "customer" in pl or "pelanggan" in pl or "toko" in pl: cols_map["customer"] = idx
                elif "total" in pl or "harga" in pl or "nilai" in pl: cols_map["total"] = idx
                elif "retur" in pl: cols_map["retur"] = idx
                elif "status" in pl or "bayar" in pl: cols_map["status"] = idx
                elif "pelunasan" in pl: cols_map["pelunasan"] = idx
            break

    print(f"[DEBUG PARSING] Cols Map: {cols_map}")

    if header_idx == -1:
        cols_map = {
            "nomor": 0, "tanggal": 3, "memo": 2, "salesman": 8,
            "customer": 9, "total": 10, "retur": 12, "status": 17, "pelunasan": 18
        }
        data_lines = lines
    else:
        data_lines = lines[header_idx + 1:]

    halaman_valid = True
    matched_rows = []
    clean_expected = re.sub(r'\s+', '', expected_code).lower()
    memo_idx = cols_map.get("memo", 2)

    print(f"[DEBUG PARSING] Memo Index: {memo_idx}")

    for line in data_lines:
        parts = [p.strip() for p in re.split(r'\t+|\s{2,}', line)]
        if len(parts) > memo_idx:
            val = re.sub(r'\s+', '', parts[memo_idx]).lower()
            if val == clean_expected:
                # Perbaikan: cari status di dalam baris yang cocok (cari kata kunci)
                status = "belum"
                # Cari di seluruh baris
                for p in parts:
                    if p.lower() in ["sudah", "paid", "lunas"]:
                        status = "sudah"
                        break

                # Tambahkan/Update status
                if "status" in cols_map:
                    idx = cols_map["status"]
                    if idx < len(parts):
                        parts[idx] = status
                    else:
                        parts.append(status)
                        cols_map["status"] = len(parts) - 1
                else:
                    parts.append(status)
                    cols_map["status"] = len(parts) - 1

                print(f"[DEBUG PARSING] Cocok ditemukan: {parts}, Status: {status}")
                matched_rows.append(parts)

    return matched_rows, cols_map, halaman_valid
