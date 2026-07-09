from __future__ import annotations

from web_app.account_change import account_today_change
from web_app.pools import load_legacy_hold_pool, load_pool_definitions
from web_app.ranking import build_rankings


REQUIRED_ROW_KEYS = {
    "代码",
    "名称",
    "持仓",
    "持仓市值",
    "板块",
    "评级",
    "最新收盘价",
    "当日涨跌幅",
    "MA15",
    "价格>MA15",
    "MA20",
    "价格>MA20",
    "20日涨幅",
    "量比",
    "动量得分",
    "量能得分",
    "趋势得分",
    "综合总分",
    "昨日排名",
    "排名变化",
    "动态预警",
}


def main() -> None:
    pools = load_pool_definitions()
    assert set(pools) == {"a_share", "global", "new_tech"}
    assert all(pools.values())

    holds = load_legacy_hold_pool()
    assert "161226" in holds

    payload = build_rankings(source="tencent", refresh=False)
    assert "pools" in payload
    assert set(payload["pools"]) == {"a_share", "global", "new_tech"}

    for pool in payload["pools"].values():
        assert "rows" in pool
        if pool["rows"]:
            assert REQUIRED_ROW_KEYS.issubset(pool["rows"][0])

    counts = {key: len(value["rows"]) for key, value in payload["pools"].items()}

    today_change = account_today_change(source="tencent")
    assert set(today_change["accounts"]) == {"a_share", "global"}

    print(
        {
            "ok": True,
            "source": payload["source"],
            "counts": counts,
            "account_change": {
                key: value["return_1d"] for key, value in today_change["accounts"].items()
            },
            "errors": len(payload.get("errors") or []),
        }
    )


if __name__ == "__main__":
    main()
