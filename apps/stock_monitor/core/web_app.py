#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
股票监控管理应用 —— **应用骨架 + 蓝图装配**。

各功能域的 REST API 均已拆为独立 Blueprint：
  * 选股器      → `analyzers/picker_web.py`
  * 估值报告    → `analyzers/valuation_web.py`
  * 基金页      → `data_fetchers/fund_web.py`
  * 指数页      → `data_fetchers/index_web.py`
  * 分析师页    → `data_fetchers/analyst_web.py`
  * 股票监控页  → `core/stock_web.py`
  * 公共助手    → `core/utils.py`
本模块只保留：Flask 实例、静态文件路由、首页渲染、缓存预热占位与蓝图注册。
行业页已下线（akshare 行业接口失效）。
"""
from flask import Flask, jsonify, render_template

from config import setup_logger

logger = setup_logger(__name__)

app = Flask(__name__, template_folder="../web_templates", static_folder="../web_static")


# 选股器模块(REST blueprint)。延迟导入避免与顶层路由在加载期相互依赖。
def _register_picker_blueprint():
    try:
        from ..analyzers import picker_web

        app.register_blueprint(picker_web.bp)
    except Exception as e:  # noqa: BLE001
        logger.error("选股器(blueprint)注册失败，请检查 analyzers/picker_* 依赖: %s", e)


# 估值报告模块(REST blueprint)。依赖 stockdb/akshare，失败不阻塞主应用。
def _register_valuation_blueprint():
    try:
        from ..analyzers import valuation_web

        app.register_blueprint(valuation_web.bp)
    except Exception as e:  # noqa: BLE001
        logger.error("估值报告(blueprint)注册失败，请检查 stockdb/akshare 依赖: %s", e)


# 基金/指数数据统计页（REST blueprint）——各自独立模块，失败不阻塞主应用
def _register_fund_blueprint():
    try:
        from ..data_fetchers import fund_web

        app.register_blueprint(fund_web.bp)
    except Exception as e:  # noqa: BLE001
        logger.error("基金页(blueprint)注册失败: %s", e)


def _register_index_blueprint():
    try:
        from ..data_fetchers import index_web

        app.register_blueprint(index_web.bp)
    except Exception as e:  # noqa: BLE001
        logger.error("指数页(blueprint)注册失败: %s", e)


def _register_analyst_blueprint():
    try:
        from ..data_fetchers import analyst_web

        app.register_blueprint(analyst_web.bp)
    except Exception as e:  # noqa: BLE001
        logger.error("分析师页(blueprint)注册失败: %s", e)


def _register_stock_blueprint():
    try:
        from . import stock_web

        app.register_blueprint(stock_web.bp)
    except Exception as e:  # noqa: BLE001
        logger.error("股票监控(blueprint)注册失败: %s", e)


_register_stock_blueprint()
_register_fund_blueprint()
_register_index_blueprint()
_register_analyst_blueprint()
_register_picker_blueprint()
_register_valuation_blueprint()

# 添加显式的静态文件路由
@app.route("/static/<path:filename>")
def static_files(filename):
    from flask import send_from_directory

    # 使用全局定义的静态文件目录
    return send_from_directory("../web_static", filename)


@app.route("/")
def index():
    """主页面（单页多标签应用）"""
    return render_template("index.html")


@app.route("/api/warmup_cache", methods=["POST"])
def warmup_cache():
    """手动触发缓存预热。

    说明：各数据现均按需实时获取（含各自缓存），此处不再做批量预热；
    保留端点以兼容旧调用。
    """
    logger.info("手动触发缓存预热（占位：各数据按需实时获取）")
    return jsonify({
        "success": True,
        "data": None,
        "message": "缓存预热：各数据按需实时获取，无需批量预热",
    })

# 启动入口统一为 `python start_app.py`（本模块不再自带 __main__）。
