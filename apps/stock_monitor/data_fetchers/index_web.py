# -*- coding: utf-8 -*-
"""指数数据统计页 REST API（Flask Blueprint）。

路由（前缀 /api/index）：
  GET  /dynamic_list      主要指数列表（大盘指数·真实估值恒置顶，组内排序）
  GET  /ranking           指数涨跌幅排名
  GET  /enhanced_ranking  指数排名 + 估值（大盘指数真实 PE/PB 恒置顶，不受 top_n 截断）
  POST /chart_data        多指数走势对比图数据

公共助手（参数校验/统一响应/异常包装）见 `core/utils.py`。
"""
from __future__ import annotations

from flask import Blueprint, request

from config import setup_logger
from ..core.utils import api_guard, err, int_arg, json_body, ok
from .index_data_fetcher import (
    get_detailed_index_ranking,
    get_index_chart_data,
    get_index_dynamic_list,
    get_index_ranking,
)
from .index_data_fetcher import _REAL_SYMBOLS as _REAL_SYMBOL_SET

logger = setup_logger(__name__)

bp = Blueprint("index_api", __name__, url_prefix="/api/index")


@bp.get("/dynamic_list")
@api_guard("获取主要指数列表")
def dynamic_list():
    """主要指数列表（用于走势对比图选择）。

    sort=change_desc/change_asc 时**组内排序**，保证大盘指数(真实估值)组恒在最前。
    """
    sort_by_change = request.args.get("sort", "none")
    logger.info(f"请求主要指数列表，排序方式: {sort_by_change}")
    index_list = get_index_dynamic_list(top_n=28)

    if index_list and sort_by_change in ("change_desc", "change_asc"):
        real = [x for x in index_list if x["symbol"] in _REAL_SYMBOL_SET]
        rest = [x for x in index_list if x["symbol"] not in _REAL_SYMBOL_SET]
        rev = sort_by_change == "change_desc"
        real.sort(key=lambda x: x["change_percent"], reverse=rev)
        rest.sort(key=lambda x: x["change_percent"], reverse=rev)
        index_list = real + rest

    if not index_list:
        return err("暂无指数数据", 404)
    return ok(index_list, message=f"成功获取 {len(index_list)} 个主要指数数据")


@bp.get("/ranking")
@api_guard("获取指数排名数据")
def ranking():
    """指数涨跌幅排名（不含估值；估值见 enhanced_ranking）。"""
    top_n = int_arg("top_n", 28, min_v=1, max_v=9999)
    period = int_arg("period", 30, min_v=1, max_v=3650)
    logger.info(f"请求指数涨跌幅排名，前N个: {top_n}, 周期: {period}天")

    ranking_data = get_index_ranking(period_days=period)
    if not ranking_data:
        return ok({"top_gainers": [], "total_count": 0, "top_n": top_n, "period": period},
                  message="暂无指数排名数据")
    return ok({"top_gainers": ranking_data[:top_n], "total_count": len(ranking_data),
               "top_n": top_n, "period": period},
              message=f"获取指数涨跌幅排行成功，共 {len(ranking_data)} 个指数数据")


@bp.get("/enhanced_ranking")
@api_guard("获取增强指数排名数据")
def enhanced_ranking():
    """指数排名 + 估值：大盘指数(真实 PE/PB) 恒置顶，其余按涨幅补足到 top_n。"""
    top_n = int_arg("top_n", 28, min_v=1, max_v=9999)
    period = int_arg("period", 30, min_v=1, max_v=3650)
    logger.info(f"请求增强指数排名，前N个: {top_n}, 周期: {period}天")

    ranking_data = get_detailed_index_ranking(period_days=period, include_valuation=True)
    if not ranking_data:
        return ok({"top_gainers": [], "total_count": 0, "top_n": top_n, "period": period},
                  message="暂无增强指数排名数据")

    real = [x for x in ranking_data if x.get("is_real_valuation")]
    rest = [x for x in ranking_data if not x.get("is_real_valuation")]
    top_gainers = real + rest[:max(0, top_n - len(real))]
    logger.info(f"选取 {len(top_gainers)} 名指数（大盘指数真实估值 {len(real)} 个恒置顶）")
    return ok({"top_gainers": top_gainers, "real_valuation_count": len(real),
               "total_count": len(ranking_data), "top_n": top_n, "period": period},
              message=f"获取增强指数涨跌幅排行成功，共 {len(ranking_data)} 个指数数据")


@bp.post("/chart_data")
@api_guard("获取指数图表数据")
def chart_data():
    """多指数走势对比（最多 10 个；可切换增长率口径）。"""
    data = json_body()
    symbols = data.get("symbols", [])
    period = data.get("period", "12M")
    use_growth_rate = data.get("use_growth_rate", True)

    if not symbols:
        return err("请至少选择一个指数", 400)
    if len(symbols) > 10:
        return err("最多只能选择10个指数进行对比", 400)

    logger.info(f"请求指数图表数据，指数: {symbols}, 周期: {period}, 使用增长率: {use_growth_rate}")
    chart_data = get_index_chart_data(symbols, period, use_growth_rate)
    if chart_data and chart_data.get("series"):
        return ok(chart_data, message=f"成功获取 {len(chart_data['series'])} 个指数的图表数据")
    return err("构建指数图表数据失败", 500)
