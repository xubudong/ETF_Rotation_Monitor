from __future__ import annotations

import json
from typing import Any

import numpy as np
import pandas as pd

from .config import DATA_DIR

SCORING_STRATEGIES_FILE = DATA_DIR / "scoring_strategies.json"

CATEGORY_MAP = {
    "防御": ["红利", "现金", "低波", "价值", "高股息", "稳健"],
    "科技": ["芯片", "半导体", "人工智能", "AI", "软件", "计算机", "通信", "互联网", "游戏", "电子", "科技"],
    "周期": ["有色", "煤炭", "化工", "电力", "绿电", "光伏", "新能源", "油气", "豆粕", "白银"],
    "制造": ["机器人", "航天", "军工", "卫星", "汽车", "电池", "储能", "电网"],
    "金融": ["银行", "证券", "券商", "保险", "房地产", "非银"],
    "消费医药": ["酒", "家电", "医疗", "医药", "中药", "创新药"],
    "宽基": ["300", "50", "500", "1000", "2000", "A500", "创业板", "科创50", "标普", "纳指", "恒生"],
}


def get_category(name: str) -> str:
    for category, keywords in CATEGORY_MAP.items():
        if any(keyword in str(name) for keyword in keywords):
            return category
    return "其他"


def calculate_indicators(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["MA20"] = df["close"].rolling(window=20).mean()
    df["MA60"] = df["close"].rolling(window=60).mean()
    df["return_20d"] = df["close"].pct_change(periods=20, fill_method=None)
    df["return_1d"] = df["close"].pct_change(periods=1, fill_method=None)
    df["vol_MA20"] = df["volume"].rolling(window=20).mean()
    df["vol_ratio"] = df["volume"] / df["vol_MA20"]
    df["volatility_20d"] = df["return_1d"].rolling(window=20).std() * np.sqrt(250)
    return df


def load_scoring_config() -> dict[str, Any]:
    if not SCORING_STRATEGIES_FILE.exists():
        raise RuntimeError(f"打分策略配置文件不存在: {SCORING_STRATEGIES_FILE}")
    payload = json.loads(SCORING_STRATEGIES_FILE.read_text(encoding="utf-8"))
    strategies = payload.get("strategies")
    if not isinstance(strategies, list) or not strategies:
        raise RuntimeError("打分策略配置缺少 strategies")
    for item in strategies:
        strategy_id = item.get("id", "<unknown>")
        for key in ("max_holdings", "tolerance_count", "momentum_weight", "vol_price", "trend", "strict_sell"):
            if key not in item:
                raise RuntimeError(f"打分策略 {strategy_id} 缺少 {key}")
    return payload


def list_scoring_strategies() -> dict[str, Any]:
    payload = load_scoring_config()
    default_id = payload.get("default_strategy") or payload["strategies"][0]["id"]
    return {
        "default_strategy": default_id,
        "strategies": [
            {
                "id": item["id"],
                "name": item.get("name", item["id"]),
                "description": item.get("description", ""),
                "max_holdings": int(item["max_holdings"]),
                "tolerance_count": int(item["tolerance_count"]),
            }
            for item in payload["strategies"]
        ],
    }


def get_strategy_config(strategy_id: str | None = None) -> dict[str, Any]:
    payload = load_scoring_config()
    default_id = payload.get("default_strategy") or payload["strategies"][0]["id"]
    wanted = strategy_id or default_id
    for item in payload["strategies"]:
        if item.get("id") == wanted:
            if "max_holdings" not in item or "tolerance_count" not in item:
                raise ValueError(f"策略 {wanted} 缺少 max_holdings 或 tolerance_count")
            if int(item["tolerance_count"]) < int(item["max_holdings"]):
                raise ValueError(f"策略 {wanted} 的 tolerance_count 不能小于 max_holdings")
            return item
    raise ValueError(f"未知打分策略: {wanted}")


def _rule_matches(row: pd.Series, rule: dict[str, Any]) -> bool:
    volume_ratio = row.get("量比", 1.0)
    return_1d = row.get("当日涨跌幅", 0.0)
    if pd.isna(volume_ratio) or pd.isna(return_1d):
        return False
    checks = [
        ("min_vol_ratio", volume_ratio, lambda value, limit: value >= limit),
        ("max_vol_ratio", volume_ratio, lambda value, limit: value <= limit),
        ("min_return_1d", return_1d, lambda value, limit: value >= limit),
        ("max_return_1d", return_1d, lambda value, limit: value <= limit),
    ]
    for key, value, predicate in checks:
        if key in rule and not predicate(float(value), float(rule[key])):
            return False
    return True


def calc_vol_price_score(row: pd.Series, strategy: dict[str, Any]) -> float:
    volume_ratio = row.get("量比", 1.0)
    return_1d = row.get("当日涨跌幅", 0.0)
    if pd.isna(volume_ratio) or pd.isna(return_1d):
        return 0.0
    vol_config = strategy.get("vol_price", {})
    multiplier = float(vol_config.get("default_multiplier", 8))
    cap = vol_config.get("cap")
    for rule in vol_config.get("rules", []):
        if _rule_matches(row, rule):
            multiplier = float(rule.get("multiplier", multiplier))
            cap = rule.get("cap", cap)
            break
    score = float(volume_ratio) * multiplier
    if cap is not None:
        score = min(score, float(cap))
    return round(float(score), 2)


def calc_vol_price_scores(score_df: pd.DataFrame, strategy: dict[str, Any]) -> pd.Series:
    vol_config = strategy["vol_price"]
    method = vol_config.get("method", "rule_multiplier")
    if method == "rank_percentile":
        volume_ratio = pd.to_numeric(score_df["量比"], errors="coerce")
        base_score = volume_ratio.rank(pct=True) * float(vol_config["weight"])
        low_threshold = vol_config.get("low_vol_ratio_threshold")
        low_multiplier = float(vol_config.get("low_vol_multiplier", 1.0))
        if low_threshold is not None:
            base_score = np.where(volume_ratio >= float(low_threshold), base_score, base_score * low_multiplier)
        return pd.Series(base_score, index=score_df.index).fillna(0.0).round(2)
    if method == "rule_multiplier":
        return score_df.apply(lambda row: calc_vol_price_score(row, strategy), axis=1)
    raise ValueError(f"未知量价策略 method: {method}")


def calculate_trend_score(row: pd.Series, strategy: dict[str, Any]) -> float:
    price = row["最新收盘价"]
    ma20 = row["MA20"]
    ma60 = row["MA60"]
    if pd.isna(ma20) or pd.isna(ma60) or ma20 <= ma60:
        return 0.0
    trend = strategy.get("trend", {})
    base_score = float(trend.get("base_score", 5))
    bias_unit = float(trend.get("bias_unit", 0.015))
    bias_weight = float(trend.get("bias_weight", 10))
    max_score = float(trend.get("max_score", 20))
    below_ma20_penalty = float(trend.get("below_ma20_penalty", 0.5))
    bias = (ma20 - ma60) / ma60
    score = base_score + (bias / bias_unit) * bias_weight if bias < bias_unit else max_score
    if price < ma20:
        score *= below_ma20_penalty
    return round(float(min(score, max_score)), 1)


def _strategy_with_runtime_overrides(strategy: dict[str, Any], runtime_overrides: dict[str, Any] | None = None) -> dict[str, Any]:
    if not runtime_overrides:
        return strategy
    effective = dict(strategy)
    for key in ("max_holdings", "tolerance_count"):
        if key in runtime_overrides:
            effective[key] = int(runtime_overrides[key])
    if int(effective["tolerance_count"]) < int(effective["max_holdings"]):
        effective["tolerance_count"] = effective["max_holdings"]
    return effective


def apply_trade_decisions(score_df: pd.DataFrame, strategy: dict[str, Any]) -> pd.DataFrame:
    score_df = score_df.copy()
    max_holdings = int(strategy["max_holdings"])
    tolerance_count = int(strategy["tolerance_count"])
    strict_sell = strategy["strict_sell"]

    ratings = []
    for index, row in score_df.iterrows():
        rank = index + 1
        price = row["最新收盘价"]
        ma20 = row["MA20"]
        trend_score = row["趋势得分"]
        if strict_sell.get("below_ma20", True) and pd.notna(ma20) and price < ma20:
            ratings.append("空仓回避")
        elif strict_sell.get("rank_gt_tolerance", True) and rank > tolerance_count:
            ratings.append("空仓回避")
        elif trend_score >= 0:
            if rank <= max_holdings:
                ratings.append("买入配仓")
            elif rank <= tolerance_count:
                ratings.append("持有观察")
            else:
                ratings.append("空仓回避")
        else:
            ratings.append("空仓回避")

    score_df["评级"] = ratings
    fatal_dump = strict_sell.get("fatal_dump")
    if fatal_dump:
        fatal_vol_ratio = float(fatal_dump["min_vol_ratio"])
        fatal_return_1d = float(fatal_dump["max_return_1d"])
        fatal_dump_mask = (score_df["量比"] > fatal_vol_ratio) & (score_df["当日涨跌幅"] < fatal_return_1d)
        score_df.loc[fatal_dump_mask, "评级"] = "空仓回避"
    score_df["策略动作"] = np.where(score_df["评级"] == "买入配仓", "target", np.where(score_df["评级"] == "空仓回避", "force_sell", "hold"))
    return score_df


def target_codes_from_scores(score_df: pd.DataFrame, strategy_id: str | None = None) -> list[str]:
    if score_df.empty or "策略动作" not in score_df.columns:
        return []
    strategy = get_strategy_config(strategy_id)
    max_holdings = int(strategy["max_holdings"])
    targets = score_df[score_df["策略动作"] == "target"].sort_values("综合总分", ascending=False)
    return [str(code).zfill(6) for code in targets["代码"].head(max_holdings)]


def force_sell_codes_from_scores(score_df: pd.DataFrame) -> set[str]:
    if score_df.empty or "策略动作" not in score_df.columns:
        return set()
    return set(str(code).zfill(6) for code in score_df.loc[score_df["策略动作"] == "force_sell", "代码"])


def cross_sectional_score_and_rate(
    cross_df: pd.DataFrame,
    strategy_id: str | None = None,
    runtime_overrides: dict[str, Any] | None = None,
) -> pd.DataFrame:
    if cross_df.empty:
        return pd.DataFrame()

    strategy = _strategy_with_runtime_overrides(get_strategy_config(strategy_id), runtime_overrides)
    score_df = cross_df.copy()
    momentum_weight = float(strategy.get("momentum_weight", 50))

    score_df["量能得分"] = calc_vol_price_scores(score_df, strategy)
    score_df["动量得分"] = score_df["20日涨幅"].rank(pct=True) * momentum_weight
    score_df["趋势得分"] = score_df.apply(lambda row: calculate_trend_score(row, strategy), axis=1)
    score_df["综合总分"] = score_df["动量得分"] + score_df["量能得分"] + score_df["趋势得分"]
    score_df = score_df.sort_values(by="综合总分", ascending=False).reset_index(drop=True)
    score_df = apply_trade_decisions(score_df, strategy)
    score_df["价格>MA20"] = np.where(score_df["最新收盘价"] > score_df["MA20"], "是", "否")
    score_df["策略"] = strategy.get("name", strategy.get("id", ""))
    if runtime_overrides:
        score_df["运行约束"] = f"目标{strategy['max_holdings']} / 观察{strategy['tolerance_count']}"
    return score_df
