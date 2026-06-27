from __future__ import annotations

from io import BytesIO
from typing import Any

import pandas as pd


def build_backtest_workbook(result: dict[str, Any]) -> bytes:
    benchmark_code = result.get("benchmark", {}).get("code", "")
    symbol_df = pd.DataFrame(result.get("symbol_performance") or []).rename(
        columns={
            "code": "代码",
            "name": "名称",
            "status": "期末状态",
            "buy_count": "买入次数",
            "sell_count": "卖出次数",
            "buy_amount": "累计买入",
            "sell_amount": "累计卖出",
            "ending_shares": "期末份额",
            "market_value": "期末市值",
            "profit": "最终盈亏",
            "profit_pct": "收益率",
        }
    )
    trade_df = pd.DataFrame(result.get("trades") or []).rename(
        columns={
            "date": "日期",
            "action": "动作",
            "code": "代码",
            "name": "名称",
            "price": "价格",
            "shares": "数量",
            "amount": "金额",
            "pnl_pct": "卖出收益率",
        }
    )
    curve_df = pd.DataFrame(result.get("curve") or []).rename(
        columns={
            "date": "日期",
            "equity": "资产",
            "return": "策略收益率",
            "cash": "现金",
            "holdings": "持仓数",
            "drawdown": "回撤",
            f"benchmark_{benchmark_code}": "基准收益率",
        }
    )
    coverage = result.get("data_coverage") or {}
    metrics = result.get("metrics") or {}
    market_state = result.get("market_state") or {}
    signals = market_state.get("signals") or {}
    params_df = pd.DataFrame(
        [
            ("回测池", result.get("pool_key")),
            ("策略", result.get("strategy", {}).get("name")),
            ("成交方式", result.get("execution_mode_name")),
            ("大盘状态", market_state.get("status")),
            ("大盘信号汇总", market_state.get("signal_summary")),
            ("中线趋势", signals.get("medium_trend", {}).get("state")),
            ("中线最近交叉", signals.get("medium_trend", {}).get("last_cross_type")),
            ("中线最近交叉日期", signals.get("medium_trend", {}).get("last_cross_date")),
            ("短线博弈", signals.get("short_trade", {}).get("state")),
            ("短线最近交叉", signals.get("short_trade", {}).get("last_cross_type")),
            ("短线最近交叉日期", signals.get("short_trade", {}).get("last_cross_date")),
            ("MACD", signals.get("macd", {}).get("state")),
            ("MACD最近交叉", signals.get("macd", {}).get("last_cross_type")),
            ("MACD最近交叉日期", signals.get("macd", {}).get("last_cross_date")),
            ("大盘仓位比例", market_state.get("position_ratio")),
            ("大盘代理", market_state.get("name")),
            ("大盘判断日期", market_state.get("date")),
            ("基准", result.get("benchmark", {}).get("name")),
            ("快捷月份", result.get("months")),
            ("指定开始日期", result.get("start_date")),
            ("指定结束日期", result.get("end_date")),
            ("实际开始日期", coverage.get("actual_start_date")),
            ("实际结束日期", coverage.get("actual_end_date")),
            ("首笔交易日期", coverage.get("first_trade_date")),
            ("初始资产", metrics.get("initial_capital")),
            ("最终资产", metrics.get("final_value")),
            ("累计收益率", metrics.get("total_return")),
            ("最大回撤", metrics.get("max_drawdown")),
        ],
        columns=["项目", "值"],
    )

    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        symbol_df.to_excel(writer, sheet_name="标的汇总", index=False)
        trade_df.to_excel(writer, sheet_name="逐笔交易", index=False)
        curve_df.to_excel(writer, sheet_name="净值曲线", index=False)
        params_df.to_excel(writer, sheet_name="回测参数", index=False)
        for worksheet in writer.book.worksheets:
            worksheet.freeze_panes = "A2"
            worksheet.auto_filter.ref = worksheet.dimensions
            for column_cells in worksheet.columns:
                values = [str(cell.value) if cell.value is not None else "" for cell in column_cells]
                width = min(max(max((len(value) for value in values), default=8) + 2, 10), 24)
                worksheet.column_dimensions[column_cells[0].column_letter].width = width

    return output.getvalue()
