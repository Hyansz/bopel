import re
import os
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
        found.append({"kode": k, "baris": h["no"], "invoice": h["invoice"], "net": h["net"], "nilai": h["nilai"]})
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
    if res["parser_problems"]:
        print("!! Masalah baca halaman:", res["parser_problems"])
    if res["dups"]:
        print("!! Kode muncul di lebih dari satu baris:", res["dups"])
    if res["extra"]:
        print(f"Baris lain di aplikasi (tidak dicentang): {len(res['extra'])}")
        os.makedirs("logs", exist_ok=True)
        with open(r"logs\bsm_match_last.txt", "w", encoding="utf-8") as f:
            f.write("BARIS  KODE              INVOICE\n")
            for r in res["extra"]:
                f.write(f"{r['no']:>5}  {r['kode']}  {r['invoice']}\n")
