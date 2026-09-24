# -*- coding: utf-8 -*-
"""股票监控页 REST API（Flask Blueprint）。

自 `core/web_app.py` 拆出；与 `config_manager`（同属 core）同层，避免跨层依赖。
路由统一在 **`/api/stocks`** 前缀下（原散落的 `/api/settings`、`/api/notification_settings`、
`/api/global_notification_enabled`、`/api/trend_analysis/<code>` 已归入）：

  GET    /api/stocks                              监控股票列表
  POST   /api/stocks                              添加股票
  PUT    /api/stocks/<code>                       更新股票
  DELETE /api/stocks/<code>                       删除股票
  GET    /api/stocks/current_data                 全部实时行情
  GET    /api/stocks/<code>/current_data          单只实时行情
  GET    /api/stocks/<code>/kline                 K 线（趋势分析器）
  GET    /api/stocks/<code>/trend_analysis        趋势交易分析
  GET    /api/stocks/settings                     应用设置（只读；值来自 config.ini）
  GET    /api/stocks/notification_settings        通知设置（读）
  POST   /api/stocks/notification_settings        通知设置（写）
  PUT    /api/stocks/global_notification_enabled  全局通知开关
  PUT    /api/stocks/<code>/notification_enabled  个股通知开关

相对原实现的修复：
  * `PUT /api/stocks/<code>` 原先用 `stock["name"]` 等**直接下标**（缺键 → KeyError 500）→ 改 `.get()` 兜底。
  * `POST /api/stocks` 原先 `data["code"]` 直接下标 → 缺 code 返回 **400**。
  * `kline` 的 `int(period)` 未校验 → 改 `int_arg`（非法 → 400）。
  * `request.json` 无兜底 → 改 `json_body()`（空/非 JSON 不再 500）。
  * 去掉函数内重复 `from ... import get_stock_info`（顶部已导入）。
  * 统一异常处理 `@api_guard`（`BadParam`→400 / 其余→500）。
"""
from __future__ import annotations

from datetime import datetime

from flask import Blueprint, jsonify, request

from config import setup_logger
from ..analyzers.trend_trading_analyzer import TrendTradingAnalyzer
from ..data_fetchers.stock_data_fetcher import get_stock_info, get_stocks_info_batch
from .utils import BadParam, api_guard, err, int_arg, json_body, ok
from .config_manager import config_manager

logger = setup_logger(__name__)

bp = Blueprint("stock_api", __name__, url_prefix="/api")

# 新增/更新股票时的可配置字段（除 code/name 外）
_STOCK_FIELDS = ("low_alert_price", "high_alert_price", "limit_alert",
                 "key_price_alerts", "change_pct_alerts")


def load_stocks() -> list:
    """从配置管理器读取监控股票列表。"""
    try:
        stocks = config_manager.get_all_stocks()
        logger.info(f"从配置管理器加载 {len(stocks)} 只股票")
        return stocks
    except Exception as e:  # noqa: BLE001
        logger.error(f"加载股票配置失败: {e}")
        return []


def _merge_stock(data: dict, base: dict) -> dict:
    """把请求字段合并到现有股票配置上（缺键用原值，避免 KeyError）。"""
    merged = {
        "name": data.get("name", base.get("name", "")),
        "code": data.get("code", base.get("code", "")),
        "notification_enabled": base.get("notification_enabled", True),
    }
    for f in _STOCK_FIELDS:
        merged[f] = data.get(f, base.get(f))
    return merged


# ---------------------------------------------------------------- 列表 / 增删改
@bp.get("/stocks")
@api_guard("获取监控股票列表")
def get_stocks():
    return ok(load_stocks())


@bp.post("/stocks")
@api_guard("添加监控股票")
def add_stock():
    data = json_body()
    code = str(data.get("code") or "").strip()
    if not code:
        raise BadParam("缺少股票代码 code")
    if any(s.get("code") == code for s in load_stocks()):
        return err("股票已存在", 400)

    # 只新增这一只（原实现是遍历全部股票各更新一次）
    config_manager.add_stock(_merge_stock(data, {"notification_enabled": True}))
    return ok(None, message="股票添加成功")


@bp.put("/stocks/<code>")
@api_guard("更新股票配置")
def update_stock(code):
    data = json_body()
    for stock in load_stocks():
        if stock.get("code") == code:
            # 只更新这一只（原实现是遍历全部股票各更新一次）
            config_manager.update_stock(code, _merge_stock(data, stock))
            return ok(None, message="股票更新成功")
    return err("未找到指定股票", 404)


@bp.delete("/stocks/<code>")
@api_guard("删除监控股票")
def delete_stock(code):
    stocks = load_stocks()
    if any(s.get("code") == code for s in stocks):
        config_manager.delete_stock(code)
        return ok(None, message="股票删除成功")
    return err("未找到指定股票", 404)


# ---------------------------------------------------------------- 实时行情
def _quote(code: str) -> dict:
    stock = next((s for s in load_stocks() if s.get("code") == code), None)
    if not stock:
        raise BadParam("未找到指定股票")   # 404 语义由调用方按需覆盖
    info = get_stock_info(stock)
    if not info or "price" not in info:
        raise RuntimeError("无法获取股票数据")
    return {
        "price": info["price"],
        "change_pct": info.get("change_pct", 0),
        "update_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }


@bp.get("/stocks/<code>/current_data")
@api_guard("获取股票实时数据")
def get_current_stock_data(code):
    stocks = load_stocks()
    if not any(s.get("code") == code for s in stocks):
        return err("未找到指定股票", 404)
    return ok(_quote(code))


@bp.get("/stocks/current_data")
@api_guard("获取全部股票实时数据")
def get_all_current_stock_data():
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    stocks = load_stocks()                      # 只读一次（原实现每只都重读配置）
    quotes = get_stocks_info_batch(stocks)      # 最多 2 次网络请求（原实现 N 次）

    all_data = {}
    for stock in stocks:
        info = quotes.get(stock.get("code", ""))
        if info and "price" in info:
            all_data[stock["code"]] = {
                "price": info["price"],
                "change_pct": info.get("change_pct", 0),
                "update_time": now,
            }
    return ok(all_data)


# ---------------------------------------------------------------- 分析与 K 线
@bp.get("/stocks/<code>/kline")
@api_guard("获取 K 线数据")
def get_stock_kline_data(code):
    period = int_arg("period", 365, min_v=5, max_v=3650)
    # 分析器已返回统一形态 {success, data}，直接透传 ——
    # 再包一层 ok() 会变成 {success, data:{success, data:{...}}}，前端 data.data.kline 取不到。
    return jsonify(TrendTradingAnalyzer().get_kline_chart_data(code, "", period))


@bp.get("/stocks/<code>/trend_analysis")
@api_guard("趋势交易分析")
def get_trend_analysis(code):
    name = request.args.get("name", "")
    # 同上：分析器已返回 {success, data}，透传即可
    return jsonify(TrendTradingAnalyzer().analyze_stock_trend(code, name))


# ---------------------------------------------------------------- 设置 / 通知
@bp.get("/stocks/settings")
@api_guard("获取应用设置")
def get_settings():
    """读取应用设置（check_interval / market_open_start / market_open_end）。

    这些值现由 `config.ini [stock_monitor]` 提供（页面上不再提供修改入口），
    此端点仅供前端读取（`isMarketTime()` 判断开市时段用）。
    """
    return ok({
        "check_interval": config_manager.get_check_interval(),
        **config_manager.get_market_times(),
    })


@bp.get("/stocks/notification_settings")
@api_guard("获取通知设置")
def get_notification_settings():
    global_enabled = config_manager.get_global_notification_enabled()
    stock_enabled = {
        s.get("code"): config_manager.get_stock_notification_enabled(s.get("code"))
        for s in load_stocks() if s.get("code")
    }
    return ok({
        "global_notification_enabled": global_enabled,
        "stock_notification_enabled": stock_enabled,
    })


@bp.post("/stocks/notification_settings")
@api_guard("更新通知设置")
def update_notification_settings():
    data = json_body()
    config_manager.set_global_notification_enabled(
        data.get("global_notification_enabled", True))
    for stock_code, enabled in (data.get("stock_notification_enabled") or {}).items():
        config_manager.set_stock_notification_enabled(stock_code, enabled)
    return ok(None, message="消息发送设置更新成功")


@bp.put("/stocks/global_notification_enabled")
@api_guard("更新全局通知开关")
def update_global_notification_enabled():
    enabled = json_body().get("global_notification_enabled", True)
    config_manager.set_global_notification_enabled(enabled)
    return ok(None, message=f"全局消息发送开关已{'开启' if enabled else '关闭'}")


@bp.put("/stocks/<code>/notification_enabled")
@api_guard("更新个股通知开关")
def update_stock_notification_enabled(code):
    enabled = json_body().get("notification_enabled", True)
    config_manager.set_stock_notification_enabled(code, enabled)
    return ok(None, message=f"股票 {code} 消息发送开关已{'开启' if enabled else '关闭'}")
