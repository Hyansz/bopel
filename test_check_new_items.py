import pytest
from decimal import Decimal
from app import Api
from core.launcher_cb import ToolLauncher
from check_new import print_check_table

def test_print_check_table_0_rows(capsys):
    """Test print_check_table with 0 rows."""
    orders = []
    res = {"found": [], "missing": [], "plan": []}
    shopee_prices = {}

    print_check_table(orders, res, shopee_prices)
    captured = capsys.readouterr()
    assert "TABEL KODE PESANAN + HARGA (CHECK NEW)" in captured.out


def test_print_check_table_1_row_ok(capsys):
    """Test print_check_table with 1 row matching."""
    orders = ["2600000000001"]
    # Add 'nilai' to found dicts
    res = {
        "found": [{"kode": "2600000000001", "baris": 1, "invoice": "24-FP.2026.0001", "net": 50000, "nilai": Decimal("50000")}],
        "missing": [],
        "plan": []
    }
    shopee_prices = {"2600000000001": 50000}

    print_check_table(orders, res, shopee_prices)
    captured = capsys.readouterr()

    api = Api(ToolLauncher())
    rk = "Checklist Automation - New"
    for line in captured.out.splitlines():
        api._parse_table_line(rk, line)

    items = api._items.get(rk, [])
    assert len(items) == 1
    assert items[0]["kode"] == "2600000000001"
    assert items[0]["kategori"] == "ok"
    assert items[0]["harga_shopee"] == "50000"
    assert items[0]["no_faktur"] == "24-FP.2026.0001"


def test_price_validation_rules(capsys):
    """Test price validation: diff <= 1 (OK), diff > 1 (BEDA), tolerance."""
    orders = ["C1", "C2", "C3"]
    # C1: diff 0 (OK)
    # C2: diff 2 (BEDA)
    # C3: diff 1 (OK - within tolerance)
    res = {
        "found": [
            {"kode": "C1", "baris": 1, "invoice": "INV1", "net": 100, "nilai": Decimal("100")},
            {"kode": "C2", "baris": 2, "invoice": "INV2", "net": 100, "nilai": Decimal("100")},
            {"kode": "C3", "baris": 3, "invoice": "INV3", "net": 100, "nilai": Decimal("100")},
        ],
        "missing": [],
        "plan": []
    }
    shopee_prices = {"C1": 100, "C2": 102, "C3": 101}

    print_check_table(orders, res, shopee_prices)
    captured = capsys.readouterr()

    api = Api(ToolLauncher())
    rk = "Checklist Automation - New"
    for line in captured.out.splitlines():
        api._parse_table_line(rk, line)

    items = api._items.get(rk, [])
    assert len(items) == 3

    # Check categories
    cat_map = {it["kode"]: it["kategori"] for it in items}
    assert cat_map["C1"] == "ok"
    assert cat_map["C2"] == "bedacek"
    assert cat_map["C3"] == "ok"

    # Verify logic manually for Beda count (manual gating)
    ok_count = 0
    beda_count = 0
    plan = []
    cur = 1
    for f in res["found"]:
        c = f["kode"]
        p2 = shopee_prices.get(c)
        app_nilai = f["nilai"]
        if p2 is not None and abs(Decimal(str(p2)) - app_nilai) <= 1:
            ok_count += 1
            plan.append({"turun": f["baris"] - cur, "baris": f["baris"], "kode": c})
            cur = f["baris"]
        else:
            beda_count += 1

    assert ok_count == 2
    assert beda_count == 1
    assert len(plan) == 2
