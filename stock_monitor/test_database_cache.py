"""
数据库缓存测试用例
测试使用内存和SQLite数据库的缓存功能
"""

import os
import json
import tempfile
import threading
import time
from datetime import datetime, timedelta
from cache_with_database import get_cached_data, set_cache_data, get_industry_cached_data, set_industry_cache_data
from cache_with_database import SQLiteCache
import unittest


class TestDatabaseCache(unittest.TestCase):
    """数据库缓存测试类"""
    
    def setUp(self):
        """测试前准备"""
        # 创建临时数据库文件用于测试
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        self.temp_db.close()
        
        # 使用临时数据库
        from cache_with_database import cache_system
        # 重新初始化cache_system使用临时数据库
        import importlib
        import cache_with_database
        # 重新加载模块以使用临时数据库
        cache_with_database.cache_system = SQLiteCache(db_path=self.temp_db.name)
        
        self.test_key = "test_stock_data"
        self.test_data = {
            "price": 100.5,
            "change_pct": 2.5,
            "volume": 1000000,
            "timestamp": datetime.now().isoformat()
        }
        
        self.industry_key = "test_industry_data"
        self.industry_data = {
            "name": "科技行业",
            "change_pct": 3.2,
            "stocks_count": 50,
            "timestamp": datetime.now().isoformat()
        }

    def tearDown(self):
        """测试后清理"""
        # 重新获取cache_system并关闭数据库连接
        from cache_with_database import cache_system
        # 关闭数据库连接
        import sqlite3
        # 由于SQLiteCache使用了上下文管理器，这里不需要显式关闭
        # 删除临时数据库文件
        try:
            if os.path.exists(self.temp_db.name):
                os.unlink(self.temp_db.name)
        except PermissionError:
            # 如果无法删除文件，跳过（在Windows上常见）
            pass

    def test_basic_cache_operations(self):
        """测试基本缓存操作"""
        # 测试设置缓存
        set_cache_data(self.test_key, self.test_data)
        
        # 测试获取缓存
        retrieved_data = get_cached_data(self.test_key)
        self.assertIsNotNone(retrieved_data)
        self.assertEqual(retrieved_data['price'], 100.5)
        self.assertEqual(retrieved_data['change_pct'], 2.5)
        self.assertEqual(retrieved_data['volume'], 1000000)

    def test_industry_cache_operations(self):
        """测试行业数据缓存操作"""
        # 测试设置行业缓存
        set_industry_cache_data(self.industry_key, self.industry_data)
        
        # 测试获取行业缓存
        retrieved_data = get_industry_cached_data(self.industry_key)
        self.assertIsNotNone(retrieved_data)
        self.assertEqual(retrieved_data['name'], "科技行业")
        self.assertEqual(retrieved_data['change_pct'], 3.2)
        self.assertEqual(retrieved_data['stocks_count'], 50)

    def test_cache_expiration(self):
        """测试缓存过期功能"""
        # 设置一个短的过期时间
        short_duration = 1  # 1秒后过期
        
        set_cache_data(self.test_key, self.test_data)
        
        # 立即获取应该能获取到数据
        data = get_cached_data(self.test_key)
        self.assertIsNotNone(data)
        
        # 等待超过过期时间
        time.sleep(2)
        
        # 应该获取不到数据（已过期）
        expired_data = get_cached_data(self.test_key, cache_duration=short_duration)
        self.assertIsNone(expired_data)

    def test_different_cache_durations(self):
        """测试不同的缓存时长"""
        # 测试股票数据默认缓存时长
        set_cache_data(self.test_key, self.test_data)
        data = get_cached_data(self.test_key)
        self.assertIsNotNone(data)
        
        # 测试行业数据默认缓存时长
        set_industry_cache_data(self.industry_key, self.industry_data)
        data = get_industry_cached_data(self.industry_key)
        self.assertIsNotNone(data)

    def test_cache_with_custom_duration(self):
        """测试自定义缓存时长"""
        custom_duration = 5  # 5秒
        
        set_cache_data(self.test_key, self.test_data)
        data = get_cached_data(self.test_key, cache_duration=custom_duration)
        self.assertIsNotNone(data)

    def test_thread_safety(self):
        """测试线程安全性"""
        results = []
        
        def cache_operation(thread_id):
            key = f"thread_test_{thread_id}"
            data = {"thread_id": thread_id, "value": thread_id * 10}
            
            # 设置缓存
            set_cache_data(key, data)
            
            # 获取缓存
            retrieved = get_cached_data(key)
            results.append((thread_id, retrieved))
        
        # 创建多个线程同时操作缓存
        threads = []
        for i in range(5):
            t = threading.Thread(target=cache_operation, args=(i,))
            threads.append(t)
            t.start()
        
        # 等待所有线程完成
        for t in threads:
            t.join()
        
        # 验证所有线程的操作都成功
        self.assertEqual(len(results), 5)
        for thread_id, data in results:
            self.assertIsNotNone(data)
            self.assertEqual(data['thread_id'], thread_id)
            self.assertEqual(data['value'], thread_id * 10)

    def test_cache_update(self):
        """测试缓存更新"""
        # 初始数据
        initial_data = {"value": 10}
        set_cache_data(self.test_key, initial_data)
        
        retrieved = get_cached_data(self.test_key)
        self.assertEqual(retrieved['value'], 10)
        
        # 更新数据
        updated_data = {"value": 20}
        set_cache_data(self.test_key, updated_data)
        
        retrieved = get_cached_data(self.test_key)
        self.assertEqual(retrieved['value'], 20)

    def test_nonexistent_key(self):
        """测试不存在的键"""
        nonexistent_data = get_cached_data("nonexistent_key")
        self.assertIsNone(nonexistent_data)
        
        nonexistent_data = get_industry_cached_data("nonexistent_industry_key")
        self.assertIsNone(nonexistent_data)

    def test_large_data_cache(self):
        """测试大容量数据缓存"""
        # 创建较大的数据
        large_data = {
            "data": list(range(1000)),  # 包含1000个整数的列表
            "metadata": {
                "size": 1000,
                "type": "large_dataset",
                "timestamp": datetime.now().isoformat()
            }
        }
        
        set_cache_data("large_data_test", large_data)
        retrieved = get_cached_data("large_data_test")
        
        self.assertIsNotNone(retrieved)
        self.assertEqual(len(retrieved['data']), 1000)
        self.assertEqual(retrieved['metadata']['size'], 1000)

    def test_special_characters_in_keys(self):
        """测试包含特殊字符的键"""
        special_key = "test_key_with_特殊字符_123!@#"
        special_data = {"value": "test_with_special_chars"}
        
        set_cache_data(special_key, special_data)
        retrieved = get_cached_data(special_key)
        
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved['value'], "test_with_special_chars")

    def test_json_serializable_data(self):
        """测试各种JSON可序列化数据"""
        test_cases = [
            {"simple_dict": {"key": "value"}},
            {"number_data": {"int": 123, "float": 123.45}},
            {"list_data": {"items": [1, 2, 3, 4, 5]}},
            {"nested_data": {"level1": {"level2": {"level3": "deep_value"}}}},
            {"boolean_data": {"true_val": True, "false_val": False}},
            {"null_data": {"null_val": None}}
        ]
        
        for i, test_data in enumerate(test_cases):
            key = f"json_test_{i}"
            set_cache_data(key, test_data)
            retrieved = get_cached_data(key)
            self.assertIsNotNone(retrieved)
            self.assertEqual(retrieved, test_data)


def run_performance_test():
    """性能测试"""
    print("开始性能测试...")
    
    # 准备测试数据
    test_data = {"value": "performance_test_data", "timestamp": datetime.now().isoformat()}
    
    # 测试写入性能
    start_time = time.time()
    for i in range(100):
        set_cache_data(f"perf_test_key_{i}", test_data)
    write_time = time.time() - start_time
    print(f"写入100条数据耗时: {write_time:.4f}秒")
    
    # 测试读取性能
    start_time = time.time()
    for i in range(100):
        get_cached_data(f"perf_test_key_{i}")
    read_time = time.time() - start_time
    print(f"读取100条数据耗时: {read_time:.4f}秒")
    
    print(f"总操作时间: {write_time + read_time:.4f}秒")


if __name__ == "__main__":
    # 运行单元测试
    print("运行数据库缓存测试...")
    unittest.main(argv=[''], exit=False, verbosity=2)
    
    # 运行性能测试
    run_performance_test()
    
    print("所有测试完成！")
