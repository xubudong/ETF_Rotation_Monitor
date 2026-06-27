from __future__ import annotations

import sqlite3
from typing import Any

import pandas as pd

from .config import ACCOUNT_POOL_KEYS, CACHE_DB, DATA_SOURCES, POOL_SPECS
from .market_data import fetch_spot, first_value
from .storage import init_cache_db, read_cached_history
from .utils import normalize_value, now_iso


def load_account_positions(pool_key: str) -> list[dict[str, Any]]:
    init_cache_db()
    with sqlite3.connect(CACHE_DB) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            SELECT pool_key, code, name, shares, market_value, current_price, updated_at
            FROM account_holdings
            WHERE pool_key = ?
            ORDER BY market_value DESC
            """,
            (pool_key,),
        ).fetchall()
    return [dict(row) for row in rows]


def cached_last_two_closes(code: str) -> tuple[float | None, float | None]:
    df = read_cached_history(code, days=3)
    if df is None or len(df) < 2:
        return None, None
    closes = pd.to_numeric(df["close"], errors="coerce")
    if pd.isna(closes.iloc[-1]) or pd.isna(closes.iloc[-2]):
        return None, None
    return float(closes.iloc[-1]), float(closes.iloc[-2])


def fallback_return_1d(code: str) -> float | None:
    latest_close, previous_close = cached_last_two_closes(code)
    if latest_close is None or previous_close is None or previous_close == 0:
        return None
    return latest_close / previous_close - 1


def spot_price_context(code: str, spot: dict[str, Any]) -> tuple[float | None, float | None, float | None, str]:
    latest = first_value(spot, ["最新价", "最新价格", "最新", "最新收盘价"])
    pct = first_value(spot, ["涨跌幅", "当日涨跌幅"])
    prev_close = first_value(spot, ["昨收", "昨日收盘价", "前收盘价"])
    try:
        latest_num = float(latest) if latest not in (None, "") else None
    except (TypeError, ValueError):
        latest_num = None
    if latest_num is not None and latest_num <= 0:
        latest_num = None

    try:
        pct_num = float(pct) if pct not in (None, "") else None
    except (TypeError, ValueError):
        pct_num = None

    try:
        prev_num = float(prev_close) if prev_close not in (None, "") else None
    except (TypeError, ValueError):
        prev_num = None
    if prev_num is not None and prev_num <= 0:
        prev_num = None

    if pct_num is not None and abs(pct_num) > 1:
        pct_num = pct_num / 100

    if latest_num is not None and prev_num is None and pct_num is not None and pct_num > -0.999:
        prev_num = latest_num / (1 + pct_num)

    if latest_num is not None and prev_num is None:
        cached_latest_close, _ = cached_last_two_closes(code)
        if cached_latest_close and cached_latest_close > 0:
            prev_num = cached_latest_close

    if pct_num is None and latest_num is not None and prev_num and prev_num > 0:
        pct_num = latest_num / prev_num - 1

    if latest_num is not None and prev_num is not None and pct_num is not None:
        return latest_num, prev_num, pct_num, "spot"

    cached_latest_close, cached_previous_close = cached_last_two_closes(code)
    if cached_latest_close is not None and cached_previous_close and cached_previous_close > 0:
        return cached_latest_close, cached_previous_close, cached_latest_close / cached_previous_close - 1, "cache"
    return latest_num, prev_num, pct_num, "missing"


def account_today_change(source: str = "tencent") -> dict[str, Any]:
    if source not in DATA_SOURCES:
        raise ValueError(f"未知数据源: {source}")

    accounts: dict[str, Any] = {}
    errors: list[str] = []
    for pool_key in sorted(ACCOUNT_POOL_KEYS):
        positions = load_account_positions(pool_key)
        pool = {row["code"]: row["name"] or row["code"] for row in positions}
        spots = fetch_spot(pool, source, errors) if pool else {}

        current_total = 0.0
        previous_total = 0.0
        today_pnl = 0.0
        covered = 0
        items = []
        for row in positions:
            code = str(row["code"]).zfill(6)
            latest, previous_price, ret_1d, ret_source = spot_price_context(code, spots.get(code, {}))
            market_value = float(row["market_value"] or 0)
            shares = float(row["shares"] or 0)
            if latest is not None and shares > 0:
                current_value = shares * latest
            else:
                current_value = market_value

            if current_value <= 0:
                continue
            current_total += current_value

            previous_value = None
            pnl = None
            if shares > 0 and latest is not None and previous_price is not None and previous_price > 0:
                previous_value = shares * previous_price
                pnl = shares * (latest - previous_price)
                ret_1d = latest / previous_price - 1
            elif ret_1d is not None and ret_1d > -0.999:
                previous_value = current_value / (1 + ret_1d)
                pnl = current_value - previous_value

            if previous_value is not None and pnl is not None:
                previous_total += previous_value
                today_pnl += pnl
                covered += 1

            items.append(
                {
                    "code": code,
                    "name": row["name"] or code,
                    "current_value": normalize_value(current_value),
                    "previous_value": normalize_value(previous_value),
                    "latest_price": normalize_value(latest),
                    "previous_price": normalize_value(previous_price),
                    "shares": normalize_value(shares),
                    "return_1d": normalize_value(ret_1d),
                    "today_pnl": normalize_value(pnl),
                    "source": ret_source,
                }
            )

        account_return = today_pnl / previous_total if previous_total > 0 else None
        accounts[pool_key] = {
            "title": POOL_SPECS[pool_key]["title"],
            "holdings": len(positions),
            "covered": covered,
            "total_value": normalize_value(current_total),
            "previous_value": normalize_value(previous_total),
            "today_pnl": normalize_value(today_pnl if previous_total > 0 else None),
            "return_1d": normalize_value(account_return),
            "items": items,
        }

    return {
        "source": source,
        "generated_at": now_iso(),
        "accounts": accounts,
        "errors": errors[-10:],
    }
