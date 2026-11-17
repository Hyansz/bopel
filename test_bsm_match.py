import pytest
from parse_bsm import parse_page
from bsm_match import match_codes


def _row(n, kode, fp, d, ppn, nilai, net, memo):
    return (f"{n}\tSHOPEE TOKO ALKES SOLO\t{kode}\t{fp}\t{d}\t{d}\t0\t{ppn}\t{nilai}\t0\t\n"
            f"0.00\n\t{net}\t{memo}\n")


PAGE = ("Detail Invoice\n5 baris\nNo\n\n"
        + _row(1, "", "09-FP.2607.0149", "2026-07-31", "3.919,37", "39.550", "35.630,63", "2607314NF54Q0M")
        + _row(2, "2611027AA02JVM", "09-FP.2611.0002", "2026-11-02", "3.894,1", "39.295", "35.400,9", "2611027AA02JVM")
        + _row(3, "2611028Q6QTV 25", "09-FP.2611.0071", "2026-11-03", "48.091,8", "485.290", "437.198,2", "2611028Q6QTV25")
        + _row(4, "261104DNUH9SD G", "09-FP.2611.0212", "2026-11-07", "28.001,94", "282.565", "254.563,06", "261104DNUH9SDG")
        + _row(5, "261106KHN0VWSB", "09-FP.2611.0283", "2026-11-09", "113.324,77", "1.143.550", "1.030.225,23", "261106KHN0VWSB")
        + "Total Bayar: 0\n")


def test_parse_real_format():
    r = parse_page(PAGE)
    assert r["problems"] == []
    assert [x["kode"] for x in r["rows"]] == ["2607314NF54Q0M", "2611027AA02JVM", "2611028Q6QTV25", "261104DNUH9SDG", "261106KHN0VWSB"]
    assert r["rows"][0]["warn"]           # kolom kode kosong -> pakai memo
    assert str(r["rows"][4]["net"]) == "1030225.23"


def test_match_rows_and_missing():
    res = match_codes(["261106KHN0VWSB", "2611027AA02JVM", "261199ZZZZZZZZ"], PAGE)
    assert [(f["baris"], f["kode"]) for f in res["found"]] == [(2, "2611027AA02JVM"), (5, "261106KHN0VWSB")]
    assert res["missing"] == ["261199ZZZZZZZZ"]
    assert len(res["extra"]) == 3
    assert [p["turun"] for p in res["plan"]] == [1, 3]


def test_header_count_mismatch_detected():
    r = parse_page(PAGE.replace("5 baris", "9 baris"))
    assert any("header bilang 9" in p[1] for p in r["problems"])


def test_garbage_has_no_rows():
    assert parse_page("bukan halaman bsm")["rows"] == []
