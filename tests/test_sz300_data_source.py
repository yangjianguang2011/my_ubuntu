#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试方案：当沪深 300 不在排名中时，使用 get_index_history 替代 get_sina_index_spot_data
"""

import sys
sys.path.insert(0, r'e:\work\code\my_ubuntu_t\stock_monitor')

from index_data_fetcher import get_index_ranking, get_index_history, get_sina_index_spot_data
from logger_config import logger
import pandas as pd

def test_sz300_data_sources():
    """测试两种数据源获取沪深 300 数据的效果"""
    
    print("=" * 80)
    print("测试方案：使用 get_index_history 替代 get_sina_index_spot_data")
    print("=" * 80)
    
    sz300_symbol = 'sz399300'
    sz300_name = '沪深 300'
    
    # 方法 1: 使用 get_sina_index_spot_data（当前方案）
    print("\n[方法 1] 使用 get_sina_index_spot_data 获取实时数据:")
    print("-" * 60)
    try:
        sina_data = get_sina_index_spot_data()
        if isinstance(sina_data, pd.DataFrame) and not sina_data.empty:
            sz300_row = sina_data[sina_data['代码'] == sz300_symbol]
            if not sz300_row.empty:
                print(f"  找到沪深 300 数据:")
                print(f"    代码：{sz300_row.iloc[0]['代码']}")
                print(f"    名称：{sz300_row.iloc[0]['名称']}")
                print(f"    最新价：{sz300_row.iloc[0]['最新价']}")
                print(f"    涨跌幅：{sz300_row.iloc[0]['涨跌幅']}%")
                print(f"    涨跌额：{sz300_row.iloc[0]['涨跌额']}")
                print(f"    成交量：{sz300_row.iloc[0]['成交量']}")
                print(f"    成交额：{sz300_row.iloc[0]['成交额']}")
                method1_success = True
            else:
                print(f"  [ERROR] 未在实时数据中找到沪深 300 ({sz300_symbol})")
                method1_success = False
        else:
            print(f"  [ERROR] 实时数据为空")
            method1_success = False
    except Exception as e:
        print(f"  [ERROR] 获取实时数据失败：{e}")
        method1_success = False
    
    # 方法 2: 使用 get_index_history（建议方案）
    print(f"\n[方法 2] 使用 get_index_history 获取历史数据:")
    print("-" * 60)
    try:
        history_data = get_index_history(sz300_symbol, period='5D')
        if history_data and len(history_data) > 0:
            latest = history_data[0]  # 获取最新一天的数据
            print(f"  找到沪深 300 数据:")
            print(f"    代码：{sz300_symbol}")
            print(f"    名称：{sz300_name}")
            print(f"    日期：{latest.get('date', 'N/A')}")
            print(f"    收盘价：{latest.get('close', 'N/A')}")
            print(f"    开盘价：{latest.get('open', 'N/A')}")
            print(f"    最高价：{latest.get('high', 'N/A')}")
            print(f"    最低价：{latest.get('low', 'N/A')}")
            print(f"    成交量：{latest.get('volume', 'N/A')}")
            print(f"    成交额：{latest.get('amount', 'N/A')}")
            
            # 检查是否有涨跌幅数据
            if 'change_pct' in latest and latest['change_pct'] is not None:
                print(f"    涨跌幅：{latest['change_pct']}%")
            if 'change_amount' in latest and latest['change_amount'] is not None:
                print(f"    涨跌额：{latest['change_amount']}")
            
            method2_success = True
        else:
            print(f"  [ERROR] 历史数据为空")
            method2_success = False
    except Exception as e:
        print(f"  [ERROR] 获取历史数据失败：{e}")
        method2_success = False
    
    # 对比两种方法
    print("\n" + "=" * 80)
    print("对比结果:")
    print("=" * 80)
    print(f"方法 1 (实时数据): {'成功' if method1_success else '失败'}")
    print(f"方法 2 (历史数据): {'成功' if method2_success else '失败'}")
    
    if method1_success and method2_success:
        print("\n[结论] 两种方法都能获取到数据，可以考虑使用 get_index_history 替代")
        print("\n优点:")
        print("  1. get_index_history 是统一的接口，代码更一致")
        print("  2. 不需要额外处理 DataFrame 转换")
        print("  3. 可以直接获取到收盘价作为 current_price")
        print("\n缺点:")
        print("  1. 历史数据可能不是实时的（有延迟）")
        print("  2. 需要计算涨跌幅（如果历史数据中没有）")
    elif method2_success and not method1_success:
        print("\n[结论] 强烈建议使用 get_index_history，因为实时数据接口失败")
    elif method1_success and not method2_success:
        print("\n[结论] 保持使用 get_sina_index_spot_data，历史数据接口失败")
    else:
        print("\n[结论] 两种方法都失败，需要检查数据源")
    
    # 测试排名数据
    print("\n" + "=" * 80)
    print("测试：检查沪深 300 是否在排名中")
    print("=" * 80)
    try:
        ranking = get_index_ranking(period_days=30)
        sz300_in_ranking = any(idx['symbol'] == sz300_symbol for idx in ranking)
        sz300_rank = next((i+1 for i, idx in enumerate(ranking) if idx['symbol'] == sz300_symbol), None)
        
        print(f"沪深 300 在排名中：{sz300_in_ranking}")
        if sz300_rank:
            print(f"沪深 300 排名：第 {sz300_rank} 名")
        
        if not sz300_in_ranking:
            print(f"\n[注意] 沪深 300 不在前{len(ranking)}名，需要额外获取数据")
    except Exception as e:
        print(f"  [ERROR] 获取排名数据失败：{e}")
    
    print("\n" + "=" * 80)

if __name__ == '__main__':
    test_sz300_data_sources()
