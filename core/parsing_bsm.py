import re

def parse_bsm_page(text: str, kode: str):
    """Parse teks halaman Inventory BSM dengan memproses per blok transaksi."""
    rows = []

    # Pisahkan teks menjadi blok-blok transaksi berdasarkan awalan "09-FP"
    blocks = re.split(r'(?=^09-FP\.)', text, flags=re.MULTILINE)

    clean_kode = re.sub(r'\s+', '', kode).lower()

    for block in blocks:
        block = block.strip()
        if not block: continue

        # Cari kode di baris data faktur (baris yang dimulai dengan 09-FP.)
        # Dan cek apakah baris tersebut mengandung kode yang dicari
        lines = block.splitlines()

        for line in lines:
            if line.startswith("09-FP."):
                parts = [p.strip() for p in line.split('\t')]
                # Contoh: 09-FP.2611.0287    09-SO.2611.0330    261028SQ0E28KN ...
                # Kolom memo ada di index 2
                if len(parts) > 2:
                    val = re.sub(r'\s+', '', parts[2]).lower()

                    if val == clean_kode:
                        # Ditemukan, sekarang tentukan status bayar
                        # Status bayar biasanya ada di baris setelah baris faktur
                        # atau di kolom ke-19 (berdasarkan contoh, status ada di sana)

                        # Cara lebih akurat: cari kata status di seluruh blok
                        status = "belum"
                        # Cari baris yang mengandung 'Sudah' atau 'Belum'
                        # Contoh baris: "Belum    Tidak        GUDANG    Belum    Non Cash    Tidak    Tidak"
                        # Kita ambil baris yang mengandung Status Bayar (setelah TOTAL atau di baris tertentu)

                        # Debug: lihat baris yang ada di block
                        # print(f"[DEBUG] Block: {block}")

                        if re.search(r'\b(sudah|paid|lunas)\b', block, re.IGNORECASE):
                            status = "sudah"

                        # Buat row untuk scan.py
                        row = [""] * 20
                        # Isi kolom dari parts faktur
                        for i, p in enumerate(parts):
                            if i < 20: row[i] = p

                        row[2] = parts[2] # Memo
                        row[19] = status # Status

                        rows.append(row)
                        break

    kolom_idx = {
        "nomor": 0, "pelunasan": 3, "tanggal": 4, "memo": 2,
        "salesman": 8, "customer": 10, "total": 11, "retur": 13, "status": 19
    }

    return rows, kolom_idx, {"valid": True}
