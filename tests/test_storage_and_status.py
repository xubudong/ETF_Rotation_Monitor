from __future__ import annotations

from web_app.storage import cache_stats, parse_holdings_text


def test_parse_holdings_uses_stock_balance_when_actual_quantity_missing():
    headers = "\u8bc1\u5238\u4ee3\u7801\t\u8bc1\u5238\u540d\u79f0\t\u80a1\u7968\u4f59\u989d\t\u6210\u672c\u4ef7\t\u6700\u65b0\u4ef7\t\u5e02\u503c"
    row = "561600\t\u6d88\u8d39\u7535\u5b50ETF\t1200\t1.2\t1.3\t1560"
    rows = parse_holdings_text(f"{headers}\n{row}\n".encode("utf-8"))
    assert rows[0]["code"] == "561600"
    assert rows[0]["shares"] == 1200
    assert rows[0]["market_value"] == 1560


def test_cache_stats_returns_stable_shape():
    stats = cache_stats()
    for key in ["sqlite_exists", "symbols", "min_date", "max_date"]:
        assert key in stats
