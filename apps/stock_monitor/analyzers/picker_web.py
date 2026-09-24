# -*- coding: utf-8 -*-
"""选股器 REST API（Flask Blueprint，挂在主应用）。

响应统一为 `{success, data, message?}`；错误 `{success:false, message}`（见 `core/utils.py`）。

API 一览：
  POST /api/picker/run       执行一次选股扫描（参数可选；已在跑则忽略）
                             body: {pool?: 'hs300'|'zz500', params?: {...}, force?: bool} → data: 任务状态
  GET  /api/picker/status    查询扫描进度／当前结果 → data: 任务状态
  POST /api/picker/stop      停止进行中的扫描
  GET  /api/picker/snapshots 列出历史扫描快照（“我的观察历史”） → data: [快照]
  GET  /api/picker/snapshots/<run_id>  取某次快照的完整命中考 → data: 快照
  GET  /api/picker/params    当前可调参数及默认值（前端表单据此生成） → data: {参数}
  GET  /api/picker/pools     可用的股票池 → data: [{key,label}]
"""
from __future__ import annotations

from flask import Blueprint, request

from ..core.utils import api_guard, err, json_body, ok
from ..data_fetchers.pool_data_fetcher import POOL_NAME
from .picker_rules import Params
from .picker_runner import get_snapshot, list_snapshots, runner

bp = Blueprint("picker", __name__, url_prefix="/api/picker")


@bp.post("/run")
@api_guard("启动选股扫描")
def run():
    """启动扫描。返回当前任务状态（可能已是 running）。

    未知 `pool`、或 `params` 取值非法 → **400**（`runner.start` 同步抛 `ValueError`）。
    """
    body = json_body()
    try:
        status = runner.start(
            params_dict=body.get("params") or {},
            pool=body.get("pool") or "hs300",
            force_refresh=bool(body.get("force")),
        )
    except ValueError as e:
        return err(str(e), 400)
    return ok(status)


@bp.get("/status")
@api_guard("查询选股进度")
def status():
    return ok(runner.status_dict())


@bp.post("/stop")
@api_guard("停止选股扫描")
def stop():
    runner.stop()
    return ok(None, message="已请求停止")


@bp.get("/pools")
@api_guard("获取选股股票池")
def pools():
    return ok([{"key": k, "label": v} for k, v in POOL_NAME.items()])


@bp.get("/params")
@api_guard("获取选股参数默认值")
def params():
    return ok(Params().to_dict())


@bp.get("/snapshots")
@api_guard("获取扫描快照列表")
def snapshots():
    limit = request.args.get("limit", default=20, type=int)
    return ok(list_snapshots(limit=max(1, min(limit, 200))))


@bp.get("/snapshots/<run_id>")
@api_guard("获取扫描快照详情")
def snapshot_detail(run_id):
    snap = get_snapshot(run_id)
    if not snap:
        return err("快照不存在", 404)
    return ok(snap)
