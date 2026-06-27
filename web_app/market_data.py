from __future__ import annotations

import importlib
import urllib.request
from datetime import datetime
from typing import Any

import pandas as pd

from .storage import read_cached_history


def market_prefix(code: str) -> str:
    return "sh" if str(code).startswith(("5", "6")) else "sz"


def yfinance_symbol(code: str) -> str:
    return f"{code}.SS" if str(code).startswith(("5", "6", "16")) else f"{code}.SZ"


def first_value(mapping: dict[str, Any], keys: list[str], default: Any = None) -> Any:
    for key in keys:
        if key in mapping and mapping[key] not in (None, ""):
            return mapping[key]
    return default


def normalize_quote_date(value: Any) -> pd.Timestamp | None:
    if value in (None, ""):
        return None
    text = str(value).strip()
    if not text:
        return None
    if text.isdigit() and len(text) >= 8:
        text = text[:8]
    try:
        return pd.to_datetime(text).normalize()
    except Exception:
        return None


def merge_spot_row(df: pd.DataFrame, spot: dict[str, Any]) -> pd.DataFrame:
    latest = first_value(spot, ["最新价", "最新价格", "最新", "最新收盘价"])
    if latest is None:
        return df

    quote_date = normalize_quote_date(first_value(spot, ["交易日期", "日期", "quote_date"]))
    today = quote_date or pd.to_datetime(datetime.now().strftime("%Y-%m-%d"))
    row = {
        "open": first_value(spot, ["开盘价", "开盘"], latest),
        "close": latest,
        "high": first_value(spot, ["最高价", "最高"], latest),
        "low": first_value(spot, ["最低价", "最低"], latest),
        "volume": first_value(spot, ["成交量"], 0),
        "amount": first_value(spot, ["成交额"], 0),
    }
    try:
        row = {key: float(value) for key, value in row.items()}
    except (TypeError, ValueError):
        return df

    df = df.copy()
    if len(df.index) and pd.to_datetime(df.index[-1]).normalize() == today:
        df.loc[df.index[-1], list(row.keys())] = list(row.values())
    else:
        df.loc[today] = row
    return df


def fetch_spot_tencent(pool: dict[str, str]) -> dict[str, dict[str, Any]]:
    stock_codes = [f"{market_prefix(code)}{code}" for code in pool]
    url = "http://qt.gtimg.cn/q=" + ",".join(stock_codes)
    with urllib.request.urlopen(url, timeout=8) as response:
        lines = response.read().decode("gbk", errors="ignore").strip().split("\n")

    spot: dict[str, dict[str, Any]] = {}
    for line in lines:
        if "=" not in line:
            continue
        left, right = line.split("=", 1)
        code = left.split("_")[-1][2:]
        data = right.strip('";').split("~")
        if len(data) <= 37:
            continue
        try:
            current = float(data[3])
            if current <= 0:
                continue
            spot[code] = {
                "最新价": current,
                "昨收": float(data[4]),
                "涨跌幅": current / float(data[4]) - 1 if float(data[4]) else None,
                "开盘价": float(data[5]),
                "最高价": float(data[33]),
                "最低价": float(data[34]),
                "成交量": float(data[36]) * 100,
                "成交额": float(data[37]) * 10000,
                "交易日期": data[30] if len(data) > 30 else None,
            }
        except ValueError:
            continue
    return spot


def fetch_spot_sina(pool: dict[str, str]) -> dict[str, dict[str, Any]]:
    stock_codes = [f"{market_prefix(code)}{code}" for code in pool]
    url = "https://hq.sinajs.cn/list=" + ",".join(stock_codes)
    req = urllib.request.Request(url, headers={"Referer": "https://finance.sina.com.cn"})
    with urllib.request.urlopen(req, timeout=8) as response:
        lines = response.read().decode("gbk", errors="ignore").strip().split("\n")

    spot: dict[str, dict[str, Any]] = {}
    for line in lines:
        if "=" not in line:
            continue
        left, right = line.split("=", 1)
        code = left.split("_")[-1][2:]
        data = right.strip('";').split(",")
        if len(data) <= 10:
            continue
        try:
            current = float(data[3])
            if current <= 0:
                continue
            spot[code] = {
                "开盘价": float(data[1]),
                "昨收": float(data[2]),
                "最新价": current,
                "涨跌幅": current / float(data[2]) - 1 if float(data[2]) else None,
                "最高价": float(data[4]),
                "最低价": float(data[5]),
                "成交量": float(data[8]),
                "成交额": float(data[9]),
                "交易日期": data[30] if len(data) > 30 else None,
            }
        except ValueError:
            continue
    return spot


def fetch_spot_yfinance(pool: dict[str, str]) -> dict[str, dict[str, Any]]:
    yf = importlib.import_module("yfinance")
    spot: dict[str, dict[str, Any]] = {}
    for code in pool:
        ticker = yf.Ticker(yfinance_symbol(code))
        hist = ticker.history(period="5d")
        if hist is None or hist.empty:
            continue
        latest = hist.iloc[-1]
        prev = hist.iloc[-2] if len(hist) > 1 else latest
        try:
            spot[code] = {
                "最新价": float(latest["Close"]),
                "昨收": float(prev["Close"]),
                "涨跌幅": float(latest["Close"]) / float(prev["Close"]) - 1 if float(prev["Close"]) else None,
                "开盘价": float(latest["Open"]),
                "最高价": float(latest["High"]),
                "最低价": float(latest["Low"]),
                "成交量": float(latest["Volume"]),
                "成交额": 0,
                "交易日期": latest.name.strftime("%Y-%m-%d") if hasattr(latest.name, "strftime") else None,
            }
        except (KeyError, TypeError, ValueError):
            continue
    return spot


def fetch_spot_em(pool: dict[str, str]) -> dict[str, dict[str, Any]]:
    ak = importlib.import_module("akshare")
    raw = ak.fund_etf_spot_em()
    if raw is None or raw.empty:
        return {}
    raw = raw.copy()
    raw.columns = [str(col).strip() for col in raw.columns]

    def col(*names: str) -> str | None:
        for name in names:
            for candidate in raw.columns:
                if name in candidate:
                    return candidate
        return None

    code_col = col("代码")
    price_col = col("最新价")
    open_col = col("开盘")
    high_col = col("最高")
    low_col = col("最低")
    volume_col = col("成交量")
    amount_col = col("成交额")
    pct_col = col("涨跌幅")
    if not code_col or not price_col:
        return {}

    wanted = set(pool)
    spot: dict[str, dict[str, Any]] = {}
    for _, row in raw.iterrows():
        code = "".join(ch for ch in str(row[code_col]) if ch.isdigit())[-6:]
        if code not in wanted:
            continue
        try:
            latest = float(row[price_col])
            if latest <= 0:
                continue
            spot[code] = {
                "最新价": latest,
                "涨跌幅": float(row[pct_col]) / 100 if pct_col else None,
                "开盘价": float(row[open_col]) if open_col else latest,
                "最高价": float(row[high_col]) if high_col else latest,
                "最低价": float(row[low_col]) if low_col else latest,
                "成交量": float(row[volume_col]) if volume_col else 0,
                "成交额": float(row[amount_col]) if amount_col else 0,
            }
        except (TypeError, ValueError):
            continue
    return spot


def fetch_spot(pool: dict[str, str], source: str, errors: list[str]) -> dict[str, dict[str, Any]]:
    try:
        if source == "tencent":
            return fetch_spot_tencent(pool)
        if source == "sina":
            return fetch_spot_sina(pool)
        if source == "em":
            return fetch_spot_em(pool)
        if source == "yfinance":
            return fetch_spot_yfinance(pool)
        return {}
    except Exception as exc:
        errors.append(f"{source} 实时行情不可用: {exc}")
        return {}


def get_history(code: str, name: str, source: str, refresh: bool, errors: list[str]) -> pd.DataFrame | None:
    if refresh:
        errors.append(f"{code} 历史刷新已迁移到“更新本地库”按钮，排名计算使用本地库")

    try:
        return read_cached_history(code, days=100)
    except Exception as exc:
        errors.append(f"{code} 本地库读取失败: {exc}")
        return None
