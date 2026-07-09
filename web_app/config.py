from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENV_FILE = ROOT / ".env"
CACHE_DIR = ROOT / "etf_cache"
DATA_DIR = ROOT / "web_app" / "data"
CACHE_DB = DATA_DIR / "etf_cache.sqlite"
NEW_TECH_POOL_FILE = DATA_DIR / "new_tech_pool.json"
POOLS_CONFIG_FILE = DATA_DIR / "pools.json"
STATIC_DIR = Path(__file__).resolve().parent / "static"

from .env_loader import load_project_env

load_project_env(ENV_FILE)

POOL_SPECS = {
    "a_share": {"title": "A 股板块轮动", "var": "A_SHARE_ETF_POOL", "sheet": "A股板块轮动"},
    "global": {"title": "全球与大宗配置", "var": "GLOBAL_ETF_POOL", "sheet": "全球与大宗配置"},
    "new_tech": {"title": "活跃科技标的", "var": "NEW_TECH_POOL", "sheet": "活跃科技标的"},
}

DATA_SOURCES = ["tencent", "sina", "em", "yfinance"]
DEFAULT_SOURCE = "tencent"
DEFAULT_REFRESH_SECONDS = 180
GLOBAL_HOLD_POOL = ["161226", "513100", "513880", "518880"]
ACCOUNT_POOL_KEYS = {"a_share", "global"}

AKSHARE_PROXY_HOST = "101.201.173.125"
AKSHARE_PROXY_TOKEN = os.getenv("AKSHARE_PROXY_TOKEN", "")
AKSHARE_PROXY_RETRY = 30
AKSHARE_PROXY_HOOK_DOMAINS = ["push2his.eastmoney.com"]
