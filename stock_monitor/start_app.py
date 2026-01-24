#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
综合金融监控应用启动脚本
启动包含股票监控、分析师数据和行业板块的综合管理系统
"""

import sys
import threading
import time
import atexit
from web_app import app as web_app
from stock_monitor import StockMonitor
from logger_config import logger,gconfig
from datetime import datetime, timedelta

def preload_cache_data():
    """预加载常用数据到缓存"""
    from analyst_data_fetcher import get_analyst_rank_data, _fetch_analyst_stocks
    from industry_data_fetcher import get_industry_names, get_single_industry_history
    from index_data_fetcher import get_index_history
    sleep_duration = gconfig.get('industry_cache_timeout', 24 * 60 * 60) + 60  # 多等一分钟再循环
    first_run = True


    while True:
        time.sleep(5)  # 等待一段时间，确保系统初始化完成
        logger.info("开始预加载缓存数据...")

        # 获取所有分析师和行业板块的列表，用于计算平均延迟时间
        all_analysts = get_analyst_rank_data()  # 获取所有分析师列表
        all_industries = get_industry_names()   # 获取所有行业列表
        all_indexs = SELECTED_MAIN_INDEX = [
            {"symbol": "sh000510", "name": "中证A500", "interface": "sinae"},
            {"symbol": "zs000813", "name": "细分化工", "interface": "eastmoney"},
            {"symbol": "sz399971", "name": "中证传媒", "interface": "sina"}, 
            {"symbol": "sz399804", "name": "中证体育", "interface": "sina"}, 
            {"symbol": "sz399935", "name": "中证信息", "interface": "sina"}, 
            {"symbol": "sz399967", "name": "中证军工", "interface": "sina"}, 
            {"symbol": "sz399989", "name": "中证医疗", "interface": "sina"}, 
            {"symbol": "sz399933", "name": "中证医药", "interface": "sina"}, 
            {"symbol": "sz399808", "name": "中证新能", "interface": "sina"}, 
            {"symbol": "sz399932", "name": "中证消费", "interface": "sina"}, 
            {"symbol": "sz399998", "name": "中证煤炭", "interface": "sina"}, 
            {"symbol": "sh000827", "name": "中证环保", "interface": "sina"}, 
            {"symbol": "sz399997", "name": "中证白酒", "interface": "sina"}, 
            {"symbol": "sz399928", "name": "中证能源", "interface": "sina"}, 
            {"symbol": "sh000934", "name": "中证金融", "interface": "sina"}, 
            {"symbol": "sz399986", "name": "中证银行", "interface": "sina"}, 
            {"symbol": "sz399283", "name": "机器人50", "interface": "sina"},
            {"symbol": "sz399363", "name": "国证算力", "interface": "sina"}, 
            {"symbol": "sz399365", "name": "国证粮食", "interface": "sina"}, 
            {"symbol": "sz399389", "name": "国证通信", "interface": "sina"}, 
            {"symbol": "sz399395", "name": "国证有色", "interface": "sina"}, 
            {"symbol": "sz399440", "name": "国证钢铁", "interface": "sina"}, 
            {"symbol": "sz399353", "name": "国证物流", "interface": "sina"}, 
            {"symbol": "sz399397", "name": "国证文化", "interface": "sina"}, 
            {"symbol": "sz399435", "name": "国证农牧", "interface": "sina"}, 
            {"symbol": "sz980035", "name": "化肥农药", "interface": "sina"}
        ]        
        avg_delay_per_call = sleep_duration / (len(all_analysts) + len(all_industries) + len(all_indexs) + 1)
        
        current_date = datetime.now()
        end_date = current_date.strftime('%Y%m%d')
        start_date = (current_date - timedelta(days=int(30))).strftime('%Y%m%d')

        if first_run:
            avg_delay_per_call = 1
            first_run = False

        logger.info(f"分析师个数 {len(all_analysts)}, 行业个数 {len(all_industries)}, 指数个数 {len(all_indexs)} "
                   f"缓存总时长 {sleep_duration}, 平均每次调用延迟: {avg_delay_per_call:.2f}秒")

        try:
            for idx, analyst in enumerate(all_analysts):
                analyst_id = analyst.get('分析师ID', '')
                analyst_name = analyst.get('分析师名称', '')
                logger.info(f"预加载分析师详情 {analyst_name}({analyst_id}) ...")
                try:
                    analyst_stocks, _, _ = _fetch_analyst_stocks(analyst_id, analyst_name, "最新跟踪成分股")
                except Exception as e:
                    logger.error(f"预加载分析师 {analyst_name}({analyst_id}) 数据失败: {e}")
                    
                time.sleep(avg_delay_per_call)

            for idx, industry in enumerate(all_industries):
                industry_name = industry.get('板块名称', '')
                logger.info(f"预加载行业历史数据 {industry_name} ...")
                try:
                    get_single_industry_history(industry_name, start_date, end_date)
                except Exception as e:
                    logger.error(f"预加载行业 {industry_name} 数据失败: {e}")

                time.sleep(avg_delay_per_call)

            for idx, index in enumerate(all_indexs):
                symbol = index.get('symbol', '')
                iname = index.get('name')
                logger.info(f"预加载指数历史数据 {iname} ...")
                try:
                    get_index_history(symbol=symbol)
                except Exception as e:
                    logger.error(f"预加载行业 {industry_name} 数据失败: {e}")
                time.sleep(avg_delay_per_call)
        except Exception as e:
            logger.error(f"预加载数据失败: {e}")

        logger.info("缓存数据预加载完成")

        #等待缓存过期时间再重新预加载
        #time.sleep(sleep_duration)


def start_web_server():
    """启动Web服务器"""
    logger.info("启动Web管理界面...")
    try:
        web_app.run(host='0.0.0.0', port=5001, debug=False, threaded=True, use_reloader=False)
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
    
    # 导入配置管理器
    from config_manager import config_manager
    
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


if __name__ == '__main__':
    main()
