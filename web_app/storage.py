from __future__ import annotations

import sqlite3
from typing import Any

import pandas as pd

from .config import ACCOUNT_POOL_KEYS, CACHE_DB, CACHE_DIR, DATA_DIR, POOL_SPECS
from .pools import all_unique_etfs, load_legacy_hold_pool
from .utils import now_iso


def init_cache_db() -> None:
    DATA_DIR.mkdir(exist_ok=True)
    with sqlite3.connect(CACHE_DB) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS etf_history (
                code TEXT NOT NULL,
                date TEXT NOT NULL,
                open REAL,
                close REAL,
                high REAL,
                low REAL,
                volume REAL,
                amount REAL,
                source TEXT NOT NULL DEFAULT 'akshare_em',
                updated_at TEXT NOT NULL,
                PRIMARY KEY (code, date)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS cache_meta (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS account_holdings (
                pool_key TEXT NOT NULL,
                code TEXT NOT NULL,
                name TEXT,
                shares REAL,
                market_value REAL,
                cost_price REAL,
                current_price REAL,
                pnl REAL,
                pnl_pct REAL,
                weight_pct REAL,
                source_file TEXT,
                updated_at TEXT NOT NULL,
                PRIMARY KEY (pool_key, code)
            )
            """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_etf_history_code_date ON etf_history(code, date)")


def parse_float(value: str | None) -> float | None:
    if value is None:
        return None
    cleaned = str(value).replace(",", "").replace("%", "").strip()
    if not cleaned:
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def _normalize_header(value: str) -> str:
    return str(value).replace("\ufeff", "").replace(" ", "").replace("\u3000", "").strip()


def _pick_value(row: dict[str, str], headers: list[str]) -> str | None:
    for header in headers:
        value = row.get(_normalize_header(header))
        if value is not None and str(value).strip():
            return value
    return None


def _parse_holdings_by_header(text: str) -> list[dict[str, Any]]:
    lines = [line for line in text.splitlines() if line.strip()]
    if not lines:
        return []
    header_parts = [_normalize_header(part) for part in lines[0].split("\t")]
    if not any(header in header_parts for header in ("证券代码", "股票代码", "代码")):
        return []

    rows: list[dict[str, Any]] = []
    seen_codes: set[str] = set()
    for line in lines[1:]:
        values = [part.strip() for part in line.split("\t")]
        if len(values) < 2:
            continue
        row = {header: values[idx] if idx < len(values) else "" for idx, header in enumerate(header_parts)}
        code = _pick_value(row, ["证券代码", "股票代码", "代码"])
        if code is None or not code.isdigit() or len(code) != 6:
            continue
        if code in seen_codes:
            continue
        seen_codes.add(code)
        rows.append(
            {
                "code": code,
                "name": _pick_value(row, ["证券名称", "股票名称", "名称"]) or "",
                "market_value": parse_float(_pick_value(row, ["市值", "持仓市值", "证券市值", "参考市值"])),
                "shares": parse_float(_pick_value(row, ["实际数量", "股票余额", "持仓数量", "证券数量", "股份余额", "当前持仓"])),
                "pnl": parse_float(_pick_value(row, ["盈亏", "持仓盈亏", "浮动盈亏"])),
                "pnl_pct": parse_float(_pick_value(row, ["盈亏比例(%)", "盈亏比例", "持仓盈亏比例", "浮动盈亏比例"])),
                "weight_pct": parse_float(_pick_value(row, ["仓位占比(%)", "仓位占比", "持仓占比"])),
                "current_price": parse_float(_pick_value(row, ["市价", "现价", "最新价", "当前价"])),
                "cost_price": parse_float(_pick_value(row, ["成本价", "成本价格", "持仓成本价"])),
            }
        )
    return rows


def parse_holdings_text(content: bytes) -> list[dict[str, Any]]:
    text = None
    for encoding in ("utf-8", "gb18030", "gbk", "gb2312"):
        try:
            text = content.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    if text is None:
        text = content.decode("utf-8", errors="ignore")

    header_rows = _parse_holdings_by_header(text)
    if header_rows:
        return header_rows

    rows: list[dict[str, Any]] = []
    seen_codes: set[str] = set()
    for line in text.splitlines()[1:]:
        parts = [part.strip() for part in line.replace("\t", " ").split() if part.strip()]
        if len(parts) < 4:
            continue
        code_index = None
        for idx, token in enumerate(parts[:5]):
            if token.isdigit() and len(token) == 6:
                code_index = idx
                break
        if code_index is None:
            continue

        code = parts[code_index]
        if code in seen_codes:
            continue
        seen_codes.add(code)
        rows.append(
            {
                "code": code,
                "name": parts[code_index + 1] if code_index + 1 < len(parts) else "",
                "market_value": parse_float(parts[code_index + 2] if code_index + 2 < len(parts) else None),
                "shares": parse_float(parts[code_index + 3] if code_index + 3 < len(parts) else None),
                "pnl": parse_float(parts[code_index + 4] if code_index + 4 < len(parts) else None),
                "pnl_pct": parse_float(parts[code_index + 5] if code_index + 5 < len(parts) else None),
                "weight_pct": parse_float(parts[code_index + 8] if code_index + 8 < len(parts) else None),
                "current_price": parse_float(parts[code_index + 11] if code_index + 11 < len(parts) else None),
                "cost_price": parse_float(parts[code_index + 12] if code_index + 12 < len(parts) else None),
            }
        )
    return rows


def save_account_holdings(pool_key: str, holdings: list[dict[str, Any]], source_file: str | None = None) -> dict[str, Any]:
    if pool_key not in ACCOUNT_POOL_KEYS:
        raise ValueError("只支持 A 股板块轮动 和 全球与大宗配置 两个账户上传持仓")
    init_cache_db()
    updated_at = now_iso()
    with sqlite3.connect(CACHE_DB) as conn:
        conn.execute("DELETE FROM account_holdings WHERE pool_key = ?", (pool_key,))
        conn.executemany(
            """
            INSERT INTO account_holdings (
                pool_key, code, name, shares, market_value, cost_price, current_price,
                pnl, pnl_pct, weight_pct, source_file, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    pool_key,
                    row["code"],
                    row.get("name"),
                    row.get("shares"),
                    row.get("market_value"),
                    row.get("cost_price"),
                    row.get("current_price"),
                    row.get("pnl"),
                    row.get("pnl_pct"),
                    row.get("weight_pct"),
                    source_file,
                    updated_at,
                )
                for row in holdings
            ],
        )
        conn.execute("INSERT OR REPLACE INTO cache_meta (key, value) VALUES (?, ?)", (f"holdings:{pool_key}:updated_at", updated_at))
        if source_file:
            conn.execute("INSERT OR REPLACE INTO cache_meta (key, value) VALUES (?, ?)", (f"holdings:{pool_key}:source_file", source_file))
    return {"pool_key": pool_key, "count": len(holdings), "updated_at": updated_at, "source_file": source_file}


def load_account_holdings(pool_key: str | None = None) -> dict[str, dict[str, Any]]:
    if not CACHE_DB.exists():
        if pool_key in (None, "a_share"):
            return {code: {"code": code, "持仓": "★ 持有", "账户": "A 股板块轮动"} for code in load_legacy_hold_pool()}
        return {}
    init_cache_db()
    query = "SELECT * FROM account_holdings"
    params: tuple[Any, ...] = ()
    if pool_key is not None:
        query += " WHERE pool_key = ?"
        params = (pool_key,)
    with sqlite3.connect(CACHE_DB) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(query, params).fetchall()

    result: dict[str, dict[str, Any]] = {}
    for row in rows:
        account = POOL_SPECS.get(row["pool_key"], {}).get("title", row["pool_key"])
        result[row["code"]] = {
            "code": row["code"],
            "持仓": "★ 持有",
            "账户": account,
            "持仓名称": row["name"],
            "持仓市值": row["market_value"],
            "持仓数量": row["shares"],
            "成本价": row["cost_price"],
            "持仓现价": row["current_price"],
            "持仓盈亏": row["pnl"],
            "持仓盈亏比例": row["pnl_pct"],
            "仓位占比": row["weight_pct"],
            "持仓更新时间": row["updated_at"],
        }
    if not result and pool_key == "a_share":
        return {code: {"code": code, "持仓": "★ 持有", "账户": POOL_SPECS["a_share"]["title"]} for code in load_legacy_hold_pool()}
    return result


def holdings_status() -> dict[str, Any]:
    init_cache_db()
    status: dict[str, Any] = {}
    with sqlite3.connect(CACHE_DB) as conn:
        conn.row_factory = sqlite3.Row
        for key in ACCOUNT_POOL_KEYS:
            count = conn.execute("SELECT COUNT(*) AS c FROM account_holdings WHERE pool_key = ?", (key,)).fetchone()["c"]
            updated = conn.execute("SELECT value FROM cache_meta WHERE key = ?", (f"holdings:{key}:updated_at",)).fetchone()
            source = conn.execute("SELECT value FROM cache_meta WHERE key = ?", (f"holdings:{key}:source_file",)).fetchone()
            status[key] = {
                "title": POOL_SPECS[key]["title"],
                "count": count,
                "updated_at": updated["value"] if updated else None,
                "source_file": source["value"] if source else None,
            }
    return status


def read_sqlite_history(code: str, days: int = 100) -> pd.DataFrame | None:
    if not CACHE_DB.exists():
        return None
    init_cache_db()
    with sqlite3.connect(CACHE_DB) as conn:
        df = pd.read_sql_query(
            """
            SELECT date, open, close, high, low, volume, amount
            FROM etf_history
            WHERE code = ?
            ORDER BY date DESC
            LIMIT ?
            """,
            conn,
            params=(code, days),
        )
    if df.empty:
        return None
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").set_index("date")
    for col in ["open", "close", "high", "low", "volume", "amount"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


def read_cached_history(code: str, days: int = 100) -> pd.DataFrame | None:
    sqlite_df = read_sqlite_history(code, days=days)
    if sqlite_df is not None:
        return sqlite_df

    cache_file = CACHE_DIR / f"{code}.csv"
    if not cache_file.exists():
        return None
    df = pd.read_csv(cache_file, parse_dates=["date"])
    if df.empty:
        return None
    df.columns = [str(col).strip().lower() for col in df.columns]
    required = {"date", "open", "close", "high", "low", "volume"}
    if not required.issubset(df.columns):
        return None
    if "amount" not in df.columns:
        df["amount"] = 0.0
    df = df.sort_values("date").set_index("date")
    for col in ["open", "close", "high", "low", "volume", "amount"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    return df.tail(days).copy()


def normalize_em_history(df: pd.DataFrame) -> pd.DataFrame:
    df = df.rename(
        columns={
            "日期": "date",
            "开盘": "open",
            "收盘": "close",
            "最高": "high",
            "最低": "low",
            "成交量": "volume",
            "成交额": "amount",
        }
    ).copy()
    required = ["date", "open", "close", "high", "low", "volume", "amount"]
    missing = [col for col in required if col not in df.columns]
    if missing:
        raise ValueError(f"EM 数据缺少字段: {', '.join(missing)}")
    df["date"] = pd.to_datetime(df["date"])
    for col in ["open", "close", "high", "low", "volume", "amount"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df["volume"] = df["volume"] * 100
    return df.sort_values("date").dropna(subset=["date", "close"])


def write_history_to_sqlite(code: str, df: pd.DataFrame, source: str = "akshare_em") -> int:
    init_cache_db()
    updated_at = now_iso()
    records = [
        (
            code,
            pd.to_datetime(row.date).strftime("%Y-%m-%d"),
            float(row.open) if pd.notna(row.open) else None,
            float(row.close) if pd.notna(row.close) else None,
            float(row.high) if pd.notna(row.high) else None,
            float(row.low) if pd.notna(row.low) else None,
            float(row.volume) if pd.notna(row.volume) else None,
            float(row.amount) if pd.notna(row.amount) else None,
            source,
            updated_at,
        )
        for row in df.itertuples(index=False)
    ]
    with sqlite3.connect(CACHE_DB) as conn:
        conn.executemany(
            """
            INSERT INTO etf_history (code, date, open, close, high, low, volume, amount, source, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(code, date) DO UPDATE SET
                open = excluded.open,
                close = excluded.close,
                high = excluded.high,
                low = excluded.low,
                volume = excluded.volume,
                amount = excluded.amount,
                source = excluded.source,
                updated_at = excluded.updated_at
            """,
            records,
        )
        conn.execute("INSERT OR REPLACE INTO cache_meta (key, value) VALUES (?, ?)", (f"{code}:updated_at", updated_at))
        conn.execute("INSERT OR REPLACE INTO cache_meta (key, value) VALUES (?, ?)", ("last_update", updated_at))
    return len(records)


def previous_trading_target_date() -> str:
    return (pd.Timestamp.now().normalize() - pd.offsets.BDay(1)).strftime("%Y-%m-%d")


def cache_stats() -> dict[str, Any]:
    target_date = previous_trading_target_date()
    target_codes = list(all_unique_etfs())
    target_total = len(target_codes)
    stats: dict[str, Any] = {
        "store": str(CACHE_DB),
        "sqlite_exists": CACHE_DB.exists(),
        "target_date": target_date,
        "target_symbols": target_total,
        "symbols": 0,
        "rows": 0,
        "min_date": None,
        "max_date": None,
        "last_update": None,
        "up_to_date": False,
        "up_to_date_symbols": 0,
        "stale_symbols": target_total,
    }
    if CACHE_DB.exists():
        init_cache_db()
        with sqlite3.connect(CACHE_DB) as conn:
            row = conn.execute("SELECT COUNT(DISTINCT code), COUNT(*), MIN(date), MAX(date) FROM etf_history").fetchone()
            if target_codes:
                placeholders = ",".join("?" for _ in target_codes)
                coverage = conn.execute(
                    f"""
                    SELECT COUNT(*) AS total,
                           SUM(CASE WHEN max_date >= ? THEN 1 ELSE 0 END) AS current_count
                    FROM (
                        SELECT code, MAX(date) AS max_date
                        FROM etf_history
                        WHERE code IN ({placeholders})
                        GROUP BY code
                    )
                    """,
                    (target_date, *target_codes),
                ).fetchone()
            else:
                coverage = (0, 0)
            stats.update(
                {
                    "symbols": row[0] or 0,
                    "rows": row[1] or 0,
                    "min_date": row[2],
                    "max_date": row[3],
                    "cached_target_symbols": coverage[0] or 0,
                    "up_to_date_symbols": coverage[1] or 0,
                }
            )
            stats["stale_symbols"] = max(target_total - int(stats["up_to_date_symbols"]), 0)
            stats["up_to_date"] = bool(target_total and stats["up_to_date_symbols"] >= target_total)
            meta = conn.execute("SELECT value FROM cache_meta WHERE key = 'last_update'").fetchone()
            stats["last_update"] = meta[0] if meta else None

    if stats["symbols"] == 0 and CACHE_DIR.exists():
        latest_dates = []
        csv_count = 0
        for csv_file in CACHE_DIR.glob("*.csv"):
            try:
                df = pd.read_csv(csv_file, usecols=["date"])
                if not df.empty:
                    csv_count += 1
                    latest_dates.append(str(pd.to_datetime(df["date"]).max().date()))
            except Exception:
                continue
        if latest_dates:
            stats.update(
                {
                    "fallback_csv_symbols": csv_count,
                    "fallback_csv_max_date": max(latest_dates),
                    "fallback_csv_min_latest_date": min(latest_dates),
                }
            )
            stats["up_to_date"] = max(latest_dates) >= target_date
    return stats
