from __future__ import annotations

from datetime import date, datetime
from io import BytesIO

from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.responses import FileResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .account_change import account_today_change
from .app_state import STATE, STATE_LOCK, clear_payload, current_state, set_state
from .backtest import benchmark_options, run_backtest
from .backtest_export import build_backtest_workbook
from .cache_update import update_cache_state
from .config import (
    ACCOUNT_POOL_KEYS,
    AKSHARE_PROXY_HOOK_DOMAINS,
    AKSHARE_PROXY_HOST,
    AKSHARE_PROXY_RETRY,
    CACHE_DB,
    DATA_SOURCES,
    DEFAULT_REFRESH_SECONDS,
    DEFAULT_SOURCE,
    POOL_SPECS,
    ROOT,
    STATIC_DIR,
)
from .ranking import build_rankings
from .scoring import list_scoring_strategies
from .storage import GLOBAL_NOTE_KEY, cache_stats, holdings_status, list_market_notes, load_market_note, save_manual_holding, save_market_note
from .tech_discovery import tech_pool_status, update_tech_pool_state
from .utils import module_available, now_iso

app = FastAPI(title="ETF Market Rotation Monitor", version="1.0.0")
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


class BacktestRequest(BaseModel):
    pool_key: str = "a_share"
    strategy_id: str | None = None
    months: int | None = Field(default=12, ge=1, le=60)
    start_date: date | None = None
    end_date: date | None = None
    initial_capital: float = Field(default=200000.0, gt=0)
    benchmark_code: str = "510300"
    execution_mode: str = "next_open"


class ManualHoldingRequest(BaseModel):
    code: str
    name: str | None = None
    held: bool = True
    market_value_wan: float | None = Field(default=None, ge=0)


class NoteRequest(BaseModel):
    content: str = Field(default="", max_length=2000)


def _state_error(payload: dict) -> str | None:
    return "; ".join(payload.get("errors") or []) or None


def refresh_state(source: str = DEFAULT_SOURCE, refresh: bool = True, strategy_id: str | None = None) -> None:
    set_state(refreshing=True, last_error=None)
    try:
        payload = build_rankings(source=source, refresh=refresh, strategy_id=strategy_id)
        set_state(payload=payload, source=source, last_refresh=now_iso(), last_error=_state_error(payload))
    except Exception as exc:
        set_state(last_error=str(exc))
    finally:
        set_state(refreshing=False)


@app.get("/")
def index():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    return Response(status_code=204)


@app.get("/api/health")
def health():
    state = current_state()
    deps = {
        name: module_available(name)
        for name in [
            "fastapi",
            "uvicorn",
            "pandas",
            "numpy",
            "akshare",
            "akshare_proxy_patch",
            "yfinance",
            "baostock",
            "openpyxl",
        ]
    }
    return {
        "ok": True,
        "time": now_iso(),
        "root": str(ROOT),
        "cache_store": str(CACHE_DB),
        "dependencies": deps,
        "refreshing": state["refreshing"],
        "last_refresh": state["last_refresh"],
        "last_error": state["last_error"],
        "cache_updating": state["cache_updating"],
        "cache_update_started": state["cache_update_started"],
        "cache_update_finished": state["cache_update_finished"],
        "cache_update_last_error": state["cache_update_last_error"],
        "cache_update_result": state["cache_update_result"],
        "cache_update_progress": state["cache_update_progress"],
        "cache_stats": cache_stats(),
        "holdings": holdings_status(),
        "tech_pool": tech_pool_status(),
    }


@app.get("/api/config")
def config():
    return {
        "sources": DATA_SOURCES,
        "default_source": DEFAULT_SOURCE,
        "default_refresh_seconds": DEFAULT_REFRESH_SECONDS,
        "cache_update_source": "akshare_em_sqlite",
        "akshare_proxy": {
            "enabled_for_cache_update": True,
            "host": AKSHARE_PROXY_HOST,
            "retry": AKSHARE_PROXY_RETRY,
            "hook_domains": AKSHARE_PROXY_HOOK_DOMAINS,
            "module_available": module_available("akshare_proxy_patch"),
        },
        "cache_store": str(CACHE_DB),
        "cache_stats": cache_stats(),
        "holdings": holdings_status(),
        "tech_pool": tech_pool_status(),
        "pools": {key: spec["title"] for key, spec in POOL_SPECS.items()},
        "account_pools": {key: POOL_SPECS[key]["title"] for key in ACCOUNT_POOL_KEYS},
        "scoring": list_scoring_strategies(),
        "benchmarks": benchmark_options(),
    }


@app.get("/api/rankings")
def rankings(source: str = DEFAULT_SOURCE, refresh: bool = False, strategy_id: str | None = None, as_of: date | None = None):
    if source not in DATA_SOURCES:
        raise HTTPException(status_code=400, detail=f"未知数据源: {source}")
    if as_of is not None:
        try:
            return build_rankings(source=source, refresh=False, strategy_id=strategy_id, as_of_date=as_of.isoformat())
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
    state = current_state()
    if not refresh and state["payload"] and state["source"] == source and state["payload"].get("strategy_id") == strategy_id:
        return state["payload"]
    try:
        payload = build_rankings(source=source, refresh=refresh, strategy_id=strategy_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    set_state(payload=payload, source=source, last_refresh=now_iso(), last_error=_state_error(payload))
    return payload


@app.post("/api/refresh")
def refresh(background_tasks: BackgroundTasks, source: str = DEFAULT_SOURCE, strategy_id: str | None = None):
    if source not in DATA_SOURCES:
        raise HTTPException(status_code=400, detail=f"未知数据源: {source}")
    state = current_state()
    if state["refreshing"]:
        return {"accepted": False, "refreshing": True, "last_error": state["last_error"]}
    background_tasks.add_task(refresh_state, source, True, strategy_id)
    return {"accepted": True, "refreshing": True, "source": source, "last_error": state["last_error"]}


@app.get("/api/scoring/strategies")
def scoring_strategies():
    return list_scoring_strategies()


def _run_backtest_request(payload: BacktestRequest):
    try:
        return run_backtest(
            pool_key=payload.pool_key,
            strategy_id=payload.strategy_id,
            months=payload.months,
            initial_capital=payload.initial_capital,
            benchmark_code=payload.benchmark_code,
            start_date=payload.start_date.isoformat() if payload.start_date else None,
            end_date=payload.end_date.isoformat() if payload.end_date else None,
            execution_mode=payload.execution_mode,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/backtest")
def backtest_api(payload: BacktestRequest):
    return _run_backtest_request(payload)


@app.post("/api/backtest/export")
def backtest_export_api(payload: BacktestRequest):
    result = _run_backtest_request(payload)
    content = build_backtest_workbook(result)
    filename = f"backtest_details_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    return StreamingResponse(
        BytesIO(content),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.get("/api/cache/status")
def cache_status():
    state = current_state()
    return {
        "updating": state["cache_updating"],
        "started": state["cache_update_started"],
        "finished": state["cache_update_finished"],
        "last_error": state["cache_update_last_error"],
        "result": state["cache_update_result"],
        "progress": state["cache_update_progress"],
        "stats": cache_stats(),
    }


@app.post("/api/cache/update")
def cache_update(background_tasks: BackgroundTasks, days: int = 800):
    if days < 120 or days > 3000:
        raise HTTPException(status_code=400, detail="days 必须在 120 到 3000 之间")
    state = current_state()
    if state["cache_updating"]:
        return {
            "accepted": False,
            "updating": True,
            "started": state["cache_update_started"],
            "last_error": state["cache_update_last_error"],
        }
    background_tasks.add_task(update_cache_state, days)
    return {"accepted": True, "updating": True, "source": "akshare_em_sqlite", "store": str(CACHE_DB), "days": days}


@app.get("/api/holdings/status")
def holdings_status_api():
    return holdings_status()


@app.get("/api/accounts/today-change")
def accounts_today_change(source: str = DEFAULT_SOURCE):
    if source not in DATA_SOURCES:
        raise HTTPException(status_code=400, detail=f"未知数据源: {source}")
    try:
        return account_today_change(source=source)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/holdings/{pool_key}/manual")
def manual_holding_api(pool_key: str, payload: ManualHoldingRequest):
    try:
        result = save_manual_holding(
            pool_key=pool_key,
            code=payload.code,
            name=payload.name,
            market_value_wan=payload.market_value_wan,
            held=payload.held,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    clear_payload()
    return {**result, "status": holdings_status()}


@app.get("/api/notes/recent")
def recent_global_notes_api(limit: int = 20):
    try:
        return {"pool_key": GLOBAL_NOTE_KEY, "notes": list_market_notes(GLOBAL_NOTE_KEY, limit=limit)}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/notes")
def global_note_api(note_date: date | None = None):
    target_date = (note_date or date.today()).isoformat()
    try:
        return load_market_note(target_date, GLOBAL_NOTE_KEY)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/notes")
def save_global_note_api(payload: NoteRequest, note_date: date | None = None):
    target_date = (note_date or date.today()).isoformat()
    try:
        return save_market_note(target_date, GLOBAL_NOTE_KEY, payload.content)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/notes/{pool_key}/recent")
def recent_notes_api(pool_key: str, limit: int = 20):
    try:
        return {"pool_key": pool_key, "notes": list_market_notes(pool_key, limit=limit)}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/notes/{pool_key}")
def note_api(pool_key: str, note_date: date | None = None):
    target_date = (note_date or date.today()).isoformat()
    try:
        return load_market_note(target_date, pool_key)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/notes/{pool_key}")
def save_note_api(pool_key: str, payload: NoteRequest, note_date: date | None = None):
    target_date = (note_date or date.today()).isoformat()
    try:
        return save_market_note(target_date, pool_key, payload.content)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/tech-pool/status")
def tech_pool_status_api():
    return tech_pool_status()


@app.post("/api/tech-pool/update")
def tech_pool_update(background_tasks: BackgroundTasks, top_n: int = 100):
    if top_n < 20 or top_n > 300:
        raise HTTPException(status_code=400, detail="top_n 必须在 20 到 300 之间")
    state = current_state()
    if state["tech_pool_updating"]:
        return {
            "accepted": False,
            "updating": True,
            "started": state["tech_pool_update_started"],
            "last_error": state["tech_pool_update_last_error"],
        }
    background_tasks.add_task(update_tech_pool_state, top_n)
    return {"accepted": True, "updating": True, "source": "akshare.fund_etf_category_sina", "top_n": top_n}
