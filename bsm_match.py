import re
from parse_bsm import parse_page


def norm(kode) -> str:
    return re.sub(r"\s+", "", str(kode)).upper()


def match_codes(shopee_codes, page_text: str) -> dict:
    page = parse_page(page_text)
    by_code = {}
    for r in page["rows"]:
        by_code.setdefault(r["kode"], []).append(r)
    wanted, seen = [], set()
    for k in shopee_codes:
        k = norm(k)
        if k and k not in seen:
            seen.add(k)
            wanted.append(k)
    found, missing, dups = [], [], []
    for k in wanted:
        hits = by_code.get(k)
        if not hits:
            missing.append(k)
            continue
        if len(hits) > 1:
            dups.append((k, [h["no"] for h in hits]))
        h = hits[0]
        found.append({"kode": k, "baris": h["no"], "invoice": h["invoice"], "net": h["net"]})
    found.sort(key=lambda x: x["baris"])
    extra = [r for r in page["rows"] if r["kode"] not in seen]
    plan, cur = [], 1
    for f in found:
        plan.append({"turun": f["baris"] - cur, "baris": f["baris"], "kode": f["kode"]})
        cur = f["baris"]
    return {"total_baris_app": len(page["rows"]), "total_shopee": len(wanted),
            "found": found, "missing": missing, "extra": extra, "dups": dups,
            "plan": plan, "parser_problems": page["problems"]}


def print_report(res: dict) -> None:
    print(f"Baris di aplikasi : {res['total_baris_app']}")
    print(f"Kode dari Shopee  : {res['total_shopee']}")
    print(f"Cocok             : {len(res['found'])}")
    print(f"Ada di Shopee, TIDAK ada di aplikasi : {len(res['missing'])}")
    print(f"Ada di aplikasi, TIDAK ada di Shopee : {len(res['extra'])}")
    if res["parser_problems"]:
        print("!! Masalah baca halaman:", res["parser_problems"])
    if res["dups"]:
        print("!! Kode muncul di lebih dari satu baris:", res["dups"])
    print("BARIS  KODE              INVOICE           NET")
    for f in res["found"]:
        print(f"{f['baris']:>5}  {f['kode']}  {f['invoice']}  {f['net']:>14,.2f}")
    if res["missing"]:
        print("Tidak ketemu di aplikasi:", ", ".join(res["missing"]))
    if res["extra"]:
        print("Ada di aplikasi tapi tidak di Shopee (tidak akan dicentang):")
        for r in res["extra"]:
            print(f"{r['no']:>5}  {r['kode']}  {r['invoice']}")
