from __future__ import annotations

import importlib
import json
from typing import Any

import pandas as pd

from .app_state import STATE, STATE_LOCK, clear_payload
from .config import NEW_TECH_POOL_FILE
from .utils import now_iso

EXCLUDE_KEYWORDS = ["债", "货币", "日利", "添益", "国债", "信用", "短融", "300", "50", "1000", "2000"]


def _pick_column(df: pd.DataFrame, candidates: list[str]) -> str:
    for candidate in candidates:
        for column in df.columns:
            if candidate in str(column):
                return str(column)
    raise ValueError(f"ETF 实时列表缺少字段: {', '.join(candidates)}")


def _base_name(name: str) -> str:
    return name.split("ETF", 1)[0].strip() if "ETF" in name else name.strip()


def discover_active_tech_etfs(top_n: int = 100) -> dict[str, str]:
    ak = importlib.import_module("akshare")
    etf_df = ak.fund_etf_category_sina(symbol="ETF基金")
    if etf_df is None or etf_df.empty:
        raise RuntimeError("akshare 返回空 ETF 列表")

    etf_df = etf_df.copy()
    etf_df.columns = [str(col).strip() for col in etf_df.columns]
    code_col = _pick_column(etf_df, ["代码"])
    name_col = _pick_column(etf_df, ["名称"])
    amount_col = _pick_column(etf_df, ["成交额"])

    name_series = etf_df[name_col].astype(str)
    exclude_pattern = "|".join(EXCLUDE_KEYWORDS)
    tech_df = etf_df[~name_series.str.contains(exclude_pattern, na=False)].copy()
    tech_df[amount_col] = pd.to_numeric(tech_df[amount_col], errors="coerce").fillna(0)
    tech_df = tech_df.sort_values(by=amount_col, ascending=False)

    result: dict[str, str] = {}
    seen_base_names: set[str] = set()
    for _, row in tech_df.iterrows():
        code = "".join(ch for ch in str(row[code_col]) if ch.isdigit())[-6:]
        name = str(row[name_col]).strip()
        if len(code) != 6 or not name:
            continue
        base_name = _base_name(name)
        if base_name in seen_base_names:
            continue
        seen_base_names.add(base_name)
        result[code] = name
        if len(result) >= top_n:
            break

    if not result:
        raise RuntimeError("未发现可用活跃 ETF")
    return result


def save_new_tech_pool(pool: dict[str, str], top_n: int) -> dict[str, Any]:
    NEW_TECH_POOL_FILE.parent.mkdir(exist_ok=True)
    payload = {
        "updated_at": now_iso(),
        "source": "akshare.fund_etf_category_sina",
        "top_n": top_n,
        "count": len(pool),
        "pool": pool,
    }
    NEW_TECH_POOL_FILE.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    clear_payload()
    return payload


def load_new_tech_pool_override() -> dict[str, Any] | None:
    if not NEW_TECH_POOL_FILE.exists():
        return None
    payload = json.loads(NEW_TECH_POOL_FILE.read_text(encoding="utf-8"))
    pool = payload.get("pool")
    if not isinstance(pool, dict) or not pool:
        return None
    payload["pool"] = {str(code).zfill(6): str(name) for code, name in pool.items()}
    payload["count"] = len(payload["pool"])
    return payload


def tech_pool_status() -> dict[str, Any]:
    payload = load_new_tech_pool_override()
    with STATE_LOCK:
        return {
            "updating": STATE["tech_pool_updating"],
            "started": STATE["tech_pool_update_started"],
            "finished": STATE["tech_pool_update_finished"],
            "last_error": STATE["tech_pool_update_last_error"],
            "result": STATE["tech_pool_update_result"],
            "override_exists": payload is not None,
            "override": {
                "updated_at": payload.get("updated_at"),
                "source": payload.get("source"),
                "top_n": payload.get("top_n"),
                "count": payload.get("count"),
            }
            if payload
            else None,
        }


def update_tech_pool_state(top_n: int = 100) -> None:
    started = now_iso()
    with STATE_LOCK:
        STATE["tech_pool_updating"] = True
        STATE["tech_pool_update_started"] = started
        STATE["tech_pool_update_finished"] = None
        STATE["tech_pool_update_last_error"] = None
        STATE["tech_pool_update_result"] = None
    try:
        pool = discover_active_tech_etfs(top_n=top_n)
        result = save_new_tech_pool(pool, top_n=top_n)
        with STATE_LOCK:
            STATE["tech_pool_update_finished"] = now_iso()
            STATE["tech_pool_update_result"] = {
                "started_at": started,
                "finished_at": STATE["tech_pool_update_finished"],
                "count": result["count"],
                "top_n": result["top_n"],
                "updated_at": result["updated_at"],
                "source": result["source"],
            }
            STATE["tech_pool_update_last_error"] = None
        print(f"[tech-pool] updated active tech pool count={result['count']}", flush=True)
    except Exception as exc:
        with STATE_LOCK:
            STATE["tech_pool_update_finished"] = now_iso()
            STATE["tech_pool_update_last_error"] = str(exc)
            STATE["tech_pool_update_result"] = None
        print(f"[tech-pool] update failed: {exc}", flush=True)
    finally:
        with STATE_LOCK:
            STATE["tech_pool_updating"] = False
