#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
分析师历史数据功能测试程序
用于测试分析师历史数据的自动保存和查询功能
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from analyst_data_fetcher import get_combined_analyst_data, get_stock_analyst_history_tracking
from cache_with_database import get_module_long_term_data
from logger_config import logger
import json
from datetime import datetime, date

def test_analyst_history_functionality():
    """测试分析师历史数据功能"""
    print("=== 分析师历史数据功能测试 ===\n")
    
    try:
        # 1. 测试获取组合分析师数据（这会触发历史数据保存）
        print("1. 测试获取组合分析师数据...")
        result = get_combined_analyst_data(top_analysts=10, top_stocks=20, period="3个月")
        
        if result and 'top_focus_stocks' in result:
            print(f"   成功获取 {len(result['top_focus_stocks'])} 只重点关注股票")
            if result['top_focus_stocks']:
                print(f"   示例数据: {result['top_focus_stocks'][0]['stock_code']} - 关注数量: {result['top_focus_stocks'][0]['analyst_count']}")
            else:
                print("   注意: 没有获取到重点关注股票数据")
        else:
            print("   获取数据失败")
            return False
            
        # 2. 测试获取历史数据
        print("\n2. 测试获取历史数据...")
        if result['top_focus_stocks']:
            # 获取第一条重点关注股票的历史数据
            test_stock = result['top_focus_stocks'][0]
            stock_code = test_stock['stock_code']
            print(f"   测试股票: {stock_code}")
            
            # 获取历史数据
            history_data = get_stock_analyst_history_tracking(stock_code, days=30)
            if history_data:
                print(f"   成功获取 {len(history_data['dates'])} 天的历史数据")
                print(f"   日期范围: {history_data['dates'][0]} 到 {history_data['dates'][-1] if history_data['dates'] else 'N/A'}")
                print(f"   关注数量: {history_data['analyst_counts']}")
            else:
                print("   未获取到历史数据")
        else:
            print("   没有可测试的重点股票")
            
        # 3. 测试数据库中的长期存储数据
        print("\n3. 测试数据库中的长期存储数据...")
        long_term_data = get_module_long_term_data("analyst")
        if long_term_data:
            print(f"   数据库中共有 {len(long_term_data)} 条分析师历史数据")
            # 显示前几条数据
            for i, item in enumerate(long_term_data[:3]):
                data = item['data']
                print(f"   数据 {i+1}: {data.get('stock_code', 'N/A')} - {data.get('date', 'N/A')} - {data.get('analyst_count', 'N/A')}")
        else:
            print("   数据库中暂无分析师历史数据")
            
        print("\n=== 测试完成 ===")
        return True
        
    except Exception as e:
        logger.error(f"测试过程中出错: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def test_specific_stock_history():
    """测试特定股票的历史数据"""
    print("\n=== 特定股票历史数据测试 ===\n")
    
    try:
        # 测试一个具体的股票代码
        test_stock_code = "SZ000408"  # 举例测试股票代码
        print(f"测试股票: {test_stock_code}")
        
        # 获取历史数据
        history_data = get_stock_analyst_history_tracking(test_stock_code, days=30)
        if history_data:
            print(f"   成功获取 {len(history_data['dates'])} 天的历史数据")
            print(f"   日期: {history_data['dates']}")
            print(f"   关注数量: {history_data['analyst_counts']}")
        else:
            print("   未获取到该股票的历史数据")
            
        # 检查数据库中是否有该股票的数据
        long_term_data = get_module_long_term_data("analyst")
        if long_term_data:
            stock_history = [item for item in long_term_data if item['data'].get('stock_code') == test_stock_code]
            print(f"   数据库中该股票有 {len(stock_history)} 条历史记录")
            for item in stock_history[:2]:  # 显示前两条
                data = item['data']
                print(f"   - {data.get('date', 'N/A')}: {data.get('analyst_count', 'N/A')} 个分析师关注")
        else:
            print("   数据库中暂无分析师历史数据")
            
        print("\n=== 特定股票测试完成 ===")
        return True
        
    except Exception as e:
        logger.error(f"特定股票测试出错: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("开始测试分析师历史数据功能...")
    
    # 运行主要测试
    success1 = test_analyst_history_functionality()
    
    # 运行特定股票测试
    success2 = test_specific_stock_history()
    
    if success1 and success2:
        print("\n🎉 所有测试成功完成！")
    else:
        print("\n❌ 部分测试失败，请检查日志")
