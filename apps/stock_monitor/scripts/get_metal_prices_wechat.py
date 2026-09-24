#!/usr/bin/env python3
"""获取金属/碳酸锂价格并推送到 **企业微信**（实现见 `_metal_prices.py`）。"""
from _bootstrap import ensure_project_root

ensure_project_root()

from _metal_prices import *  # noqa: F401,F403  公共抓取与消息构建
import _metal_prices as mp


def main():
    import os
    # 切换到脚本所在目录，确保文件保存到正确位置
    script_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(script_dir)
    
    print("🟡 正在获取多种金属、加密货币及碳酸锂价格...")
    
    # 获取所有金属价格数据
    metals_data = get_all_metals_prices()
    
    # 获取碳酸锂价格数据
    lithium_data = get_lithium_carbonate_price()
    
    # 加载历史价格数据
    historical_records = load_historical_prices()
    
    # 计算每日和每周涨幅
    changes = calculate_daily_weekly_changes(historical_records, metals_data, lithium_data)
    
    # 保存今日价格数据
    save_daily_prices(metals_data, lithium_data)
    
    # 格式化综合消息
    message = format_combined_message(metals_data, lithium_data, changes)
    
    print("\n" + "="*60)
    print("综合价格报告:")
    print(message)
    print("="*60)
    
    # 发送消息到企业微信（消息服务）
    success = send_to_wechat(message)

    if success:
        print("\n✅ 综合价格信息已成功发送到企业微信")
    else:
        print("\n⚠️  发送到企业微信失败")
    
    print(f"\n✅ 任务完成")




if __name__ == "__main__":
    main()
