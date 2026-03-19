"""
测试配置变更通知机制
"""
import time
import threading
from config_manager import config_manager
from stock_monitor import StockMonitor

class TestObserver:
    """测试观察者，用来验证通知机制"""
    def __init__(self):
        self.notifications = []
        self.lock = threading.Lock()
    
    def on_config_change(self, change_type, data):
        """接收配置变更通知"""
        with self.lock:
            self.notifications.append({
                'timestamp': time.time(),
                'change_type': change_type,
                'data': data
            })
        print(f"收到配置变更通知: {change_type}, 数据: {data}")

def test_observer_mechanism():
    """测试观察者机制"""
    print("开始测试配置变更通知机制...")
    
    # 创建测试观察者
    test_observer = TestObserver()
    
    # 注册测试观察者
    config_manager.add_observer(test_observer)
    
    # 创建StockMonitor也会自动注册为观察者
    stock_monitor = StockMonitor()
    
    print("当前注册的观察者数量:", len(config_manager.observers))
    
    # 测试添加股票
    print("\n--- 测试添加股票 ---")
    test_stock = {
        'name': '测试股票',
        'code': 'TEST001',
        'low_alert_price': 10.0,
        'high_alert_price': 20.0,
        'limit_alert': True,
        'key_price_alerts': [],
        'change_pct_alerts': [{'pct': 5, 'type': 'warning'}],
        'notification_enabled': True
    }
    
    config_manager.add_stock(test_stock)
    time.sleep(0.1)  # 等待通知处理
    
    # 测试更新股票
    print("\n--- 测试更新股票 ---")
    config_manager.update_stock('TEST001', {'low_alert_price': 8.0})
    time.sleep(0.1)  # 等待通知处理
    
    # 测试删除股票
    print("\n--- 测试删除股票 ---")
    config_manager.delete_stock('TEST001')
    time.sleep(0.1)  # 等待通知处理
    
    # 测试更新设置
    print("\n--- 测试更新设置 ---")
    config_manager.update_settings({'check_interval': 600})
    time.sleep(0.1)  # 等待通知处理
    
    # 输出收集到的通知
    print(f"\n总共收到 {len(test_observer.notifications)} 个通知:")
    for i, note in enumerate(test_observer.notifications):
        print(f"  {i+1}. 类型: {note['change_type']}, 数据: {note['data']}")
    
    # 检查stock_monitor是否也收到了通知
    print(f"\nStockMonitor内部股票数量: {len(stock_monitor.stocks)}")
    
    # 清理 - 移除测试观察者
    config_manager.remove_observer(test_observer)
    
    print("\n配置变更通知机制测试完成!")

if __name__ == "__main__":
    test_observer_mechanism()
