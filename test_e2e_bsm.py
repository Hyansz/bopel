"""E2E Test simulation for Inventory BSM web app parsing and checklist automation."""

import pytest
from parse_bsm import parse_page


SAMPLE_BSM_PAGE = """1	26-FP.2026.0001	2026-11-10	2026-11-20	0	10000	100000	0	0	90000	2611028Q6QTV
2	26-FP.2026.0002	2026-11-10	2026-11-20	0	5000	50000	0	0	45000	2611028Q6QTW
Total Bayar 2 baris
"""


def test_parse_bsm_sample():
    result = parse_page(SAMPLE_BSM_PAGE)
    assert len(result["rows"]) == 2
    assert result["problems"] == []

    r1 = result["rows"][0]
    assert r1["no"] == 1
    assert r1["kode"] == "2611028Q6QTV"
    assert r1["net"] == 90000

    r2 = result["rows"][1]
    assert r2["no"] == 2
    assert r2["kode"] == "2611028Q6QTW"
    assert r2["net"] == 45000


def test_parse_bsm_invalid_data():
    invalid_text = "This is not a valid BSM page"
    result = parse_page(invalid_text)
    assert len(result["rows"]) == 0
    assert isinstance(result["problems"], list)
