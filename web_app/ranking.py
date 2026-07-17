from __future__ import annotations

import glob
from pathlib import Path
from typing import Any

import pandas as pd

from .config import DATA_SOURCES, POOL_SPECS, ROOT
from .market_regime import runtime_overrides_for_market_filter
from .market_data import fetch_intraday_trends, fetch_spot, get_history, merge_spot_row
from .pools import load_pool_definitions
from .scoring import calculate_indicators, cross_sectional_score_and_rate, get_category, get_strategy_config
from .storage import load_account_holdings, read_cached_history
from .utils import normalize_records, now_iso

HISTORY_LOOKBACK_DAYS = 3000
HISTORY_CALENDAR_PRIORITY = ["510300", "563360", "510500", "510050", "588000", "159915"]
TREND_POINT_DAYS = 30


def _rank_change_text(previous_rank: Any, current_rank: int) -> str:
    if previous_rank is None or pd.isna(previous_rank):
        return "新进"
    previous_rank = int(previous_rank)
    diff = previous_rank - current_rank
    if diff > 0:
        return f"↑{diff}"
    if diff < 0:
        return f"↓{abs(diff)}"
    return "-"


def _close_trend_points(df: pd.DataFrame, end_date: pd.Timestamp | None = None) -> list[float]:
    if df is None or df.empty or "close" not in df.columns:
        return []
    closes = pd.to_numeric(df["close"], errors="coerce").dropna()
    if end_date is not None:
        closes = closes[closes.index <= end_date]
    values = closes.tail(TREND_POINT_DAYS)
    if len(values) < 2:
        return []
    return [round(float(value), 4) for value in values]


def _historical_date_index(code: str, before_or_on: pd.Timestamp) -> pd.Timestamp | None:
    df = read_cached_history(code, days=HISTORY_LOOKBACK_DAYS)
    if df is None or df.empty:
        return None
    eligible = df.index[df.index <= before_or_on]
    return eligible[-1] if not eligible.empty else None


def resolve_historical_date(requested_date: str, pools: dict[str, dict[str, str]]) -> pd.Timestamp:
    wanted = pd.to_datetime(requested_date, errors="coerce")
    if pd.isna(wanted):
        raise ValueError("历史打分日期格式无效")
    candidates = list(dict.fromkeys(HISTORY_CALENDAR_PRIORITY + [code for pool in pools.values() for code in pool]))
    for code in candidates:
        effective_date = _historical_date_index(code, wanted.normalize())
        if effective_date is not None:
            return effective_date.normalize()
    raise ValueError(f"{requested_date} 之前没有可用的本地历史数据")


def previous_rank_map(
    pool: dict[str, str],
    errors: list[str],
    strategy_id: str | None = None,
    scoring_date: pd.Timestamp | None = None,
    runtime_overrides: dict[str, Any] | None = None,
) -> dict[str, int]:
    rows: list[dict[str, Any]] = []
    for code, name in pool.items():
        try:
            df = read_cached_history(code, days=HISTORY_LOOKBACK_DAYS if scoring_date is not None else 120)
            if df is None or len(df) < 61:
                continue
            df = calculate_indicators(df.copy())
            if scoring_date is None:
                row = df.iloc[-1]
            else:
                previous_rows = df[df.index < scoring_date].dropna(subset=["close", "MA20", "MA60"])
                if previous_rows.empty:
                    continue
                row = previous_rows.iloc[-1]
            rows.append(
                {
                    "代码": code,
                    "名称": name,
                    "最新收盘价": row["close"],
                    "MA5": row["MA5"],
                    "MA15": row["MA15"],
                    "MA20": row["MA20"],
                    "MA60": row["MA60"],
                    "20日涨幅": row["return_20d"],
                    "量比": row["vol_ratio"],
                    "当日涨跌幅": row["return_1d"],
                }
            )
        except Exception as exc:
            errors.append(f"{code} 前日排名计算失败: {exc}")

    if not rows:
        return {}
    scored = cross_sectional_score_and_rate(pd.DataFrame(rows), strategy_id=strategy_id, runtime_overrides=runtime_overrides)
    if "代码" not in scored.columns:
        return {}
    return {str(code).zfill(6): idx + 1 for idx, code in enumerate(scored["代码"])}


def historical_score_pool(
    pool: dict[str, str],
    holdings: dict[str, dict[str, Any]],
    scoring_date: pd.Timestamp,
    errors: list[str],
    strategy_id: str | None = None,
    runtime_overrides: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for code, name in pool.items():
        holding = holdings.get(code, {})
        try:
            df = read_cached_history(code, days=HISTORY_LOOKBACK_DAYS)
            if df is None or len(df) < 60:
                continue
            df = calculate_indicators(df.copy()).dropna(subset=["close", "MA20", "MA60"])
            if scoring_date not in df.index:
                continue
            latest = df.loc[scoring_date]
            trend = _close_trend_points(df, scoring_date)
            rows.append(
                {
                    "代码": code,
                    "名称": name,
                    "日内走势": [],
                    "日线走势": trend,
                    "持仓": holding.get("持仓", ""),
                    "账户": holding.get("账户", ""),
                    "仓位占比": holding.get("仓位占比"),
                    "持仓市值": holding.get("持仓市值"),
                    "板块": get_category(name),
                    "最新收盘价": latest["close"],
                    "当日涨跌幅": latest["return_1d"],
                    "MA5": latest["MA5"],
                    "MA15": latest["MA15"],
                    "MA20": latest["MA20"],
                    "MA60": latest["MA60"],
                    "20日涨幅": latest["return_20d"],
                    "量比": latest["vol_ratio"],
                }
            )
        except Exception as exc:
            errors.append(f"{code} {scoring_date.strftime('%Y-%m-%d')} 历史评分失败: {exc}")

    if not rows:
        return []
    strategy = get_strategy_config(strategy_id)
    tolerance_count = int(strategy["tolerance_count"])
    scored = cross_sectional_score_and_rate(pd.DataFrame(rows), strategy_id=strategy_id, runtime_overrides=runtime_overrides)
    previous_ranks = previous_rank_map(pool, errors, strategy_id=strategy_id, scoring_date=scoring_date, runtime_overrides=runtime_overrides)
    previous_observation = {code for code, rank in previous_ranks.items() if rank <= tolerance_count}
    if "代码" in scored.columns:
        yesterday_ranks = []
        rank_changes = []
        top_warnings = []
        for idx, code in enumerate(scored["代码"]):
            code_str = str(code).zfill(6)
            rank = idx + 1
            previous_rank = previous_ranks.get(code_str)
            yesterday_ranks.append(previous_rank)
            rank_changes.append(_rank_change_text(previous_rank, rank))
            if rank <= tolerance_count and code_str not in previous_observation:
                top_warnings.append("新进观察区")
            elif rank > tolerance_count and code_str in previous_observation:
                top_warnings.append("掉出观察区")
            else:
                top_warnings.append("")
        scored["昨日排名"] = yesterday_ranks
        scored["排名变化"] = rank_changes
        scored["动态预警"] = top_warnings
    return _select_score_columns(scored)


def _select_score_columns(scored: pd.DataFrame) -> list[dict[str, Any]]:
    columns = [
        "代码", "名称", "日内走势", "日线走势", "持仓", "账户", "仓位占比", "持仓市值", "板块", "昨日排名", "排名变化",
        "动态预警", "评级", "最新收盘价", "当日涨跌幅", "MA5", "价格>MA5", "MA15", "价格>MA15", "MA20", "价格>MA20",
        "20日涨幅", "量比", "动量得分", "量能得分", "趋势得分", "综合总分",
    ]
    columns = [col for col in columns if col in scored.columns]
    return normalize_records(scored[columns])


def score_pool(
    key: str,
    pool: dict[str, str],
    holdings: dict[str, dict[str, Any]],
    source: str,
    refresh: bool,
    errors: list[str],
    strategy_id: str | None = None,
    runtime_overrides: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    spot = fetch_spot(pool, source, errors)
    intraday_trends = fetch_intraday_trends(pool, source, errors)
    rows: list[dict[str, Any]] = []

    for code, name in pool.items():
        holding = holdings.get(code, {})
        df = get_history(code, name, source, refresh, errors)
        if df is None or len(df) < 60:
            continue
        if code in spot:
            df = merge_spot_row(df, spot[code])

        try:
            df = calculate_indicators(df.copy())
            latest = df.iloc[-1]
            trend = _close_trend_points(df)
            spot_return = spot.get(code, {}).get("涨跌幅")
            if spot_return is not None and not pd.isna(spot_return):
                latest_return_1d = float(spot_return)
            else:
                latest_return_1d = latest["return_1d"]
            rows.append(
                {
                    "代码": code,
                    "名称": name,
                    "日内走势": intraday_trends.get(code, []),
                    "日线走势": trend,
                    "持仓": holding.get("持仓", ""),
                    "账户": holding.get("账户", ""),
                    "仓位占比": holding.get("仓位占比"),
                    "持仓市值": holding.get("持仓市值"),
                    "板块": get_category(name),
                    "最新收盘价": latest["close"],
                    "当日涨跌幅": latest_return_1d,
                    "MA5": latest["MA5"],
                    "MA15": latest["MA15"],
                    "MA20": latest["MA20"],
                    "MA60": latest["MA60"],
                    "20日涨幅": latest["return_20d"],
                    "量比": latest["vol_ratio"],
                }
            )
        except Exception as exc:
            errors.append(f"{code} 评分失败: {exc}")

    if not rows:
        return []

    strategy = get_strategy_config(strategy_id)
    tolerance_count = int(strategy["tolerance_count"])
    scored = cross_sectional_score_and_rate(pd.DataFrame(rows), strategy_id=strategy_id, runtime_overrides=runtime_overrides)
    previous_ranks = previous_rank_map(pool, errors, strategy_id=strategy_id, runtime_overrides=runtime_overrides)
    previous_observation = {code for code, rank in previous_ranks.items() if rank <= tolerance_count}

    if "代码" in scored.columns:
        yesterday_ranks = []
        rank_changes = []
        top_warnings = []
        for idx, code in enumerate(scored["代码"]):
            code_str = str(code).zfill(6)
            rank = idx + 1
            previous_rank = previous_ranks.get(code_str)
            yesterday_ranks.append(previous_rank)
            rank_changes.append(_rank_change_text(previous_rank, rank))
            if rank <= tolerance_count and code_str not in previous_observation:
                top_warnings.append(f"新进观察区")
            elif rank > tolerance_count and code_str in previous_observation:
                top_warnings.append(f"掉出观察区")
            else:
                top_warnings.append("")

        scored["昨日排名"] = yesterday_ranks
        scored["排名变化"] = rank_changes
        scored["动态预警"] = top_warnings

    return _select_score_columns(scored)


def latest_report_path() -> Path | None:
    files = [Path(path) for path in glob.glob(str(ROOT / "量化轮动打分报表_*.xlsx"))]
    if not files:
        return None
    return max(files, key=lambda path: path.stat().st_mtime)


def payload_from_latest_report(errors: list[str]) -> dict[str, Any] | None:
    path = latest_report_path()
    if path is None:
        return None
    data: dict[str, list[dict[str, Any]]] = {}
    try:
        for key, spec in POOL_SPECS.items():
            df = pd.read_excel(path, sheet_name=spec["sheet"])
            data[key] = normalize_records(df)
    except Exception as exc:
        errors.append(f"最新报表读取失败: {exc}")
        return None
    return {
        "source": "latest_report",
        "generated_at": pd.Timestamp.fromtimestamp(path.stat().st_mtime).isoformat(timespec="seconds"),
        "from_cache": True,
        "report_file": path.name,
        "pools": {key: {"title": POOL_SPECS[key]["title"], "rows": rows} for key, rows in data.items()},
        "errors": errors[-20:],
    }


def build_rankings(
    source: str = "tencent",
    refresh: bool = False,
    strategy_id: str | None = None,
    as_of_date: str | None = None,
) -> dict[str, Any]:
    if source not in DATA_SOURCES:
        raise ValueError(f"未知数据源: {source}")
    errors: list[str] = []
    try:
        pools = load_pool_definitions()
        holdings_by_pool = {
            "a_share": load_account_holdings("a_share"),
            "global": load_account_holdings("global"),
        }
        union_holdings = {**holdings_by_pool["a_share"], **holdings_by_pool["global"]}
        scoring_date = resolve_historical_date(as_of_date, pools) if as_of_date else None
        strategy = get_strategy_config(strategy_id)
        market_state = runtime_overrides_for_market_filter(strategy, scoring_date)
        runtime_overrides = market_state.get("runtime_overrides") or {}
        data = {}
        for key, pool in pools.items():
            holdings = holdings_by_pool.get(key, union_holdings)
            data[key] = {
                "title": POOL_SPECS[key]["title"],
                "holdings": len(holdings),
                "rows": historical_score_pool(pool, holdings, scoring_date, errors, strategy_id=strategy_id, runtime_overrides=runtime_overrides)
                if scoring_date is not None
                else score_pool(key, pool, holdings, source, False, errors, strategy_id=strategy_id, runtime_overrides=runtime_overrides),
            }

        total_rows = sum(len(group["rows"]) for group in data.values())
        if scoring_date is not None and total_rows == 0:
            raise ValueError(f"{scoring_date.strftime('%Y-%m-%d')} 本地库没有可用于打分的标的数据")
        if total_rows == 0:
            fallback = payload_from_latest_report(errors)
            if fallback:
                fallback["errors"] = errors[-20:]
                return fallback

        return {
            "source": "local_history" if scoring_date is not None else source,
            "strategy_id": strategy_id,
            "generated_at": now_iso(),
            "from_cache": scoring_date is not None,
            "report_file": None,
            "mode": "historical" if scoring_date is not None else "realtime",
            "requested_as_of_date": as_of_date,
            "as_of_date": scoring_date.strftime("%Y-%m-%d") if scoring_date is not None else None,
            "market_state": market_state if market_state.get("enabled") else None,
            "pools": data,
            "errors": errors[-20:],
        }
    except Exception as exc:
        errors.append(str(exc))
        if as_of_date:
            raise
        fallback = payload_from_latest_report(errors)
        if fallback:
            return fallback
        raise
