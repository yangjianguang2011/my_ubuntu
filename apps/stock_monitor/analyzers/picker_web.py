# -*- coding: utf-8 -*-
"""选股器 REST API（Flask Blueprint，挂在主应用）。

响应统一为 `{success, data, message?}`；错误 `{success:false, message}`（见 `core/utils.py`）。

API 一览：
  GET  /api/picker/conditions 条件清单（全局参数 + 技术面/估值面条件及参数规格） → data: 目录
  POST /api/picker/run        执行一次选股扫描（**条件清单驱动**；已在跑则忽略）
                              body: {pool?, global_params?, conditions?: {cid: {enabled, params}},
                                     params?（旧格式，向后兼容）, force?} → data: 任务状态
  GET  /api/picker/status     查询扫描进度／当前结果 → data: 任务状态
  POST /api/picker/stop       停止进行中的扫描
  GET  /api/picker/snapshots  列出历史扫描快照（“我的观察历史”） → data: [快照]
  GET  /api/picker/snapshots/<run_id>  取某次快照的完整命中考 → data: 快照
  GET  /api/picker/params     原有 4 条件的默认值（向后兼容；新前端请用 /conditions）
  GET  /api/picker/pools      可用的股票池 → data: [{key,label}]
"""
from __future__ import annotations

from flask import Blueprint, request

from ..core.utils import api_guard, err, json_body, ok
from ..data_fetchers.pool_data_fetcher import POOL_NAME
from .conditions import condition_catalog
from .picker_rules import Params
from .picker_runner import get_snapshot, list_snapshots, runner

bp = Blueprint("picker", __name__, url_prefix="/api/picker")


@bp.get("/conditions")
@api_guard("获取选股条件清单")
def conditions():
    """条件清单（全局参数 + 分组条件 + 参数规格），供前端**动态生成表单**。"""
    return ok(condition_catalog())


@bp.post("/run")
@api_guard("启动选股扫描")
def run():
    """启动扫描。返回当前任务状态（可能已是 running）。

    未知 `pool`、条件/参数非法 → **400**（`runner.start` 同步抛 `ValueError`）。
    """
    body = json_body()
    try:
        status = runner.start(
            conditions=body.get("conditions"),
            global_params=body.get("global_params"),
            legacy_params=body.get("params"),
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
    """原有 4 条件的默认值（向后兼容；新前端请用 `/conditions`）。"""
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
