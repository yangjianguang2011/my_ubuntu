# -*- coding: utf-8 -*-
"""基金数据统计页 REST API（Flask Blueprint）。

路由（前缀 /api/fund）：
  GET  /list          精选基金列表（含最新收盘价/涨跌幅）
  GET  /dynamic_list  动态基金列表（按区间收益排名，供走势对比图选择）
  GET  /ranking       基金涨跌幅排名
  POST /chart_data    多基金走势对比图数据

公共助手（参数校验/统一响应/异常包装）见 `core/utils.py`。
"""
from __future__ import annotations

from flask import Blueprint, request

from config import setup_logger
from ..core.utils import api_guard, err, int_arg, json_body, ok
from .fund_data_fetcher import (
    get_fund_chart_data,
    get_fund_dynamic_list,
    get_fund_ranking,
    get_selected_fund_list,
)
from .stockdb_data_fetcher import last_error as stockdb_last_error

logger = setup_logger(__name__)

bp = Blueprint("fund_api", __name__, url_prefix="/api/fund")


def _stockdb_note():
    """stockdb 不可用时的提示文案（正常时为空串）。

    返回 (stockdb_error, message_suffix)：前者供前端展示警示条，
    后者拼到 message 里，便于只看日志/接口时也能发现降级。
    """
    err_msg = stockdb_last_error()
    if not err_msg:
        return None, ""
    return err_msg, f"；⚠ stockdb 不可用，已降级 akshare：{err_msg}"


@bp.get("/list")
@api_guard("获取基金列表")
def fund_list():
    """精选基金列表（页面主用，含真实收盘价/涨跌幅快照）。"""
    logger.info("请求基金列表")
    funds = get_selected_fund_list()
    db_err, suffix = _stockdb_note()
    if not funds:
        return err("暂无基金数据", 404)
    return ok(funds, message=f"成功获取 {len(funds)} 个基金数据{suffix}", stockdb_error=db_err)


@bp.get("/dynamic_list")
@api_guard("获取动态基金列表")
def dynamic_list():
    """动态基金列表（按区间收益），sort 仅影响展示顺序（返回副本，不改缓存）。"""
    top_n = int_arg("top_n", 28, min_v=1, max_v=9999)
    period = request.args.get("period", "30D")
    sort_by_change = request.args.get("sort", "none")
    logger.info(f"请求动态基金列表，前N个: {top_n}, 周期: {period}, 排序方式: {sort_by_change}")

    funds = list(get_fund_dynamic_list(top_n=top_n, period=period) or [])
    db_err, suffix = _stockdb_note()
    if not funds:
        return err("暂无基金数据", 404)
    if sort_by_change == "change_desc":
        funds.sort(key=lambda x: x["change_percent"], reverse=True)
    elif sort_by_change == "change_asc":
        funds.sort(key=lambda x: x["change_percent"])
    return ok(funds, message=f"成功获取 {len(funds)} 个动态基金数据{suffix}", stockdb_error=db_err)


@bp.get("/ranking")
@api_guard("获取基金排名数据")
def ranking():
    """基金涨跌幅排名。"""
    top_n = int_arg("top_n", 28, min_v=1, max_v=9999)
    period = int_arg("period", 30, min_v=1, max_v=3650)
    logger.info(f"请求基金涨跌幅排名，前N个: {top_n}, 周期: {period}天")

    ranking_data = get_fund_ranking(period=f"{period}D")
    db_err, suffix = _stockdb_note()
    if not ranking_data:
        return ok({"top_gainers": [], "total_count": 0, "top_n": top_n, "period": period},
                  message=f"暂无基金排名数据{suffix}", stockdb_error=db_err)
    return ok({"top_gainers": ranking_data[:top_n], "total_count": len(ranking_data),
               "top_n": top_n, "period": period},
              message=f"获取基金涨跌幅排行成功，共 {len(ranking_data)} 个基金数据{suffix}",
              stockdb_error=db_err)


@bp.post("/chart_data")
@api_guard("获取基金图表数据")
def chart_data():
    """多基金走势对比（最多 10 个；可切换增长率口径）。"""
    data = json_body()
    symbols = data.get("symbols", [])
    period = data.get("period", "12M")
    use_growth_rate = data.get("use_growth_rate", True)

    if not symbols:
        return err("请至少选择一个基金", 400)
    if len(symbols) > 10:
        return err("最多只能选择10个基金进行对比", 400)

    logger.info(f"请求基金图表数据，基金: {symbols}, 周期: {period}, 使用增长率: {use_growth_rate}")
    chart_data = get_fund_chart_data(symbols, period, use_growth_rate)
    db_err, suffix = _stockdb_note()
    if chart_data and chart_data.get("series"):
        return ok(chart_data,
                  message=f"成功获取 {len(chart_data['series'])} 个基金的图表数据{suffix}",
                  stockdb_error=db_err)
    return err("构建基金图表数据失败", 500)
