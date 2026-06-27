from __future__ import annotations

import importlib
import sqlite3
from typing import Any

import pandas as pd

from .app_state import STATE, STATE_LOCK
from .config import (
    AKSHARE_PROXY_HOOK_DOMAINS,
    AKSHARE_PROXY_HOST,
    AKSHARE_PROXY_RETRY,
    AKSHARE_PROXY_TOKEN,
    CACHE_DB,
)
from .pools import all_unique_etfs
from .storage import cache_stats, init_cache_db, normalize_em_history, previous_trading_target_date, write_history_to_sqlite
from .utils import now_iso


def install_akshare_proxy_patch() -> bool:
    if not AKSHARE_PROXY_TOKEN:
        raise RuntimeError("请先设置 AKSHARE_PROXY_TOKEN 环境变量，再更新本地库。")
    patch = importlib.import_module("akshare_proxy_patch")
    patch.install_patch(
        AKSHARE_PROXY_HOST,
        auth_token=AKSHARE_PROXY_TOKEN,
        retry=AKSHARE_PROXY_RETRY,
        hook_domains=AKSHARE_PROXY_HOOK_DOMAINS,
    )
    return True


def load_latest_history_dates(codes: list[str]) -> dict[str, pd.Timestamp]:
    if not codes:
        return {}
    init_cache_db()
    placeholders = ",".join("?" for _ in codes)
    with sqlite3.connect(CACHE_DB) as conn:
        rows = conn.execute(
            f"""
            SELECT code, MAX(date) AS max_date
            FROM etf_history
            WHERE code IN ({placeholders})
            GROUP BY code
            """,
            codes,
        ).fetchall()
    return {
        str(code): pd.to_datetime(max_date).normalize()
        for code, max_date in rows
        if max_date
    }


def update_cache_progress(**updates: Any) -> None:
    with STATE_LOCK:
        progress = dict(STATE.get("cache_update_progress") or {})
        logs = list(progress.get("logs") or [])
        new_log = updates.pop("log", None)
        if new_log:
            logs.append(f"{now_iso()} {new_log}")
            logs = logs[-30:]
        progress.update(updates)
        progress["logs"] = logs
        STATE["cache_update_progress"] = progress


def update_local_cache_em(days: int = 800) -> dict[str, Any]:
    install_akshare_proxy_patch()
    ak = importlib.import_module("akshare")
    etfs = all_unique_etfs()
    codes = list(etfs.keys())
    init_cache_db()
    end_date = pd.to_datetime(previous_trading_target_date()).normalize()
    full_start_date = end_date - pd.Timedelta(days=days * 2)
    full_start_str = full_start_date.strftime("%Y%m%d")
    end_str = end_date.strftime("%Y%m%d")
    latest_dates = load_latest_history_dates(codes)

    updated = 0
    skipped = 0
    failed: list[dict[str, str]] = []
    total = len(etfs)
    update_cache_progress(
        total=total,
        current=0,
        success=0,
        skipped=0,
        failed=0,
        percent=0,
        current_code=None,
        current_name=None,
        target_end_date=end_date.strftime("%Y-%m-%d"),
        log=f"开始 EM 本地库增量更新，共 {total} 个标的，目标日期 {end_date.strftime('%Y-%m-%d')}",
    )

    for index, (code, name) in enumerate(etfs.items(), start=1):
        latest_date = latest_dates.get(code)
        if latest_date is not None and latest_date >= end_date:
            skipped += 1
            update_cache_progress(
                current=index,
                total=total,
                success=updated,
                skipped=skipped,
                failed=len(failed),
                percent=round(index / total * 100, 1) if total else 100,
                current_code=code,
                current_name=name,
                log=f"[{index}/{total}] 跳过 {code} {name}，已更新至 {latest_date.strftime('%Y-%m-%d')}",
            )
            print(f"[cache-update] [{index}/{total}] skip {code} latest={latest_date.strftime('%Y-%m-%d')}", flush=True)
            continue

        update_cache_progress(
            current=index,
            total=total,
            current_code=code,
            current_name=name,
            success=updated,
            skipped=skipped,
            failed=len(failed),
            percent=round((index - 1) / total * 100, 1) if total else 0,
            log=f"[{index}/{total}] 更新 {code} {name}：本地最新 {latest_date.strftime('%Y-%m-%d') if latest_date is not None else '无'}，重刷 {full_start_date.strftime('%Y-%m-%d')} 至 {end_date.strftime('%Y-%m-%d')}",
        )
        print(f"[cache-update] [{index}/{total}] updating {code} {name} {full_start_str}-{end_str}", flush=True)
        try:
            raw = ak.fund_etf_hist_em(
                symbol=code,
                period="daily",
                start_date=full_start_str,
                end_date=end_str,
                adjust="qfq",
            )
            if raw is None or raw.empty:
                raise ValueError("EM 返回空数据")
            df = normalize_em_history(raw)
            df = df[(df["date"] >= full_start_date) & (df["date"] <= end_date)]
            if df.empty:
                raise ValueError("清洗后没有可写入的新数据")
            rows_written = write_history_to_sqlite(code, df, source="akshare_em_incremental")
            updated += 1
            latest_dates[code] = pd.to_datetime(df["date"]).max().normalize()
            update_cache_progress(
                current=index,
                total=total,
                success=updated,
                skipped=skipped,
                failed=len(failed),
                percent=round(index / total * 100, 1) if total else 100,
                log=f"[{index}/{total}] 成功 {code} {name}，写入 {rows_written} 行",
            )
            print(f"[cache-update] [{index}/{total}] ok {code} rows={rows_written}", flush=True)
        except Exception as exc:
            failed.append({"code": code, "name": name, "error": str(exc)})
            update_cache_progress(
                current=index,
                total=total,
                success=updated,
                skipped=skipped,
                failed=len(failed),
                percent=round(index / total * 100, 1) if total else 100,
                log=f"[{index}/{total}] 失败 {code} {name}: {exc}",
            )
            print(f"[cache-update] [{index}/{total}] failed {code}: {exc}", flush=True)

    update_cache_progress(
        current=total,
        total=total,
        success=updated,
        skipped=skipped,
        failed=len(failed),
        percent=100,
        current_code=None,
        current_name=None,
        target_end_date=end_date.strftime("%Y-%m-%d"),
        log=f"EM 本地库增量更新完成：更新 {updated}，跳过 {skipped}，失败 {len(failed)}",
    )
    print(f"[cache-update] finished updated={updated} skipped={skipped} total={total} failed={len(failed)}", flush=True)
    return {
        "started_at": None,
        "finished_at": now_iso(),
        "source": "akshare_em_sqlite_incremental",
        "store": str(CACHE_DB),
        "target_end_date": end_date.strftime("%Y-%m-%d"),
        "cache_stats": cache_stats(),
        "total": total,
        "success": updated,
        "skipped": skipped,
        "failed": len(failed),
        "failed_items": failed[:30],
    }


def update_cache_state(days: int = 800) -> None:
    started = now_iso()
    with STATE_LOCK:
        STATE["cache_updating"] = True
        STATE["cache_update_started"] = started
        STATE["cache_update_finished"] = None
        STATE["cache_update_last_error"] = None
        STATE["cache_update_result"] = None
        STATE["cache_update_progress"] = {
            "total": 0,
            "current": 0,
            "success": 0,
            "skipped": 0,
            "failed": 0,
            "percent": 0,
            "current_code": None,
            "current_name": None,
            "logs": [f"{started} 准备启动 EM 本地库增量更新"],
        }
    try:
        result = update_local_cache_em(days=days)
        result["started_at"] = started
        with STATE_LOCK:
            STATE["cache_update_result"] = result
            STATE["cache_update_finished"] = result["finished_at"]
            STATE["cache_update_last_error"] = None if result["failed"] == 0 else f"{result['failed']} 个标的更新失败"
    except Exception as exc:
        with STATE_LOCK:
            STATE["cache_update_finished"] = now_iso()
            STATE["cache_update_last_error"] = str(exc)
            STATE["cache_update_result"] = {
                "started_at": started,
                "finished_at": STATE["cache_update_finished"],
                "source": "akshare_em_sqlite_incremental",
                "store": str(CACHE_DB),
                "total": 0,
                "success": 0,
                "skipped": 0,
                "failed": 0,
                "failed_items": [],
                "cache_stats": cache_stats(),
            }
            STATE["cache_update_progress"] = {
                "total": 0,
                "current": 0,
                "success": 0,
                "skipped": 0,
                "failed": 0,
                "percent": 0,
                "current_code": None,
                "current_name": None,
                "logs": [f"{started} 启动失败: {exc}"],
            }
    finally:
        with STATE_LOCK:
            STATE["cache_updating"] = False
