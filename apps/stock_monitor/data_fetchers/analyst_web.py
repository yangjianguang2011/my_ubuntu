# -*- coding: utf-8 -*-
"""分析师数据页 REST API（Flask Blueprint）。

数据源为**东方财富（经 akshare）**，口径为**年度排行**（详见 `analyst_data_fetcher` 的
模块 docstring：akshare 只有 year 参数的排行接口，无法复现页面的 3/6/12 个月榜）。

路由（前缀 /api/analyst）：
  GET /focus_stocks      分析师重点关注股票（top_analysts / top_stocks，支持 all）
  GET /updated_stocks    最近 N 天更新的跟踪成份股（days 必填；indicator 可选）
  GET /history_tracking  单只股票的历史关注数（stock_code 必填 / days）
  GET /latest_tracking   最新跟踪成份股明细（top_analysts / top_stocks，支持 all）
"""
from __future__ import annotations

from flask import Blueprint, request

from config import setup_logger
from .analyst_data_fetcher import (
    DEFAULT_INDICATOR,
    get_analyst_focus_stocks,
    get_analyst_history_tracking,
    get_analyst_latest_tracking,
    get_analyst_updated_stocks,
)
from ..core.utils import BadParam, api_guard, err, int_arg, ok, top_arg

logger = setup_logger(__name__)

bp = Blueprint("analyst_api", __name__, url_prefix="/api/analyst")

_ALL = 9999  # 'all' 的统一哨兵值


def _indicator_arg() -> str:
    """读取并校验 indicator（默认「最新跟踪成分股」）。"""
    value = request.args.get("indicator", DEFAULT_INDICATOR)
    if value not in ("最新跟踪成分股", "历史跟踪成分股"):
        raise BadParam(f"indicator 非法: {value!r}（可选：最新跟踪成分股 / 历史跟踪成分股）")
    return value


# ---------------------------------------------------------------- 路由
@bp.get("/focus_stocks")
@api_guard("获取分析师重点关注股票")
def focus_stocks():
    top_analysts = top_arg("top_analysts", 50, _ALL)
    top_stocks = top_arg("top_stocks", 50, _ALL)
    logger.info(f"分析师重点关注股票：前{top_analysts}位分析师 / 前{top_stocks}只股票")

    data = get_analyst_focus_stocks(top_analysts=top_analysts, top_stocks=top_stocks)
    if not data:
        return err("未能获取分析师重点关注股票数据", 404)
    return ok(data)


@bp.get("/updated_stocks")
@api_guard("获取最近更新的股票数据")
def updated_stocks():
    days = int_arg("days", min_v=1, max_v=3650)   # 必填；非法/缺失 → 400
    indicator = _indicator_arg()
    logger.info(f"最近更新的股票数据：{days} 天 / {indicator}")

    data = get_analyst_updated_stocks(days=days, indicator=indicator)
    if data is None:
        return err(f"未能获取最近 {days} 天更新的股票数据", 404)
    return ok(data)


@bp.get("/history_tracking")
@api_guard("获取股票历史跟踪数据")
def history_tracking():
    stock_code = request.args.get("stock_code")
    if not stock_code:
        raise BadParam("缺少股票代码参数")
    days = int_arg("days", 360, min_v=1, max_v=3650)

    data = get_analyst_history_tracking(stock_code, days)
    if not data:
        return err(f"未能获取股票 {stock_code} 的历史关注数据", 404)
    return ok(data)


@bp.get("/latest_tracking")
@api_guard("获取最新跟踪成份股数据")
def latest_tracking():
    top_analysts = top_arg("top_analysts", 50, _ALL)
    top_stocks = top_arg("top_stocks", 50, _ALL)
    logger.info(f"最新跟踪成份股：前{top_analysts}位分析师 / 前{top_stocks}只股票")

    data = get_analyst_latest_tracking(top_analysts=top_analysts, top_stocks=top_stocks)
    if data is None:
        return err("未能获取最新跟踪成份股数据", 404)
    return ok(data)
