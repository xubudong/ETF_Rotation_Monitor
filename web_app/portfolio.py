from __future__ import annotations

import json
import sqlite3
from functools import lru_cache
from typing import Any

from .config import ACCOUNT_POOL_KEYS, CACHE_DB, PORTFOLIO_INDUSTRY_FILE, POOL_SPECS
from .storage import init_cache_db
from .utils import normalize_value, now_iso


def _load_industry_config() -> dict[str, Any]:
    if not PORTFOLIO_INDUSTRY_FILE.exists():
        return {}
    return json.loads(PORTFOLIO_INDUSTRY_FILE.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def industry_mapping() -> dict[str, dict[str, float]]:
    mapping = _load_industry_config().get("industry_mapping", {})
    return {
        str(code).zfill(6): {str(industry): float(weight) for industry, weight in weights.items()}
        for code, weights in mapping.items()
        if isinstance(weights, dict)
    }


@lru_cache(maxsize=1)
def shenwan_mapping() -> dict[str, str]:
    mapping = _load_industry_config().get("shenwan_mapping", {})
    return {str(secondary): str(primary) for secondary, primary in mapping.items()}


def load_portfolio_rows(pool_key: str = "all") -> list[dict[str, Any]]:
    if pool_key != "all" and pool_key not in ACCOUNT_POOL_KEYS:
        raise ValueError("pool_key 只支持 a_share/global/all")
    init_cache_db()
    query = """
        SELECT pool_key, code, name, market_value, weight_pct, updated_at
        FROM account_holdings
        WHERE market_value IS NOT NULL AND market_value > 0
    """
    params: tuple[Any, ...] = ()
    if pool_key != "all":
        query += " AND pool_key = ?"
        params = (pool_key,)

    with sqlite3.connect(CACHE_DB) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(query, params).fetchall()

    combined: dict[str, dict[str, Any]] = {}
    for row in rows:
        code = str(row["code"]).zfill(6)
        if code not in combined:
            combined[code] = {
                "code": code,
                "name": row["name"] or code,
                "market_value": 0.0,
                "accounts": set(),
                "updated_at": row["updated_at"],
            }
        combined[code]["market_value"] += float(row["market_value"] or 0)
        combined[code]["accounts"].add(POOL_SPECS.get(row["pool_key"], {}).get("title", row["pool_key"]))
        combined[code]["updated_at"] = max(combined[code]["updated_at"] or "", row["updated_at"] or "")

    result = []
    for item in combined.values():
        result.append(
            {
                "code": item["code"],
                "name": item["name"],
                "market_value": item["market_value"],
                "accounts": " / ".join(sorted(item["accounts"])),
                "updated_at": item["updated_at"],
            }
        )
    return sorted(result, key=lambda item: item["market_value"], reverse=True)


def analyze_portfolio_rows(rows: list[dict[str, Any]], pool_key: str = "all") -> dict[str, Any]:
    ind_map = industry_mapping()
    sw_map = shenwan_mapping()
    total_value = sum(float(row.get("market_value") or 0) for row in rows)
    if total_value <= 0:
        return {
            "pool_key": pool_key,
            "title": POOL_SPECS.get(pool_key, {}).get("title", "全部账户") if pool_key != "all" else "全部账户",
            "generated_at": now_iso(),
            "source_file": PORTFOLIO_INDUSTRY_FILE.name,
            "total_value": 0,
            "holdings_count": 0,
            "mapped_count": 0,
            "unmapped_count": 0,
            "top1_weight": 0,
            "top3_weight": 0,
            "top5_weight": 0,
            "primary": [],
            "details": [],
            "unmapped": [],
        }

    details: list[dict[str, Any]] = []
    unmapped_codes: set[str] = set()
    mapped_codes: set[str] = set()

    for row in rows:
        code = str(row.get("code") or "").zfill(6)
        value = float(row.get("market_value") or 0)
        allocation = ind_map.get(code)
        if allocation:
            mapped_codes.add(code)
        else:
            allocation = {"未分类": 1.0}
            unmapped_codes.add(code)

        for secondary, exposure_weight in allocation.items():
            primary = sw_map.get(secondary, "其他")
            exposure_value = value * float(exposure_weight)
            details.append(
                {
                    "申万一级行业": primary,
                    "申万二级细分": secondary,
                    "代码": code,
                    "名称": row.get("name") or code,
                    "账户": row.get("accounts") or "",
                    "持仓市值": value,
                    "穿透金额": exposure_value,
                    "组合占比": exposure_value / total_value,
                    "基金内权重": float(exposure_weight),
                }
            )

    primary_map: dict[str, dict[str, Any]] = {}
    for item in details:
        industry = item["申万一级行业"]
        bucket = primary_map.setdefault(industry, {"行业": industry, "穿透金额": 0.0, "组合占比": 0.0, "明细数": 0})
        bucket["穿透金额"] += float(item["穿透金额"])
        bucket["明细数"] += 1

    primary_rows = []
    for bucket in primary_map.values():
        bucket["组合占比"] = bucket["穿透金额"] / total_value
        primary_rows.append(bucket)
    primary_rows.sort(key=lambda item: item["穿透金额"], reverse=True)
    details.sort(key=lambda item: (item["申万一级行业"], -float(item["穿透金额"])))

    holding_weights = sorted((float(row.get("market_value") or 0) / total_value for row in rows), reverse=True)

    return {
        "pool_key": pool_key,
        "title": POOL_SPECS.get(pool_key, {}).get("title", "全部账户") if pool_key != "all" else "全部账户",
        "generated_at": now_iso(),
        "source_file": PORTFOLIO_INDUSTRY_FILE.name,
        "total_value": normalize_value(total_value),
        "holdings_count": len(rows),
        "mapped_count": len(mapped_codes),
        "unmapped_count": len(unmapped_codes),
        "top1_weight": normalize_value(sum(holding_weights[:1])),
        "top3_weight": normalize_value(sum(holding_weights[:3])),
        "top5_weight": normalize_value(sum(holding_weights[:5])),
        "primary": [{key: normalize_value(value) for key, value in row.items()} for row in primary_rows],
        "details": [{key: normalize_value(value) for key, value in row.items()} for row in details],
        "unmapped": sorted(unmapped_codes),
    }


def analyze_portfolio(pool_key: str = "all") -> dict[str, Any]:
    return analyze_portfolio_rows(load_portfolio_rows(pool_key), pool_key=pool_key)
