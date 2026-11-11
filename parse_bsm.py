import re
from decimal import Decimal

ROW_START = re.compile(r"(?m)^(\d{1,4})\t")
FP = re.compile(r"\d{2}-FP\.\d{4}\.\d{4}")
DATE = re.compile(r"\d{4}-\d{2}-\d{2}")
KODE = re.compile(r"^[0-9A-Z]{12,15}$")


def _idr(s: str) -> Decimal:
    return Decimal(s.replace(".", "").replace(",", "."))


def parse_page(text: str) -> dict:
    text = text.replace("\r\n", "\n")
    m_total = re.search(r"(?m)^Total Bayar", text)
    body = text[: m_total.start()] if m_total else text
    declared = re.search(r"(\d+)\s+baris", body)
    starts = list(ROW_START.finditer(body))
    rows, problems = [], []
    for i, m in enumerate(starts):
        rec = body[m.start(): starts[i + 1].start() if i + 1 < len(starts) else len(body)]
        no = int(m.group(1))
        fp, dates = FP.search(rec), DATE.findall(rec)
        if not fp or len(dates) < 2:
            problems.append((no, "baris tidak lengkap")); continue
        tail = rec[rec.rfind(dates[1]) + len(dates[1]):].split()
        if len(tail) != 7:
            problems.append((no, f"kolom angka {len(tail)} (harus 7)")); continue
        retur, ppn, nilai, terbayar, bayar, net, memo = tail
        if not KODE.match(memo):
            problems.append((no, f"memo bukan kode pesanan: {memo!r}")); continue
        pre = re.sub(r"\s+", "", rec[:fp.start()])
        warn = "" if memo in pre else "kolom kode pesanan kosong/beda, dipakai memo"
        net_d = _idr(net)
        if abs(_idr(nilai) - _idr(ppn) - net_d) > Decimal("0.02"):
            problems.append((no, f"nilai-ppn != net ({nilai} - {ppn} vs {net})")); continue
        rows.append({"no": no, "kode": memo, "invoice": fp.group(), "tgl": dates[0],
                     "nilai": _idr(nilai), "ppn": _idr(ppn), "net": net_d, "warn": warn})
    if declared and int(declared.group(1)) != len(rows):
        problems.append((0, f"header bilang {declared.group(1)} baris, terbaca {len(rows)}"))
    kodes = [r["kode"] for r in rows]
    if len(set(kodes)) != len(kodes):
        problems.append((0, "ada kode pesanan ganda"))
    return {"rows": rows, "problems": problems}
