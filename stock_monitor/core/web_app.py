#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
股票监控管理应用
提供Web界面来管理监控股票
"""
import json
import logging
import os
from datetime import datetime, timedelta

from flask import Flask, jsonify, render_template, request

from config import get_path, setup_logger

logger = setup_logger(__name__)

# 所有导入都放在这里，避免在函数内部导入
from ..analyzers.trend_trading_analyzer import TrendTradingAnalyzer
from ..data_fetchers.analyst_data_fetcher import (
    get_analyst_focus_stocks,
    get_analyst_history_tracking,
    get_analyst_latest_tracking,
    get_analyst_updated_stocks,
)
from ..data_fetchers.fund_data_fetcher import (
    get_fund_chart_data,
    get_fund_dynamic_list,
    get_fund_ranking,
    get_selected_fund_list,
)
from ..data_fetchers.index_data_fetcher import (
    get_detailed_index_ranking,
    get_index_chart_data,
    get_index_dynamic_list,
    get_index_ranking,
)
from ..data_fetchers.industry_data_fetcher import (
    get_industry_char_data,
    get_industry_constituents,
    get_industry_ranking,
)
from ..data_fetchers.stock_data_fetcher import get_stock_info

app = Flask(__name__, template_folder="../web_templates", static_folder="../web_static")


# 添加显式的静态文件路由
@app.route("/static/<path:filename>")
def static_files(filename):
    from flask import send_from_directory

    # 使用全局定义的静态文件目录
    return send_from_directory("../web_static", filename)


@app.route("/api/warmup_cache", methods=["POST"])
def warmup_cache():
    """手动触发缓存预热"""
    try:
        logger.info("手动触发缓存预热...")

        # # 预加载分析师数据
        # from analyst_data_fetcher import get_combined_analyst_data
        # from industry_data_fetcher import get_industry_ranking
        # from index_data_fetcher import get_index_selected_list, get_index_ranking, get_index_history, get_multiple_index_history, calculate_growth_rate
        # analyst_data = get_combined_analyst_data(top_analysts=20, top_stocks=50, period="3个月")
        # industry_data = get_industry_ranking(period="30")
        # index_data = get_index_selected_list()  # 预加载指数数据

        # return jsonify({
        #     "success": True,
        #     "message": "缓存预热完成",
        #     "analyst_data_count": len(analyst_data.get('top_focus_stocks', [])),
        #     "industry_data_count": len(industry_data),
        #     "index_data_count": len(index_data)
        # })
    except Exception as e:
        logger.error(f"缓存预热失败: {str(e)}")
        return jsonify({"success": False, "message": f"缓存预热失败: {str(e)}"}), 500


#############################################################stocks###################################
def load_stocks():
    """加载股票配置 - 现在从配置管理器获取"""
    from .config_manager import config_manager

    try:
        stocks = config_manager.get_all_stocks()
        logger.info(f"从配置管理器加载 {len(stocks)} 只股票")
        return stocks
    except Exception as e:
        logger.error(f"从配置管理器加载股票配置失败: {str(e)}...\n\n")
        return []


def save_stocks(stocks):
    """保存股票配置 - 现在通过配置管理器保存"""
    from .config_manager import config_manager

    try:
        for stock in stocks:
            config_manager.update_stock(stock["code"], stock)
        logger.info(f"通过配置管理器保存 {len(stocks)} 只股票配置")
    except Exception as e:
        logger.error(f"通过配置管理器保存股票配置失败: {str(e)} ...\n\n")


@app.route("/")
def index():
    """主页面"""
    return render_template("index.html")


@app.route("/api/stocks", methods=["GET"])
def get_stocks():
    """获取所有监控股票"""
    stocks = load_stocks()
    return jsonify({"stocks": stocks})


@app.route("/api/stocks", methods=["POST"])
def add_stock():
    """添加新的监控股票"""
    data = request.json
    stocks = load_stocks()

    # 检查股票是否已存在
    for stock in stocks:
        if stock["code"] == data["code"]:
            return jsonify({"success": False, "message": "股票已存在"}), 400

    # 添加新股票
    new_stock = {
        "name": data.get("name", ""),
        "code": data.get("code", ""),
        "low_alert_price": data.get("low_alert_price"),
        "high_alert_price": data.get("high_alert_price"),
        "limit_alert": data.get("limit_alert", False),
        "key_price_alerts": data.get("key_price_alerts", []),
        "change_pct_alerts": data.get("change_pct_alerts", []),
        "notification_enabled": True,  # 默认启用通知
    }

    stocks.append(new_stock)
    save_stocks(stocks)

    return jsonify({"success": True, "message": "股票添加成功"})


@app.route("/api/stocks/<code>", methods=["PUT"])
def update_stock(code):
    """更新股票配置"""
    data = request.json
    stocks = load_stocks()

    for i, stock in enumerate(stocks):
        if stock["code"] == code:
            # 保留原有的notification_enabled状态
            current_notification_enabled = stock.get("notification_enabled", True)
            stocks[i] = {
                "name": data.get("name", stock["name"]),
                "code": data.get("code", stock["code"]),
                "low_alert_price": data.get(
                    "low_alert_price", stock["low_alert_price"]
                ),
                "high_alert_price": data.get(
                    "high_alert_price", stock["high_alert_price"]
                ),
                "limit_alert": data.get("limit_alert", stock["limit_alert"]),
                "key_price_alerts": data.get(
                    "key_price_alerts", stock["key_price_alerts"]
                ),
                "change_pct_alerts": data.get(
                    "change_pct_alerts", stock["change_pct_alerts"]
                ),
                "notification_enabled": current_notification_enabled,  # 保留原有通知设置
            }
            save_stocks(stocks)
            return jsonify({"success": True, "message": "股票更新成功"})

    return jsonify({"success": False, "message": "未找到指定股票"}), 404


@app.route("/api/stocks/<code>", methods=["DELETE"])
def delete_stock(code):
    """删除监控股票"""
    from .config_manager import config_manager

    stocks = load_stocks()
    original_length = len(stocks)
    stocks = [stock for stock in stocks if stock["code"] != code]

    if len(stocks) < original_length:
        config_manager.delete_stock(code)
        return jsonify({"success": True, "message": "股票删除成功"})
    else:
        return jsonify({"success": False, "message": "未找到指定股票"}), 404


@app.route("/api/stocks/<code>/current_data", methods=["GET"])
def get_current_stock_data(code):
    """获取单个股票的实时数据"""
    try:
        from ..data_fetchers.stock_data_fetcher import get_stock_info

        stocks = load_stocks()
        stock = next((s for s in stocks if s["code"] == code), None)
        if not stock:
            return jsonify({"success": False, "message": "未找到指定股票"}), 404

        stock_info = get_stock_info(stock)
        if stock_info and "price" in stock_info:
            current_data = {
                "success": True,
                "data": {
                    "price": stock_info["price"],
                    "change_pct": stock_info.get("change_pct", 0),
                    "update_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                },
            }
            return jsonify(current_data)
        else:
            return jsonify({"success": False, "message": "无法获取股票数据"}), 500
    except Exception as e:
        return jsonify({"success": False, "message": f"获取数据时出错: {str(e)}"}), 500


@app.route("/api/stocks/current_data", methods=["GET"])
def get_all_current_stock_data():
    """获取所有股票的实时数据"""
    try:
        from ..data_fetchers.stock_data_fetcher import get_stock_info

        stocks = load_stocks()
        all_data = {}
        for stock in stocks:
            try:
                stock_info = get_stock_info(stock)
                if stock_info and "price" in stock_info:
                    all_data[stock["code"]] = {
                        "price": stock_info["price"],
                        "change_pct": stock_info.get("change_pct", 0),
                        "update_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    }
            except Exception:
                # 如果某个股票数据获取失败，继续处理下一个
                continue
        return jsonify({"success": True, "data": all_data})
    except Exception as e:
        return jsonify({"success": False, "message": f"获取数据时出错: {str(e)}"}), 500


############################################## analyst APIs ##################################################


@app.route("/api/analyst/focus_stocks", methods=["GET"])
def get_analyst_focus_stocks_api():
    """获取分析师重点关注股票"""
    try:
        # 获取查询参数
        period = request.args.get("period", "3个月")
        top_analysts = request.args.get("top_analysts", 50)
        top_stocks = request.args.get("top_stocks", 50)

        # 处理 'all' 参数
        if top_analysts == "all":
            top_analysts = 100  #   使用一个大数来获取所有分析师
        else:
            top_analysts = int(top_analysts)

        if top_stocks == "all":
            top_stocks = 9999  # 使用一个大数来获取所有股票
        else:
            top_stocks = int(top_stocks)

        logger.info(
            f"请求分析师重点关注股票，周期: {period}, 前{top_analysts}名分析师, 前{top_stocks}只股票"
        )

        # 使用analyst_data_fetcher中的函数获取数据
        # 导入已在文件顶部完成

        focus_stocks_result = get_analyst_focus_stocks(
            top_analysts=top_analysts, top_stocks=top_stocks, period=period
        )

        if focus_stocks_result:
            return jsonify(
                {
                    "success": True,
                    "data": focus_stocks_result,
                    "period": period,
                    "top_analysts": top_analysts,
                    "top_stocks": top_stocks,
                }
            )
        else:
            return (
                jsonify(
                    {
                        "success": False,
                        "message": f"未能获取分析师重点关注股票数据，周期: {period}",
                    }
                ),
                404,
            )

    except Exception as e:
        logger.error(f"获取分析师重点关注股票失败: {str(e)}")
        return (
            jsonify(
                {"success": False, "message": f"获取分析师重点关注股票失败: {str(e)}"}
            ),
            500,
        )


@app.route("/api/analyst/updated_stocks", methods=["GET"])
def get_analyst_updated_stocks_api():
    """获取最近更新的股票数据"""
    try:
        # 获取查询参数
        days = int(request.args.get("days"))  # 天数参数，表示最近几天内更新的股票
        logger.info(f"请求最近更新的股票数据，天数: {days}")

        # 调用analyst_data_fetcher中的函数获取数据
        # 导入已在文件顶部完成

        stocks_data = get_analyst_updated_stocks(days=days)

        if stocks_data is not None:
            # 计算日期阈值用于返回给前端
            from datetime import datetime, timedelta

            date_threshold = (datetime.now() - timedelta(days=days)).strftime(
                "%Y-%m-%d"
            )
            return jsonify(
                {
                    "success": True,
                    "data": stocks_data,
                    "days": days,
                    "date_threshold": date_threshold,
                }
            )
        else:
            return (
                jsonify(
                    {
                        "success": False,
                        "message": f"未能获取最近更新的股票数据，天数: {days}",
                    }
                ),
                404,
            )

    except Exception as e:
        logger.error(f"获取最近更新的股票数据失败: {str(e)}")
        return (
            jsonify(
                {"success": False, "message": f"获取最近更新的股票数据失败: {str(e)}"}
            ),
            500,
        )


@app.route("/api/analyst/history_tracking", methods=["GET"])
def get_analyst_history_tracking_api():
    """获取股票历史分析师跟踪数据"""
    try:
        stock_code = request.args.get("stock_code")
        days = request.args.get("days", 360)  # 默认30天

        if not stock_code:
            return jsonify({"success": False, "message": "缺少股票代码参数"}), 400

        # 调用分析师数据获取函数
        # 导入已在文件顶部完成

        history_data = get_analyst_history_tracking(stock_code, int(days))

        if history_data:
            return jsonify(
                {"success": True, "data": history_data, "stock_code": stock_code}
            )
        else:
            return (
                jsonify(
                    {
                        "success": False,
                        "message": f"未能获取股票 {stock_code} 的历史跟踪数据",
                    }
                ),
                404,
            )

    except Exception as e:
        logger.error(f"获取股票历史跟踪数据失败: {str(e)}")
        return (
            jsonify(
                {"success": False, "message": f"获取股票历史跟踪数据失败: {str(e)}"}
            ),
            500,
        )


@app.route("/api/analyst/latest_tracking", methods=["GET"])
def get_analyst_latest_tracking_api():
    """获取最新跟踪成份股数据"""
    try:
        # 获取查询参数
        period = request.args.get("period", "3个月")
        top_analysts = request.args.get("top_analysts", 50)
        top_stocks = request.args.get("top_stocks", 50)  # 添加top_stocks参数

        # 处理 'all' 参数
        if top_analysts == "all":
            top_analysts = 999  # 使用一个大数来获取所有分析师
        else:
            top_analysts = int(top_analysts)

        if top_stocks == "all":
            top_stocks = 9999  # 使用一个大数来获取所有股票
        else:
            top_stocks = int(top_stocks)

        logger.info(
            f"请求最新跟踪成份股数据，周期: {period}, 前{top_analysts}名分析师, 前{top_stocks}只股票"
        )

        # 使用analyst_data_fetcher中的函数获取数据
        # 导入已在文件顶部完成

        latest_tracking_data = get_analyst_latest_tracking(
            top_analysts=top_analysts, top_stocks=top_stocks, period=period
        )

        if latest_tracking_data is not None:
            return jsonify(
                {
                    "success": True,
                    "data": latest_tracking_data,
                    "period": period,
                    "top_analysts": top_analysts,
                    "top_stocks": top_stocks,
                }
            )
        else:
            return (
                jsonify(
                    {
                        "success": False,
                        "message": f"未能获取最新跟踪成份股数据，周期: {period}",
                    }
                ),
                404,
            )

    except Exception as e:
        logger.error(f"获取最新跟踪成份股数据失败: {str(e)}")
        return (
            jsonify(
                {"success": False, "message": f"获取最新跟踪成份股数据失败: {str(e)}"}
            ),
            500,
        )


################################################ industry APIs ##################################################
@app.route("/api/industry/char_data", methods=["POST"])
def get_industry_chart_data_api():
    """获取行业图表数据（用于ECharts展示）"""
    try:
        # 获取请求参数
        data = request.json
        industry_names = data.get("industries", [])
        period = data.get("period", "365")

        # 验证参数
        if not industry_names or len(industry_names) == 0:
            return jsonify({"success": False, "message": "请至少选择一个行业"}), 400

        if len(industry_names) > 10:
            return (
                jsonify({"success": False, "message": "最多只能选择10个行业进行对比"}),
                400,
            )

        # 验证周期参数
        valid_periods = ["30", "90", "180", "365", "1825"]
        if period not in valid_periods:
            period = "365"

        logger.info(f"请求行业图表数据，行业: {industry_names}, 周期: {period}天")

        # 获取图表数据
        # 导入已在文件顶部完成

        chart_data = get_industry_char_data(industry_names, period)

        if chart_data:
            return jsonify(
                {
                    "success": True,
                    "data": chart_data,
                    "message": f"成功获取 {len(chart_data['series'])} 个行业的图表数据",
                }
            )
        else:
            return jsonify({"success": False, "message": "获取行业图表数据失败"}), 500

    except Exception as e:
        logger.error(f"获取行业图表数据异常: {str(e)}")
        return (
            jsonify({"success": False, "message": f"获取行业图表数据异常: {str(e)}"}),
            500,
        )


@app.route("/api/industry/ranking_data", methods=["GET"])
def get_industry_ranking_data_api():
    """获取行业板块数据"""
    try:
        # 获取查询参数
        period = request.args.get("period", "30")  # 默认30天
        top_n = request.args.get("top_n", "20")  # 默认前20个

        # 验证周期参数
        valid_periods = ["1", "30", "60", "120", "365"]
        if period not in valid_periods:
            period = "30"

        # 获取行业排行数据
        # 导入已在文件顶部完成

        logger.info(f"请求行业数据，周期: {period}天, 前N个: {top_n}")

        ranking_data = get_industry_ranking(period)

        if not ranking_data:
            return jsonify({"success": False, "message": "暂无行业数据"}), 404

        # 根据涨跌幅排序后取前N个
        top_ranking = ranking_data[: int(top_n)]

        # 分离涨幅和跌幅前N个
        top_gainers = top_ranking[: int(top_n)]  # 涨幅前N个（已按涨幅排序）
        top_losers = ranking_data[
            -int(top_n) :
        ]  # 跌幅前N个（按跌幅排序，即涨幅最小的）
        top_losers = sorted(top_losers, key=lambda x: x["change_pct"], reverse=False)[
            : int(top_n)
        ]

        return jsonify(
            {
                "success": True,
                "data": {
                    "top_gainers": top_gainers,  # 涨幅前N个
                    "top_losers": top_losers,  # 跌幅前N个
                    "total_count": len(ranking_data),
                    "period": period,
                },
                "message": f"获取行业{period}天涨跌幅排行成功",
            }
        )
    except Exception as e:
        return (
            jsonify({"success": False, "message": f"获取行业数据失败: {str(e)}"}),
            500,
        )


@app.route("/api/industry/constituents", methods=["GET"])
def get_industry_constituents():
    """获取行业成份股数据"""
    try:
        # 获取查询参数
        industry_name = request.args.get("industry_name", "")
        if not industry_name:
            return jsonify({"success": False, "message": "缺少行业名称参数"}), 40

        # 获取行业成份股数据
        # 导入已在文件顶部完成

        logger.info(f"请求行业成份股数据，行业: {industry_name}")
        constituents = get_industry_constituents(industry_name)

        if not constituents:
            return (
                jsonify(
                    {
                        "success": False,
                        "message": f"未找到行业 '{industry_name}' 的成份股数据",
                    }
                ),
                404,
            )

        return jsonify(
            {
                "success": True,
                "data": constituents,
                "industry_name": industry_name,
                "message": f"获取行业 '{industry_name}' 成份股数据成功",
            }
        )
    except Exception as e:
        return (
            jsonify({"success": False, "message": f"获取行业成份股数据失败: {str(e)}"}),
            500,
        )


################################################ index APIs ##################################################
@app.route("/api/index/dynamic_list", methods=["GET"])
def get_index_dynamic_list_api():
    # 导入已在文件顶部完成

    """获取主要指数列表用于显示基金走势对比图"""
    try:
        sort_by_change = request.args.get(
            "sort", "none"
        )  # 'none', 'change_asc', 'change_desc'
        logger.info(f"请求主要指数列表，排序方式: {sort_by_change}")
        index_list = get_index_dynamic_list(top_n=28)  # 获取动态选择的主要指数列表

        if index_list:
            # 根据参数决定是否按涨跌幅排序
            if sort_by_change == "change_desc":
                # 按涨跌幅降序排列
                index_list.sort(key=lambda x: x["change_percent"], reverse=True)
            elif sort_by_change == "change_asc":
                # 按涨跌幅升序排列
                index_list.sort(key=lambda x: x["change_percent"])

            return jsonify(
                {
                    "success": True,
                    "data": index_list,
                    "message": f"成功获取 {len(index_list)} 个主要指数数据",
                }
            )
        else:
            return jsonify({"success": False, "message": "暂无指数数据"}), 404
    except Exception as e:
        logger.error(f"获取主要指数列表失败: {str(e)}")
        return (
            jsonify({"success": False, "message": f"获取主要指数列表失败: {str(e)}"}),
            500,
        )


@app.route("/api/index/ranking", methods=["GET"])
def get_index_ranking_api():
    """获取指数涨跌幅排名"""
    try:
        top_n = request.args.get("top_n", "28")  # 默认前28个
        period = request.args.get("period", "30")  # 默认30天周期

        # 将字符串参数转换为整数，使用默认值处理无效输入
        try:
            top_n = int(top_n)
        except (ValueError, TypeError):
            top_n = 28  # 如果转换失败，使用默认值
            logger.warning(f"top_n 参数无效，使用默认值: {top_n}")
        try:
            period = int(period)
        except (ValueError, TypeError):
            period = 30  # 如果转换失败，使用默认值
            logger.warning(f"period 参数无效，使用默认值: {period}")

        logger.info(f"请求指数涨跌幅排名，前N个: {top_n}, 周期: {period}天")

        # 导入已在文件顶部完成

        ranking_data = get_index_ranking(period_days=period)
        logger.info(f"获取到 {len(ranking_data) if ranking_data else 0} 条指数排名数据")

        if not ranking_data or len(ranking_data) == 0:
            return jsonify(
                {
                    "success": True,  # 改为返回成功但无数据，避免前端错误
                    "data": {
                        "top_gainers": [],
                        "total_count": 0,
                        "top_n": top_n,
                        "period": period,
                    },
                    "message": "暂无指数排名数据",
                }
            )

        # 取前N个指数作为涨幅榜（数据已按涨幅排序）
        top_gainers = ranking_data[:top_n]
        logger.info(f"选取前 {len(top_gainers)} 名指数作为涨幅榜")

        return jsonify(
            {
                "success": True,
                "data": {
                    "top_gainers": top_gainers,  # 涨幅前N个
                    "total_count": len(ranking_data),
                    "top_n": top_n,
                    "period": period,
                },
                "message": f"获取指数涨跌幅排行成功，共 {len(ranking_data)} 个指数数据",
            }
        )
    except Exception as e:
        logger.error(f"获取指数排名数据失败: {str(e)}", exc_info=True)
        return (
            jsonify({"success": False, "message": f"获取指数排名数据失败: {str(e)}"}),
            500,
        )


@app.route("/api/index/enhanced_ranking", methods=["GET"])
def get_enhanced_index_ranking_api():
    """获取增强的指数排名（包含估值数据）"""
    try:
        top_n = request.args.get("top_n", "28")  # 默认前28个
        period = request.args.get("period", "30")  # 默认30天周期

        # 将字符串参数转换为整数，使用默认值处理无效输入
        try:
            top_n = int(top_n)
        except (ValueError, TypeError):
            top_n = 28
            logger.warning(f"top_n 参数无效，使用默认值: {top_n}")
        try:
            period = int(period)
        except (ValueError, TypeError):
            period = 30
            logger.warning(f"period 参数无效，使用默认值: {period}")

        logger.info(f"请求增强指数排名，前N个: {top_n}, 周期: {period}天")

        # 导入已在文件顶部完成

        ranking_data = get_detailed_index_ranking(
            period_days=period, include_valuation=True
        )
        logger.info(
            f"获取到 {len(ranking_data) if ranking_data else 0} 条增强指数排名数据"
        )

        if not ranking_data or len(ranking_data) == 0:
            return jsonify(
                {
                    "success": True,
                    "data": {
                        "top_gainers": [],
                        "total_count": 0,
                        "top_n": top_n,
                        "period": period,
                    },
                    "message": "暂无增强指数排名数据",
                }
            )

        # 取前N个指数作为涨幅榜（数据已按涨幅排序）
        top_gainers = ranking_data[:top_n]
        logger.info(f"选取前 {len(top_gainers)} 名指数作为涨幅榜")

        return jsonify(
            {
                "success": True,
                "data": {
                    "top_gainers": top_gainers,  # 涨幅前N个
                    "total_count": len(ranking_data),
                    "top_n": top_n,
                    "period": period,
                },
                "message": f"获取增强指数涨跌幅排行成功，共 {len(ranking_data)} 个指数数据",
            }
        )
    except Exception as e:
        logger.error(f"获取增强指数排名数据失败: {str(e)}", exc_info=True)
        return (
            jsonify(
                {"success": False, "message": f"获取增强指数排名数据失败: {str(e)}"}
            ),
            500,
        )


# @app.route('/api/index_history', methods=['GET'])
# def get_index_history_api():
#     """获取单个指数历史数据"""
#     try:
#         # 获取查询参数
#         symbol = request.args.get('symbol', '')
#         period = request.args.get('period', '12M')  # 默认12个月

#         if not symbol:
#             return jsonify({
#                 "success": False,
#                 "message": "缺少指数代码参数"
#             }), 400

#         logger.info(f"请求指数历史数据，代码: {symbol}, 周期: {period}")
#         history_data = get_index_history(symbol, period)

#         if history_data:
#             return jsonify({
#                 "success": True,
#                 "data": history_data,
#                 "symbol": symbol,
#                 "period": period,
#                 "message": f"成功获取指数 {symbol} 的 {len(history_data)} 条历史数据"
#             })
#         else:
#             return jsonify({
#                 "success": False,
#                 "message": f"暂无指数 {symbol} 的历史数据"
#             }), 404
#     except Exception as e:
#         logger.error(f"获取指数历史数据失败: {str(e)}")
#         return jsonify({
#             "success": False,
#             "message": f"获取指数历史数据失败: {str(e)}"
#         }), 500


@app.route("/api/index/chart_data", methods=["POST"])
def get_index_chart_data_api():
    """获取指数图表数据（用于ECharts展示）"""
    try:
        # 获取请求参数
        data = request.json
        symbols = data.get("symbols", [])
        period = data.get("period", "12M")
        use_growth_rate = data.get("use_growth_rate", True)  # 是否使用增长率对比

        # 验证参数
        if not symbols or len(symbols) == 0:
            return jsonify({"success": False, "message": "请至少选择一个指数"}), 400

        if len(symbols) > 10:
            return (
                jsonify({"success": False, "message": "最多只能选择10个指数进行对比"}),
                400,
            )

        logger.info(
            f"请求指数图表数据，指数: {symbols}, 周期: {period}, 使用增长率: {use_growth_rate}"
        )

        # 使用index_data_fetcher中的函数准备图表数据
        # 导入已在文件顶部完成

        chart_data = get_index_chart_data(symbols, period, use_growth_rate)

        if chart_data and chart_data.get("series"):
            return jsonify(
                {
                    "success": True,
                    "data": chart_data,
                    "message": f"成功获取 {len(chart_data['series'])} 个指数的图表数据",
                }
            )
        else:
            return jsonify({"success": False, "message": "构建指数图表数据失败"}), 500

    except Exception as e:
        logger.error(f"获取指数图表数据失败: {str(e)}", exc_info=True)
        return (
            jsonify({"success": False, "message": f"获取指数图表数据失败: {str(e)}"}),
            500,
        )


################################################ fund APIs ##################################################
@app.route("/api/fund/list", methods=["GET"])
def get_fund_list_api():
    """获取基金列表"""
    try:
        sort_by_change = request.args.get(
            "sort", "none"
        )  # 'none', 'change_asc', 'change_desc'
        logger.info(f"请求基金列表，排序方式: {sort_by_change}")

        # 导入已在文件顶部完成

        fund_list = get_selected_fund_list()

        if fund_list:
            # 根据参数决定是否按涨跌幅排序
            # 注意：这里我们只是返回基金列表，实际的涨跌幅计算在排名API中进行
            return jsonify(
                {
                    "success": True,
                    "data": fund_list,
                    "message": f"成功获取 {len(fund_list)} 个基金数据",
                }
            )
        else:
            return jsonify({"success": False, "message": "暂无基金数据"}), 404
    except Exception as e:
        logger.error(f"获取基金列表失败: {str(e)}")
        return (
            jsonify({"success": False, "message": f"获取基金列表失败: {str(e)}"}),
            500,
        )


@app.route("/api/fund/dynamic_list", methods=["GET"])
def get_fund_dynamic_list_api():
    """获取动态选择的基金列表（基于收益率排名）
    用于显示基金走势对比图
    """
    try:
        top_n = request.args.get("top_n", "28")  # 默认前28个
        period = request.args.get("period", "30D")  # 默认30天周期
        sort_by_change = request.args.get(
            "sort", "none"
        )  # 'none', 'change_asc', 'change_desc'

        # 将字符串参数转换为适当的类型
        try:
            top_n = int(top_n)
        except (ValueError, TypeError):
            top_n = 28  # 如果转换失败，使用默认值
            logger.warning(f"top_n 参数无效，使用默认值: {top_n}")

        logger.info(
            f"请求动态基金列表，前N个: {top_n}, 周期: {period}, 排序方式: {sort_by_change}"
        )

        # 导入已在文件顶部完成

        fund_list = get_fund_dynamic_list(top_n=top_n, period=period)

        if fund_list:
            # 根据参数决定是否按涨跌幅排序
            if sort_by_change == "change_desc":
                # 按涨跌幅降序排列
                fund_list.sort(key=lambda x: x["change_percent"], reverse=True)
            elif sort_by_change == "change_asc":
                # 按涨跌幅升序排列
                fund_list.sort(key=lambda x: x["change_percent"])

            return jsonify(
                {
                    "success": True,
                    "data": fund_list,
                    "message": f"成功获取 {len(fund_list)} 个动态基金数据",
                }
            )
        else:
            return jsonify({"success": False, "message": "暂无基金数据"}), 404
    except Exception as e:
        logger.error(f"获取动态基金列表失败: {str(e)}")
        return (
            jsonify({"success": False, "message": f"获取动态基金列表失败: {str(e)}"}),
            500,
        )


@app.route("/api/fund/ranking", methods=["GET"])
def get_fund_ranking_api():
    """获取基金涨跌幅排名"""
    try:
        top_n = request.args.get("top_n", "28")  # 默认前28个
        period = request.args.get("period", "30")  # 默认30天周期

        # 将字符串参数转换为整数，使用默认值处理无效输入
        try:
            top_n = int(top_n)
        except (ValueError, TypeError):
            top_n = 28  # 如果转换失败，使用默认值
            logger.warning(f"top_n 参数无效，使用默认值: {top_n}")
        try:
            period = int(period)
        except (ValueError, TypeError):
            period = 30  # 如果转换失败，使用默认值
            logger.warning(f"period 参数无效，使用默认值: {period}")

        logger.info(f"请求基金涨跌幅排名，前N个: {top_n}, 周期: {period}天")

        # 导入已在文件顶部完成

        ranking_data = get_fund_ranking(period=f"{period}D")
        logger.info(f"获取到 {len(ranking_data) if ranking_data else 0} 条基金排名数据")

        if not ranking_data or len(ranking_data) == 0:
            return jsonify(
                {
                    "success": True,  # 改为返回成功但无数据，避免前端错误
                    "data": {
                        "top_gainers": [],
                        "total_count": 0,
                        "top_n": top_n,
                        "period": period,
                    },
                    "message": "暂无基金排名数据",
                }
            )

        top_gainers = ranking_data[:top_n]

        return jsonify(
            {
                "success": True,
                "data": {
                    "top_gainers": top_gainers,  # 涨幅前N个
                    "total_count": len(ranking_data),
                    "top_n": top_n,
                    "period": period,
                },
                "message": f"获取基金涨跌幅排行成功，共 {len(ranking_data)} 个基金数据",
            }
        )
    except Exception as e:
        logger.error(f"获取基金排名数据失败: {str(e)}", exc_info=True)
        return (
            jsonify({"success": False, "message": f"获取基金排名数据失败: {str(e)}"}),
            500,
        )


@app.route("/api/fund/chart_data", methods=["POST"])
def get_fund_chart_data_api():
    """获取基金图表数据（用于ECharts展示）"""
    try:
        # 获取请求参数
        data = request.json
        symbols = data.get("symbols", [])
        period = data.get("period", "12M")
        use_growth_rate = data.get("use_growth_rate", True)  # 是否使用增长率对比

        # 验证参数
        if not symbols or len(symbols) == 0:
            return jsonify({"success": False, "message": "请至少选择一个基金"}), 400

        if len(symbols) > 10:
            return (
                jsonify({"success": False, "message": "最多只能选择10个基金进行对比"}),
                400,
            )

        logger.info(
            f"请求基金图表数据，基金: {symbols}, 周期: {period}, 使用增长率: {use_growth_rate}"
        )

        # 使用fund_data_fetcher中的函数准备图表数据
        # 导入已在文件顶部完成

        chart_data = get_fund_chart_data(symbols, period, use_growth_rate)

        if chart_data and chart_data.get("series"):
            return jsonify(
                {
                    "success": True,
                    "data": chart_data,
                    "message": f"成功获取 {len(chart_data['series'])} 个基金的图表数据",
                }
            )
        else:
            return jsonify({"success": False, "message": "构建基金图表数据失败"}), 500

    except Exception as e:
        logger.error(f"获取基金图表数据失败: {str(e)}", exc_info=True)
        return (
            jsonify({"success": False, "message": f"获取基金图表数据失败: {str(e)}"}),
            500,
        )


###########################################settings##################################


@app.route("/api/settings", methods=["GET"])
def get_settings():
    """获取应用设置"""
    from .config_manager import config_manager

    settings = config_manager.get_settings()
    return jsonify(settings)


@app.route("/api/industry_page_enabled", methods=["GET"])
def get_industry_page_enabled():
    """获取行业页面启用状态"""
    from .config_manager import get_industry_page_enabled

    industry_enabled = get_industry_page_enabled()
    return jsonify({"industry_page_enabled": industry_enabled})


@app.route("/api/settings", methods=["POST"])
def update_settings():
    """更新应用设置"""
    from .config_manager import config_manager

    data = request.json
    config_manager.update_settings(data)
    return jsonify({"success": True, "message": "设置更新成功"})


@app.route("/api/notification_settings", methods=["GET"])
def get_notification_settings():
    """获取消息发送设置（从配置管理器）"""
    from .config_manager import config_manager

    # 从配置管理器获取全局通知设置
    global_notification_enabled = config_manager.get_global_notification_enabled()

    # 从配置管理器获取每只股票的通知设置
    stocks = load_stocks()
    stock_notification_enabled = {}
    for stock in stocks:
        stock_code = stock.get("code")
        notification_enabled = config_manager.get_stock_notification_enabled(stock_code)
        if stock_code:
            stock_notification_enabled[stock_code] = notification_enabled

    return jsonify(
        {
            "global_notification_enabled": global_notification_enabled,
            "stock_notification_enabled": stock_notification_enabled,
        }
    )


@app.route("/api/notification_settings", methods=["POST"])
def update_notification_settings():
    """更新消息发送设置（保存到配置管理器）"""
    from .config_manager import config_manager

    data = request.json
    global_enabled = data.get("global_notification_enabled", True)
    stock_enabled = data.get("stock_notification_enabled", {})

    # 更新配置管理器中的全局设置
    config_manager.set_global_notification_enabled(global_enabled)

    # 更新配置管理器中每只股票的设置
    for stock_code, enabled in stock_enabled.items():
        config_manager.set_stock_notification_enabled(stock_code, enabled)

    return jsonify({"success": True, "message": "消息发送设置更新成功"})


@app.route("/api/stocks/<code>/notification_enabled", methods=["PUT"])
def update_stock_notification_enabled(code):
    """更新单个股票的消息发送开关状态"""
    data = request.json
    notification_enabled = data.get("notification_enabled", True)

    # 更新到配置管理器
    from .config_manager import (
        set_stock_notification_enabled as set_stock_notif_enabled,
    )

    set_stock_notif_enabled(code, notification_enabled)

    return jsonify(
        {
            "success": True,
            "message": f"股票 {code} 消息发送开关已{'开启' if notification_enabled else '关闭'}",
        }
    )


# AI分析任务管理
@app.route("/api/trend_analysis/<code>", methods=["GET"])
def get_trend_analysis(code):
    """获取股票趋势交易分析"""
    try:

        name = request.args.get("name", "")

        analyzer = TrendTradingAnalyzer()
        result = analyzer.analyze_stock_trend(code, name)

        return jsonify(result)

    except Exception as e:
        logger.error(f"趋势交易分析股票 {code} 失败: {str(e)}")
        return (
            jsonify({"success": False, "message": f"趋势交易分析失败: {str(e)}"}),
            500,
        )


@app.route("/api/global_notification_enabled", methods=["PUT"])
def update_global_notification_enabled():
    """更新全局消息发送开关状态"""
    data = request.json
    global_enabled = data.get("global_notification_enabled", True)

    # 更新到配置管理器
    from .config_manager import (
        set_global_notification_enabled as set_global_notif_enabled,
    )

    set_global_notif_enabled(global_enabled)

    return jsonify(
        {
            "success": True,
            "message": f"全局消息发送开关已{'开启' if global_enabled else '关闭'}",
        }
    )


@app.route("/api/stocks/<code>/kline", methods=["GET"])
def get_stock_kline_data(code):
    """
    获取股票 K 线数据（用于 ECharts 图表展示）
    包含：OHLCV 数据、均线（MA5/20/60/120）、买卖信号、密集成交区
    """
    try:
        # 获取参数
        period = request.args.get("period", "365")  # 默认最近 365 天
        period = int(period)

        # 使用趋势分析器获取 K 线图表数据
        analyzer = TrendTradingAnalyzer()
        result = analyzer.get_kline_chart_data(code, "", period)

        return jsonify(result)

    except Exception as e:
        logger.error(f"获取股票 {code} K 线数据失败：{str(e)}", exc_info=True)
        return (
            jsonify({"success": False, "message": f"获取 K 线数据失败：{str(e)}"}),
            500,
        )


if __name__ == "__main__":
    # 启动预加载（在新线程中执行，避免阻塞主服务启动）
    logger.error("run with: python start_app.py ...")
    app.run(host="0.0.0.0", port=5001, debug=False)
