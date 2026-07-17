from __future__ import annotations

import importlib.util
import math
from datetime import datetime
from typing import Any

import pandas as pd


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def module_available(name: str) -> bool:
    return importlib.util.find_spec(name) is not None


def normalize_value(value: Any) -> Any:
    if isinstance(value, list):
        return [normalize_value(item) for item in value]
    if pd.isna(value):
        return None
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if isinstance(value, float):
        if math.isinf(value) or math.isnan(value):
            return None
        return round(value, 6)
    return value


def normalize_records(df: pd.DataFrame) -> list[dict[str, Any]]:
    if df is None or df.empty:
        return []
    records = []
    for idx, row in df.reset_index(drop=True).iterrows():
        record = {str(col): normalize_value(row[col]) for col in df.columns}
        if "代码" in record and record["代码"] is not None:
            record["代码"] = str(record["代码"]).split(".")[0].zfill(6)
        record["排名"] = idx + 1
        records.append(record)
    return records
