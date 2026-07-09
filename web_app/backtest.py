from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd

from .pools import load_pool_definitions
from .market_regime import runtime_overrides_for_market_filter
from .scoring import calculate_indicators, cross_sectional_score_and_rate, force_sell_codes_from_scores, get_strategy_config, target_codes_from_scores
from .storage import read_cached_history
from .utils import normalize_records, now_iso

BENCHMARKS = {
    "510300": "沪深300",
    "563360": "中证A500",
    "510500": "中证500",
    "588000": "科创50",
    "159915": "创业板ETF",
    "513100": "纳指100",
    "513880": "日经225",
    "518880": "黄金ETF",
}
CALENDAR_PRIORITY = ["510300", "563360", "510500", "510050", "588000", "159915"]
EXECUTION_MODES = {
    "next_open": "次日开盘成交",
    "same_close": "当日收盘成交",
}


@dataclass
class Holding:
    name: str
    shares: int
    cost_price: float


def benchmark_options() -> list[dict[str, str]]:
    return [{"code": code, "name": name} for code, name in BENCHMARKS.items()]


def _history_days(months: int | None, start_date: str | None, end_date: str | None) -> int:
    if start_date:
        requested_start = pd.to_datetime(start_date).normalize()
        latest_anchor = max(
            pd.Timestamp.now().normalize(),
            pd.to_datetime(end_date).normalize() if end_date else pd.Timestamp.now().normalize(),
        )
        return max(360, int((latest_anchor - requested_start).days + 260))
    return max(360, int((months or 12) * 31 + 260))


def _load_histories(pool: dict[str, str], days: int) -> dict[str, pd.DataFrame]:
    histories: dict[str, pd.DataFrame] = {}
    for code in pool:
        df = read_cached_history(code, days=days)
        if df is None or len(df) < 80:
            continue
        histories[code] = calculate_indicators(df.copy()).dropna(subset=["close", "MA20", "MA60"])
    return histories


def _load_calendar_df(days: int) -> pd.DataFrame | None:
    for code in CALENDAR_PRIORITY:
        df = read_cached_history(code, days=days)
        if df is not None and not df.empty:
            return df
    return None


def _trading_days(
    histories: dict[str, pd.DataFrame],
    calendar_df: pd.DataFrame | None,
    months: int | None,
    start_date: str | None,
    end_date: str | None,
) -> tuple[pd.DatetimeIndex, pd.Timestamp, pd.Timestamp]:
    if calendar_df is not None and not calendar_df.empty:
        base_index = calendar_df.index
    else:
        all_dates = sorted({date for df in histories.values() for date in df.index})
        base_index = pd.DatetimeIndex(all_dates)
    if base_index.empty:
        return base_index, pd.NaT, pd.NaT
    requested_end = pd.to_datetime(end_date).normalize() if end_date else base_index.max()
    actual_end = min(base_index.max(), requested_end)
    requested_start = pd.to_datetime(start_date).normalize() if start_date else actual_end - pd.DateOffset(months=months or 12)
    return base_index[(base_index >= requested_start) & (base_index <= actual_end)], requested_start, requested_end


def _row_for_scoring(code: str, name: str, row: pd.Series) -> dict[str, Any]:
    return {
        "代码": code,
        "名称": name,
        "最新收盘价": row["close"],
        "MA15": row["MA15"],
        "MA20": row["MA20"],
        "MA60": row["MA60"],
        "20日涨幅": row["return_20d"],
        "量比": row["vol_ratio"],
        "当日涨跌幅": row["return_1d"],
        "20日波动率": row.get("volatility_20d"),
    }


def _drawdown(series: pd.Series) -> pd.Series:
    peak = series.cummax()
    return series / peak - 1


def _execute_orders(
    sell_codes: list[str],
    buy_codes: list[str],
    current_date: pd.Timestamp,
    price_column: str,
    histories: dict[str, pd.DataFrame],
    pool: dict[str, str],
    holdings: dict[str, Holding],
    cash: float,
    max_holdings: int,
) -> tuple[float, list[dict[str, Any]], list[dict[str, Any]], list[str]]:
    sold_today: list[dict[str, Any]] = []
    pending_sells: list[str] = []
    for code in sell_codes:
        if code not in holdings:
            continue
        df = histories.get(code)
        if df is None or current_date not in df.index or pd.isna(df.loc[current_date, price_column]):
            pending_sells.append(code)
            continue
        price = float(df.loc[current_date, price_column])
        holding = holdings.pop(code)
        amount = holding.shares * price
        cash += amount
        sold_today.append(
            {
                "date": current_date.strftime("%Y-%m-%d"),
                "action": "卖出",
                "code": code,
                "name": holding.name,
                "price": price,
                "shares": holding.shares,
                "amount": amount,
                "pnl_pct": price / holding.cost_price - 1 if holding.cost_price else None,
            }
        )

    bought_today: list[dict[str, Any]] = []
    slots = max(max_holdings - len(holdings), 0)
    for code in buy_codes:
        if slots <= 0 or code in holdings:
            continue
        df = histories.get(code)
        if df is None or current_date not in df.index or pd.isna(df.loc[current_date, price_column]):
            continue
        price = float(df.loc[current_date, price_column])
        shares = int((cash / slots) / price / 100) * 100
        if shares <= 0:
            continue
        cash -= shares * price
        holdings[code] = Holding(pool[code], shares, price)
        bought_today.append(
            {
                "date": current_date.strftime("%Y-%m-%d"),
                "action": "买入",
                "code": code,
                "name": pool[code],
                "price": price,
                "shares": shares,
                "amount": shares * price,
                "pnl_pct": None,
            }
        )
        slots -= 1
    return cash, sold_today, bought_today, pending_sells


def _price_on_date(histories: dict[str, pd.DataFrame], code: str, current_date: pd.Timestamp, price_column: str, fallback: float | None = None) -> float | None:
    df = histories.get(code)
    if df is not None and current_date in df.index and pd.notna(df.loc[current_date, price_column]):
        return float(df.loc[current_date, price_column])
    return fallback


def _execute_target_rebalance(
    target_codes: list[str],
    force_sell_pool: set[str],
    current_date: pd.Timestamp,
    price_column: str,
    histories: dict[str, pd.DataFrame],
    pool: dict[str, str],
    holdings: dict[str, Holding],
    cash: float,
    max_holdings: int,
    position_ratio: float,
) -> tuple[float, list[dict[str, Any]], list[dict[str, Any]]]:
    sold_today: list[dict[str, Any]] = []
    bought_today: list[dict[str, Any]] = []
    target_set = set(target_codes)

    prices: dict[str, float] = {}
    for code, holding in holdings.items():
        price = _price_on_date(histories, code, current_date, price_column, holding.cost_price)
        if price is not None:
            prices[code] = price
    for code in target_codes:
        price = _price_on_date(histories, code, current_date, price_column)
        if price is not None:
            prices[code] = price

    total_asset = cash + sum(holding.shares * prices.get(code, holding.cost_price) for code, holding in holdings.items())
    target_value = total_asset * position_ratio / max(max_holdings, 1)

    def sell_shares(code: str, shares: int) -> None:
        nonlocal cash
        if shares <= 0 or code not in holdings or code not in prices:
            return
        holding = holdings[code]
        shares = min(shares, holding.shares)
        price = prices[code]
        amount = shares * price
        holding.shares -= shares
        cash += amount
        sold_today.append(
            {
                "date": current_date.strftime("%Y-%m-%d"),
                "action": "卖出",
                "code": code,
                "name": holding.name,
                "price": price,
                "shares": shares,
                "amount": amount,
                "pnl_pct": price / holding.cost_price - 1 if holding.cost_price else None,
            }
        )
        if holding.shares <= 0:
            holdings.pop(code, None)

    def buy_shares(code: str, shares: int) -> None:
        nonlocal cash
        if shares <= 0 or code not in prices:
            return
        price = prices[code]
        affordable = int(cash / price / 100) * 100
        shares = min(shares, affordable)
        if shares <= 0:
            return
        amount = shares * price
        existing = holdings.get(code)
        if existing:
            total_shares = existing.shares + shares
            existing.cost_price = (existing.cost_price * existing.shares + amount) / total_shares if total_shares else price
            existing.shares = total_shares
        else:
            holdings[code] = Holding(pool[code], shares, price)
        cash -= amount
        bought_today.append(
            {
                "date": current_date.strftime("%Y-%m-%d"),
                "action": "买入",
                "code": code,
                "name": pool[code],
                "price": price,
                "shares": shares,
                "amount": amount,
                "pnl_pct": None,
            }
        )

    for code in list(holdings):
        if code in force_sell_pool or code not in target_set:
            sell_shares(code, holdings[code].shares)

    for code in target_codes:
        if code not in prices:
            continue
        desired_shares = int(target_value / prices[code] / 100) * 100
        current_shares = holdings[code].shares if code in holdings else 0
        if current_shares > desired_shares:
            sell_shares(code, current_shares - desired_shares)

    for code in target_codes:
        if code not in prices:
            continue
        desired_shares = int(target_value / prices[code] / 100) * 100
        current_shares = holdings[code].shares if code in holdings else 0
        if current_shares < desired_shares:
            buy_shares(code, desired_shares - current_shares)

    return cash, sold_today, bought_today


def run_backtest(
    pool_key: str,
    strategy_id: str | None = None,
    months: int | None = 12,
    initial_capital: float = 200000.0,
    benchmark_code: str = "510300",
    start_date: str | None = None,
    end_date: str | None = None,
    execution_mode: str = "next_open",
) -> dict[str, Any]:
    if start_date:
        requested_start = pd.to_datetime(start_date, errors="coerce")
        requested_end = pd.to_datetime(end_date, errors="coerce") if end_date else None
        if pd.isna(requested_start):
            raise ValueError("开始日期格式无效")
        if end_date and pd.isna(requested_end):
            raise ValueError("结束日期格式无效")
        if requested_end is not None and requested_end < requested_start:
            raise ValueError("结束日期不能早于开始日期")
    elif end_date:
        raise ValueError("指定结束日期时必须同时指定开始日期")
    elif months is None or months < 1 or months > 60:
        raise ValueError("months 必须在 1 到 60 之间")
    if initial_capital <= 0:
        raise ValueError("initial_capital 必须大于 0")
    if execution_mode not in EXECUTION_MODES:
        raise ValueError(f"未知成交方式: {execution_mode}")

    pools = load_pool_definitions()
    if pool_key not in pools:
        raise ValueError(f"未知池子: {pool_key}")
    pool = pools[pool_key]
    strategy = get_strategy_config(strategy_id)
    max_holdings = int(strategy.get("max_holdings", 8))

    fetch_days = _history_days(months, start_date, end_date)
    histories = _load_histories(pool, fetch_days)
    benchmark_df = read_cached_history(benchmark_code, days=fetch_days)
    if benchmark_df is not None:
        benchmark_df = calculate_indicators(benchmark_df.copy())
    calendar_df = _load_calendar_df(fetch_days)
    trading_days, requested_start, requested_end = _trading_days(histories, calendar_df, months, start_date, end_date)
    if len(histories) < 2:
        raise ValueError("本地库历史数据不足，请先更新本地库后再回测")
    if trading_days.empty:
        raise ValueError("所选区间内没有可用交易日，请调整开始或结束日期")
    requested_start_date = requested_start.strftime("%Y-%m-%d")
    requested_end_date = requested_end.strftime("%Y-%m-%d")
    actual_start_date = trading_days.min().strftime("%Y-%m-%d")
    actual_end_date = trading_days.max().strftime("%Y-%m-%d")

    cash = float(initial_capital)
    holdings: dict[str, Holding] = {}
    pending_sells: list[str] = []
    pending_buys: list[str] = []
    pending_target_codes: list[str] | None = None
    pending_force_sell_pool: set[str] = set()
    pending_position_ratio = 1.0
    records: list[dict[str, Any]] = []
    rebalance_records: list[dict[str, Any]] = []
    trade_records: list[dict[str, Any]] = []
    market_states: list[dict[str, Any]] = []

    for current_date in trading_days:
        sold_today: list[dict[str, Any]] = []
        bought_today: list[dict[str, Any]] = []
        if execution_mode == "next_open":
            if pending_target_codes is not None:
                cash, sold_today, bought_today = _execute_target_rebalance(
                    pending_target_codes,
                    pending_force_sell_pool,
                    current_date,
                    "open",
                    histories,
                    pool,
                    holdings,
                    cash,
                    max_holdings,
                    pending_position_ratio,
                )
                pending_target_codes = None
                pending_force_sell_pool = set()
            else:
                cash, sold_today, bought_today, pending_sells = _execute_orders(
                    pending_sells, pending_buys, current_date, "open", histories, pool, holdings, cash, max_holdings
                )
            trade_records.extend(sold_today + bought_today)
            pending_buys = []

        daily_rows = []
        for code, df in histories.items():
            if current_date not in df.index or pd.isna(df.loc[current_date, "close"]):
                continue
            daily_rows.append(_row_for_scoring(code, pool[code], df.loc[current_date]))
        market_state = runtime_overrides_for_market_filter(strategy, current_date, days=fetch_days)
        runtime_overrides = market_state.get("runtime_overrides") or {}
        if market_state.get("enabled"):
            market_states.append(market_state)
        rating_df = (
            cross_sectional_score_and_rate(pd.DataFrame(daily_rows), strategy_id=strategy.get("id"), runtime_overrides=runtime_overrides)
            if daily_rows
            else pd.DataFrame()
        )
        if not rating_df.empty and "综合总分" in rating_df.columns:
            target_codes = target_codes_from_scores(rating_df, strategy_id=strategy.get("id"))
            target_pool = set(target_codes)
            force_sell_pool = force_sell_codes_from_scores(rating_df)
            if market_state.get("enabled"):
                position_ratio = float(market_state.get("position_ratio") or 1.0)
                if execution_mode == "same_close":
                    cash, sold_today, bought_today = _execute_target_rebalance(
                        target_codes,
                        force_sell_pool,
                        current_date,
                        "close",
                        histories,
                        pool,
                        holdings,
                        cash,
                        max_holdings,
                        position_ratio,
                    )
                    trade_records.extend(sold_today + bought_today)
                else:
                    pending_target_codes = target_codes
                    pending_force_sell_pool = force_sell_pool
                    pending_position_ratio = position_ratio
                pending_sells = []
                pending_buys = []
            else:
                signal_sells = [code for code in holdings if code in force_sell_pool or code not in target_pool]
                signal_buys = [code for code in target_codes if code not in holdings]
                if execution_mode == "same_close":
                    cash, sold_today, bought_today, _ = _execute_orders(
                        signal_sells, signal_buys, current_date, "close", histories, pool, holdings, cash, max_holdings
                    )
                    trade_records.extend(sold_today + bought_today)
                    pending_sells = []
                    pending_buys = []
                else:
                    pending_sells = list(dict.fromkeys(pending_sells + signal_sells))
                    pending_buys = signal_buys
            if bought_today or sold_today or pending_buys or pending_sells or pending_target_codes is not None:
                next_buys = pending_buys
                next_sells = pending_sells
                if pending_target_codes is not None:
                    next_buys = [code for code in pending_target_codes if code not in holdings]
                    next_sells = [code for code in holdings if code in pending_force_sell_pool or code not in set(pending_target_codes)]
                rebalance_records.append(
                    {
                        "date": current_date.strftime("%Y-%m-%d"),
                        "buy_next": [f"{code} {pool.get(code, '')}" for code in next_buys],
                        "sell_next": [f"{code} {pool.get(code, '')}" for code in next_sells],
                        "bought": [f"{item['code']} {item['name']}" for item in bought_today],
                        "sold": [f"{item['code']} {item['name']}" for item in sold_today],
                    }
                )

        market_value = 0.0
        for code, holding in holdings.items():
            df = histories.get(code)
            if df is None:
                close_price = holding.cost_price
            elif current_date in df.index and pd.notna(df.loc[current_date, "close"]):
                close_price = float(df.loc[current_date, "close"])
            else:
                close_price = float(df["close"].asof(current_date) or holding.cost_price)
            market_value += holding.shares * close_price

        total_asset = cash + market_value
        records.append(
            {
                "date": current_date.strftime("%Y-%m-%d"),
                "equity": round(total_asset, 2),
                "return": total_asset / initial_capital - 1,
                "cash": round(cash, 2),
                "holdings": len(holdings),
                "market_status": market_state.get("status") if market_state.get("enabled") else None,
            }
        )

    final_date = trading_days.max()
    symbol_totals: dict[str, dict[str, Any]] = {}
    for trade in trade_records:
        totals = symbol_totals.setdefault(
            trade["code"],
            {
                "code": trade["code"],
                "name": trade["name"],
                "buy_amount": 0.0,
                "sell_amount": 0.0,
                "buy_count": 0,
                "sell_count": 0,
                "ending_shares": 0,
                "market_value": 0.0,
            },
        )
        if trade["action"] == "买入":
            totals["buy_amount"] += float(trade["amount"])
            totals["buy_count"] += 1
        else:
            totals["sell_amount"] += float(trade["amount"])
            totals["sell_count"] += 1

    for code, holding in holdings.items():
        totals = symbol_totals[code]
        df = histories.get(code)
        close_price = float(df["close"].asof(final_date)) if df is not None and pd.notna(df["close"].asof(final_date)) else holding.cost_price
        totals["ending_shares"] = holding.shares
        totals["market_value"] = holding.shares * close_price

    symbol_performance = []
    for totals in symbol_totals.values():
        profit = totals["sell_amount"] + totals["market_value"] - totals["buy_amount"]
        totals["profit"] = profit
        totals["profit_pct"] = profit / totals["buy_amount"] if totals["buy_amount"] else None
        totals["status"] = "持有" if totals["ending_shares"] else "已清仓"
        symbol_performance.append(totals)
    symbol_performance.sort(key=lambda row: row["profit"], reverse=True)

    curve = pd.DataFrame(records)
    curve["drawdown"] = _drawdown(curve["equity"])
    benchmark_name = BENCHMARKS.get(benchmark_code, benchmark_code)
    benchmark_return = None
    if benchmark_df is not None and not benchmark_df.empty:
        start_date = pd.to_datetime(curve["date"].iloc[0])
        first_price = benchmark_df["close"].asof(start_date)
        if pd.notna(first_price) and first_price > 0:
            curve[f"benchmark_{benchmark_code}"] = curve["date"].apply(
                lambda value: (benchmark_df["close"].asof(pd.to_datetime(value)) / first_price - 1)
                if pd.notna(benchmark_df["close"].asof(pd.to_datetime(value)))
                else None
            )
            benchmark_return = float(curve[f"benchmark_{benchmark_code}"].dropna().iloc[-1])

    total_return = float(curve["return"].iloc[-1])
    years = max(len(curve) / 252, 1 / 252)
    annualized_return = (1 + total_return) ** (1 / years) - 1 if total_return > -1 else -1
    max_drawdown = float(curve["drawdown"].min())
    metrics = {
        "initial_capital": initial_capital,
        "final_value": float(curve["equity"].iloc[-1]),
        "total_return": total_return,
        "annualized_return": annualized_return,
        "max_drawdown": max_drawdown,
        "benchmark_return": float(benchmark_return) if benchmark_return is not None else None,
        "alpha": float(total_return - benchmark_return) if benchmark_return is not None else None,
        "trading_days": len(curve),
        "symbols": len(histories),
        "requested_start_date": requested_start_date,
        "requested_end_date": requested_end_date,
        "actual_start_date": actual_start_date,
        "actual_end_date": actual_end_date,
        "first_trade_date": trade_records[0]["date"] if trade_records else None,
    }

    return {
        "generated_at": now_iso(),
        "pool_key": pool_key,
        "strategy": {
            "id": strategy.get("id"),
            "name": strategy.get("name", strategy.get("id")),
            "max_holdings": max_holdings,
        },
        "months": months,
        "start_date": start_date,
        "end_date": end_date,
        "execution_mode": execution_mode,
        "execution_mode_name": EXECUTION_MODES[execution_mode],
        "market_state": market_states[-1] if market_states else None,
        "benchmark": {"code": benchmark_code, "name": benchmark_name},
        "metrics": metrics,
        "data_coverage": {
            "requested_months": months,
            "requested_start_date": requested_start_date,
            "requested_end_date": requested_end_date,
            "actual_start_date": actual_start_date,
            "actual_end_date": actual_end_date,
            "first_trade_date": trade_records[0]["date"] if trade_records else None,
            "calendar_source": "large_cap_index",
            "calendar_priority": CALENDAR_PRIORITY,
        },
        "curve": normalize_records(curve),
        "rebalances": rebalance_records,
        "trades": trade_records,
        "symbol_performance": symbol_performance,
        "current_holdings": [{"code": code, "name": item.name, "shares": item.shares} for code, item in holdings.items()],
    }
