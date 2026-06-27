from __future__ import annotations

from typing import Any

import pandas as pd

from .scoring import calculate_indicators
from .storage import read_cached_history


def _add_cross_indicators(df: pd.DataFrame) -> pd.DataFrame:
    df = calculate_indicators(df.copy())
    df["MA5"] = df["close"].rolling(window=5).mean()
    ema12 = df["close"].ewm(span=12, adjust=False).mean()
    ema26 = df["close"].ewm(span=26, adjust=False).mean()
    df["DIF"] = ema12 - ema26
    df["DEA"] = df["DIF"].ewm(span=9, adjust=False).mean()
    df["MACD"] = (df["DIF"] - df["DEA"]) * 2
    return df


def _cross_signal(
    df: pd.DataFrame,
    fast_col: str,
    slow_col: str,
    label: str,
    fast_name: str,
    slow_name: str,
) -> dict[str, Any] | None:
    valid = df.dropna(subset=[fast_col, slow_col])
    if valid.empty:
        return None
    relation = valid[fast_col] >= valid[slow_col]
    current = bool(relation.iloc[-1])
    event = ""
    if len(relation) >= 2:
        previous = bool(relation.iloc[-2])
        if not previous and current:
            event = "当日金叉"
        elif previous and not current:
            event = "当日死叉"

    last_cross_date = None
    last_cross_type = None
    if len(relation) >= 2:
        changes = relation[relation != relation.shift(1)]
        changes = changes.iloc[1:] if len(changes) else changes
        if not changes.empty:
            last_cross_date = changes.index[-1].strftime("%Y-%m-%d")
            last_cross_type = "金叉" if bool(changes.iloc[-1]) else "死叉"

    return {
        "key": label,
        "name": label,
        "fast_name": fast_name,
        "slow_name": slow_name,
        "fast": float(valid[fast_col].iloc[-1]),
        "slow": float(valid[slow_col].iloc[-1]),
        "state": "金叉" if current else "死叉",
        "is_bullish": current,
        "event": event,
        "last_cross_date": last_cross_date,
        "last_cross_type": last_cross_type,
    }


def runtime_overrides_for_market_filter(strategy: dict[str, Any], as_of_date: pd.Timestamp | None = None, days: int = 240) -> dict[str, Any]:
    market_filter = strategy.get("market_filter")
    if not market_filter:
        return {"enabled": False, "runtime_overrides": {}}

    symbol = str(market_filter.get("symbol", "")).zfill(6)
    df = read_cached_history(symbol, days=days)
    if df is None or df.empty:
        return {
            "enabled": True,
            "available": False,
            "symbol": symbol,
            "name": market_filter.get("name", symbol),
            "runtime_overrides": {},
            "message": f"{symbol} 本地库缺少大盘过滤数据",
        }

    df = _add_cross_indicators(df.copy()).dropna(subset=["close", "MA5", "MA20", "MA60", "DIF", "DEA"])
    if df.empty:
        return {
            "enabled": True,
            "available": False,
            "symbol": symbol,
            "name": market_filter.get("name", symbol),
            "runtime_overrides": {},
            "message": f"{symbol} 均线/MACD 数据不足",
        }

    if as_of_date is not None:
        eligible = df[df.index <= pd.to_datetime(as_of_date).normalize()]
        if eligible.empty:
            return {
                "enabled": True,
                "available": False,
                "symbol": symbol,
                "name": market_filter.get("name", symbol),
                "runtime_overrides": {},
                "message": f"{symbol} 在所选日期前没有可用数据",
            }
        row = eligible.iloc[-1]
        date = eligible.index[-1]
    else:
        row = df.iloc[-1]
        date = df.index[-1]

    eligible_for_signals = df[df.index <= date]
    signals = {
        "medium_trend": _cross_signal(eligible_for_signals, "MA20", "MA60", "中线趋势", "MA20", "MA60"),
        "short_trade": _cross_signal(eligible_for_signals, "MA5", "MA20", "短线博弈", "MA5", "MA20"),
        "macd": _cross_signal(eligible_for_signals, "DIF", "DEA", "MACD", "DIF", "DEA"),
    }
    signals = {key: value for key, value in signals.items() if value is not None}
    control_signal = market_filter.get("control_signal", "medium_trend")
    controlled = signals.get(control_signal)
    risk_off = bool(controlled and not controlled["is_bullish"])
    position_ratio = float(market_filter.get("risk_off_position_ratio", 0.5)) if risk_off else 1.0
    signal_summary = "，".join(f"{item['name']}{item['state']}" for item in signals.values())
    control_name = controlled["name"] if controlled else control_signal

    return {
        "enabled": True,
        "available": True,
        "symbol": symbol,
        "name": market_filter.get("name", symbol),
        "date": date.strftime("%Y-%m-%d"),
        "fast_ma": float(row["MA20"]),
        "slow_ma": float(row["MA60"]),
        "fast_ma_name": "MA20",
        "slow_ma_name": "MA60",
        "signals": signals,
        "signal_summary": signal_summary,
        "control_signal": control_signal,
        "control_signal_name": control_name,
        "risk_off": risk_off,
        "status": f"{control_name}死叉半仓" if risk_off else f"{control_name}金叉/恢复",
        "position_ratio": position_ratio,
        "runtime_overrides": {},
    }
