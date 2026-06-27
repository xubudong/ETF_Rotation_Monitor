from __future__ import annotations

import json
from pathlib import Path

from .config import GLOBAL_HOLD_POOL, POOLS_CONFIG_FILE, ROOT
from .tech_discovery import load_new_tech_pool_override


def _normalize_pool(pool: dict) -> dict[str, str]:
    return {str(code).zfill(6): str(name) for code, name in pool.items() if str(code).strip()}


def load_pools_config() -> dict:
    if not POOLS_CONFIG_FILE.exists():
        raise RuntimeError(f"ETF 池配置文件不存在: {POOLS_CONFIG_FILE}")
    payload = json.loads(POOLS_CONFIG_FILE.read_text(encoding="utf-8"))
    pools = payload.get("pools")
    if not isinstance(pools, dict):
        raise RuntimeError("ETF 池配置缺少 pools 对象")
    return payload


def load_pool_definitions() -> dict[str, dict[str, str]]:
    payload = load_pools_config()
    pools = payload["pools"]
    required = {"a_share", "global"}
    missing = [key for key in required if not isinstance(pools.get(key), dict) or not pools.get(key)]
    if missing:
        raise RuntimeError(f"ETF 池配置缺少: {', '.join(missing)}")

    result = {
        "a_share": _normalize_pool(pools["a_share"]),
        "global": _normalize_pool(pools["global"]),
        "new_tech": _normalize_pool(pools.get("new_tech", {})),
    }
    override = load_new_tech_pool_override()
    if override:
        result["new_tech"] = override["pool"]
    if not result["new_tech"]:
        raise RuntimeError("活跃科技标的池为空，请先点击页面上的“更新科技池”")
    return result


def all_unique_etfs() -> dict[str, str]:
    merged: dict[str, str] = {}
    for pool in load_pool_definitions().values():
        for code, name in pool.items():
            merged.setdefault(code, name)
    try:
        from .scoring import load_scoring_config

        for strategy in load_scoring_config().get("strategies", []):
            market_filter = strategy.get("market_filter") or {}
            symbol = market_filter.get("symbol")
            if symbol:
                merged.setdefault(str(symbol).zfill(6), market_filter.get("name", str(symbol).zfill(6)))
    except Exception:
        pass
    return merged


def load_legacy_hold_pool(file_path: Path | None = None) -> list[str]:
    path = file_path or (ROOT / "table.xls")
    hold_list: list[str] = []
    if not path.exists():
        return GLOBAL_HOLD_POOL.copy()

    lines = None
    for encoding in ("utf-8", "gb18030", "gbk", "gb2312"):
        try:
            lines = path.read_text(encoding=encoding).splitlines()
            break
        except UnicodeDecodeError:
            continue

    if not lines:
        return GLOBAL_HOLD_POOL.copy()

    for line in lines[1:]:
        parts = [part.strip() for part in line.replace("\t", " ").split() if part.strip()]
        for token in parts[:4]:
            if token.isdigit() and len(token) == 6:
                hold_list.append(token)
                break

    return list(dict.fromkeys(hold_list + GLOBAL_HOLD_POOL))
