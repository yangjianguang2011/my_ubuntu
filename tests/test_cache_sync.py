#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试通知开关配置管理器的后台同步功能
"""
import time
import json
import os
from config_manager import set_global_notification_enabled, set_stock_notification_enabled
from logger_config import gconfig

def test_cache_sync():
    """测试配置管理器同步功能"""
    print("开始测试通知开关配置管理器的后台同步功能...")
    
    # 设置一些值到配置管理器
    print("\n1. 设置配置值:")
    set_global_notification_enabled(False)
    set_stock_notification_enabled("00001", False)
    set_stock_notification_enabled("600000", True)
    print("   已设置全局开关为False，股票00001为False，股票600000为True")
    
    # 等待后台同步（我们手动同步，因为实际后台同步是60秒一次）
    print("\n2. 等待后台同步...")
    print("   注意：实际后台同步是每60秒一次，这里为了测试，我们直接检查文件内容")
    
    # 检查配置文件内容
    print("\n3. 检查配置文件内容:")
    settings_file = gconfig.get('settings_file', './settings.json')
    stocks_file = gconfig.get('stocks_file', './stocks.json')
    
    print(f"   Settings文件: {settings_file}")
    print(f"   Stocks文件: {stocks_file}")
    
    # 由于后台同步需要60秒，我们手动触发一次同步
    from config_manager import config_manager
    print("\n4. 手动触发同步...")
    config_manager._sync_to_file()
    print("   同步完成")
    
    # 检查文件内容
    if os.path.exists(settings_file):
        with open(settings_file, 'r', encoding='utf-8') as f:
            settings = json.load(f)
        print(f"   Settings.json global_notification_enabled: {settings.get('global_notification_enabled')}")
    
    if os.path.exists(stocks_file):
        with open(stocks_file, 'r', encoding='utf-8') as f:
            stocks = json.load(f)
        print(f"   Stocks.json 有 {len(stocks)} 只股票")
        for stock in stocks:
            code = stock.get('code')
            enabled = stock.get('notification_enabled', True)
            if code in ['000001', '600000']:
                print(f"   股票{code} notification_enabled: {enabled}")
    
    print("\n5. 测试配置管理器关闭功能...")
    config_manager.shutdown()
    print("   配置管理器已关闭，剩余变更已同步")
    
    print("\n通知开关配置管理器后台同步功能测试完成!")

if __name__ == "__main__":
    test_cache_sync()
