#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
综合金融监控应用启动脚本
启动包含股票监控、分析师数据和行业板块的综合管理系统
"""

import atexit
import sys
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent.resolve()
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from config import get_path, setup_logger

logger = setup_logger(__name__)
from stock_monitor.core.stock_monitor import StockMonitor
from stock_monitor.core.web_app import app as web_app


def preload_cache_data():
    """预加载常用数据到缓存"""
    try:
        from stock_monitor.core.config_manager import get_industry_page_enabled
        from stock_monitor.data_fetchers.analyst_data_fetcher import (
            _fetch_analyst_stocks,
            get_analyst_rank_data,
        )
        from stock_monitor.data_fetchers.fund_data_fetcher import (
            SELECTED_FUND_LIST,
            get_fund_daily_data,
        )
        from stock_monitor.data_fetchers.index_data_fetcher import (
            SINA_ALL_INDEX,
            get_index_daily_data,
        )
        from stock_monitor.data_fetchers.industry_data_fetcher import (
            get_industry_names,
            get_single_industry_history,
        )
    except ImportError as e:
        logger.error(f"导入数据获取模块失败: {e}")
        return

    sleep_duration = (
        int(get_path("cache", "industry_cache_timeout", 24 * 60 * 60)) + 60
    )  # 多等一分钟再循环
    first_run = True

    while True:
        time.sleep(5)  # 等待一段时间，确保系统初始化完成
        logger.info("开始预加载缓存数据...")

        try:
            # 获取所有分析师和行业板块的列表，用于计算平均延迟时间
            logger.info("获取分析师数据列表...")
            all_analysts = get_analyst_rank_data()  # 获取所有分析师列表
            logger.info("获取行业数据列表...")
            all_industries = (
                get_industry_names() if get_industry_page_enabled() else []
            )  # 获取所有行业列表
            all_indexs = SINA_ALL_INDEX
            all_funds = SELECTED_FUND_LIST

            total_items = (
                len(all_analysts)
                + len(all_industries)
                + len(all_indexs)
                + len(all_funds)
            )
            avg_delay_per_call = max(
                0.1, sleep_duration / total_items if total_items > 0 else 0.1
            )

            current_date = datetime.now()
            end_date = current_date.strftime("%Y%m%d")
            start_date = (current_date - timedelta(days=int(30))).strftime("%Y%m%d")

            if first_run:
                avg_delay_per_call = 5  # 第一次运行时使用较短的延迟
                first_run = False

            logger.info(
                f"分析师个数 {len(all_analysts)}, 行业个数 {len(all_industries)}, 指数个数 {len(all_indexs)}, 基金个数 {len(all_funds)}, "
                f"缓存总时长 {sleep_duration}, 平均每次调用延迟: {avg_delay_per_call:.2f}秒"
            )

            # 预加载基金数据
            logger.info(f"开始预加载 {len(all_funds)} 个基金数据...")
            for idx, fund in enumerate(all_funds):
                fund_code = str(fund.get("基金代码", "")).zfill(6)  # 确保基金代码为6位
                fund_name = fund.get("基金简称", "")
                logger.info(
                    f"[{idx+1}/{len(all_funds)}] 预加载基金历史数据 {fund_name}({fund_code}) ..."
                )
                try:
                    get_fund_daily_data(fund_code, apply_delay=False)
                    logger.debug(f"基金 {fund_name}({fund_code}) 数据预加载成功")
                except Exception as e:
                    logger.error(
                        f"预加载基金 {fund_name}({fund_code}) 数据失败: {e}",
                        exc_info=True,
                    )
                time.sleep(avg_delay_per_call)

            # 预加载指数数据
            logger.info(f"开始预加载 {len(all_indexs)} 个指数数据...")
            for idx, index in enumerate(all_indexs):
                symbol = index.get("symbol", "")
                iname = index.get("name")
                logger.info(
                    f"[{idx+1}/{len(all_indexs)}] 预加载指数历史数据 {iname} ..."
                )
                try:
                    get_index_daily_data(symbol=symbol)
                    logger.debug(f"指数 {iname} 数据预加载成功")
                except Exception as e:
                    logger.error(f"预加载指数 {iname} 数据失败: {e}", exc_info=True)
                time.sleep(avg_delay_per_call)

            # 预加载分析师数据
            logger.info(f"开始预加载 {len(all_analysts)} 个分析师数据...")
            for idx, analyst in enumerate(all_analysts):
                analyst_id = analyst.get("分析师ID", "")
                analyst_name = analyst.get("分析师名称", "")
                logger.info(
                    f"[{idx+1}/{len(all_analysts)}] 预加载分析师详情 {analyst_name}({analyst_id}) ..."
                )
                try:
                    analyst_stocks, _, _ = _fetch_analyst_stocks(
                        analyst_id, analyst_name, "最新跟踪成分股"
                    )
                    logger.debug(f"分析师 {analyst_name}({analyst_id}) 数据预加载成功")
                except Exception as e:
                    logger.error(
                        f"预加载分析师 {analyst_name}({analyst_id}) 数据失败: {e}",
                        exc_info=True,
                    )
                time.sleep(avg_delay_per_call)

            # 预加载行业数据
            logger.info(f"开始预加载 {len(all_industries)} 个行业数据...")
            for idx, industry in enumerate(all_industries):
                industry_name = industry.get("板块名称", "")
                logger.info(
                    f"[{idx+1}/{len(all_industries)}] 跳过预加载行业历史数据 {industry_name} ..."
                )
                try:
                    get_single_industry_history(industry_name, start_date, end_date)
                    logger.debug(f"行业 {industry_name} 数据预加载成功")
                except Exception as e:
                    logger.error(
                        f"预加载行业 {industry_name} 数据失败: {e}", exc_info=True
                    )
                time.sleep(avg_delay_per_call)

            logger.info("所有缓存数据预加载完成")

        except Exception as e:
            logger.error(f"预加载数据过程中发生严重错误: {e}", exc_info=True)

        # 等待缓存过期时间再重新预加载
        logger.info(f"等待 {avg_delay_per_call} 秒后重新预加载...")
        time.sleep(avg_delay_per_call)


def start_web_server():
    """启动Web服务器"""
    logger.info("启动Web管理界面...")
    try:
        web_app.run(
            host="0.0.0.0", port=5001, debug=False, threaded=True, use_reloader=False
        )
    except Exception as e:
        logger.error(f"Web服务器启动失败: {e}")
    finally:
        logger.info("Web服务器启动完成")


def start_stock_monitor():
    """启动股票监控程序"""
    logger.info("启动股票监控程序...")
    try:
        monitor = StockMonitor()
        if monitor.stocks:
            monitor.start_monitoring()
        else:
            logger.warning("没有配置监控股票，监控程序退出")
    except Exception as e:
        logger.error(f"股票监控程序出错: {e}")
    finally:
        logger.info("股票监控程序初始化完成")


def main():

    logger.info("正在启动股票监控管理系统...")

    # 打印配置目录信息
    try:
        from config import get_paths

        paths = get_paths()
        logger.info(f"配置路径信息: {paths}")
    except Exception as e:
        logger.error(f"获取配置路径失败: {e}")

    # 导入配置管理器
    from stock_monitor.core.config_manager import config_manager

    # 定义清理函数
    def cleanup():
        """应用关闭时清理资源"""
        logger.info("正在关闭应用，同步配置管理器...")
        config_manager.shutdown()

    # 注册清理函数
    atexit.register(cleanup)

    # 创建线程运行Web服务器
    web_thread = threading.Thread(target=start_web_server, daemon=True)
    web_thread.start()
    time.sleep(1)

    # 创建线程运行股票监控
    monitor_thread = threading.Thread(target=start_stock_monitor, daemon=True)
    monitor_thread.start()
    time.sleep(1)

    # 行业数据、分析师数据预取线程
    preload_thread = threading.Thread(target=preload_cache_data, daemon=True)
    preload_thread.start()

    try:
        # 等待主线程，保持程序运行
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("\n收到终止信号，正在关闭程序...")
        sys.exit(0)
    finally:
        logger.info("主程序执行结束")


if __name__ == "__main__":
    main()
