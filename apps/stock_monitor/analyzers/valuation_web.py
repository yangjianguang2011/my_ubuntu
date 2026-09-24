# -*- coding: utf-8 -*-
"""估值报告 REST API（Flask Blueprint），挂到 stock_monitor 主应用。

API 一览（统一响应 `{success, data, message?}`；错误 `{success:false, message}`）：
  GET  /api/valuation/pools                     可用股票池 → data: [{key,label}]
  GET  /api/valuation/pool/<pool>/constituents  池成分列表 → data: {pool,label,count,constituents}
  POST /api/valuation/report/run                启动报告计算 body: {code, start?, force?} → data: 任务状态
  GET  /api/valuation/report/status             查询计算进度 → data: 任务状态
  GET  /api/valuation/report/<code>/data        取报告 JSON（需先 run）→ data: 报告
  POST /api/valuation/market/run                启动市场温度计算 body: {force?} → data: 任务状态
  GET  /api/valuation/market/status             查询市场温度进度 → data: 任务状态
  GET  /api/valuation/market/data               取三大指数温度 JSON（需先 run）→ data: 温度
"""
from __future__ import annotations

from flask import Blueprint, request

from config import setup_logger
from ..core.utils import api_guard, err, json_body, ok
from ..data_fetchers.pool_data_fetcher import POOL_NAME, load_pool
from .market_runner import runner as market_runner
from .valuation_runner import runner

logger = setup_logger(__name__)

bp = Blueprint("valuation", __name__, url_prefix="/api/valuation")


@bp.get("/pools")
@api_guard("获取股票池列表")
def pools():
    return ok([{"key": k, "label": v} for k, v in POOL_NAME.items()])


@bp.get("/pool/<pool>/constituents")
@api_guard("读取池成分")
def constituents(pool):
    try:
        rows = load_pool(pool)
    except ValueError as e:
        return err(str(e), 400)
    return ok({
        "pool": pool,
        "label": POOL_NAME.get(pool, pool),
        "count": len(rows),
        "constituents": [{"code": r["code"], "name": r["name"]} for r in rows],
    })


@bp.post("/report/run")
@api_guard("启动估值报告")
def run_report():
    """启动报告计算。返回当前任务状态（可能已在跑）。"""
    body = json_body()
    code = (body.get("code") or "").strip()
    if not code:
        return err("缺少 code 参数", 400)
    status = runner.start(code, start=body.get("start"), force=bool(body.get("force")))
    return ok(status)


@bp.get("/report/status")
@api_guard("查询估值报告进度")
def status():
    return ok(runner.status_dict())


@bp.get("/report/<code>/data")
@api_guard("读取估值报告")
def report_data(code):
    result = runner.get_result(code)
    if result is None:
        return err("报告尚未生成，请先 POST /api/valuation/report/run", 404)
    return ok(result)


# ---- 市场温度（三大指数）----
@bp.post("/market/run")
@api_guard("启动市场温度计算")
def market_run():
    """启动市场温度后台计算。返回当前任务状态。"""
    status = market_runner.start(force=bool(json_body().get("force")))
    return ok(status)


@bp.get("/market/status")
@api_guard("查询市场温度进度")
def market_status():
    return ok(market_runner.status_dict())


@bp.get("/market/data")
@api_guard("读取市场温度")
def market_data():
    result = market_runner.get_result()
    if result is None:
        return err("市场温度尚未计算，请先 POST /api/valuation/market/run", 404)
    return ok(result)
