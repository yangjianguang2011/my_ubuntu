"""
统一配置管理器
整合系统设置、股票配置和通知开关的管理
"""

import json
import os
import sqlite3
import threading
import time
from datetime import datetime

from config import get_path, setup_logger

logger = setup_logger(__name__)


class ConfigManager:
    def __init__(self):
        # 数据库路径
        db_dir = get_path(
            "stock_monitor", "database_dir", "/data/stock_monitor_data/database"
        )
        os.makedirs(db_dir, exist_ok=True)
        self.db_path = os.path.join(db_dir, "config.db")
        logger.info(f"配置管理数据库路径: {self.db_path}")

        # 线程锁
        self.lock = threading.Lock()

        # 变更队列，用于后台同步
        self.pending_changes = []
        self.pending_changes_lock = threading.Lock()

        # 观察者列表，用于通知配置变更
        self.observers = []

        # 初始化数据库
        self._init_db()

        # 从配置文件加载初始状态
        self._load_from_file()

        # 启动后台同步线程
        self.sync_thread_running = True
        self.sync_thread = threading.Thread(target=self._sync_to_file_loop, daemon=True)
        self.sync_thread.start()

        logger.info("统一配置管理系统初始化完成")

    def add_observer(self, observer):
        """添加配置变更观察者"""
        if observer not in self.observers:
            self.observers.append(observer)

    def remove_observer(self, observer):
        """移除配置变更观察者"""
        if observer in self.observers:
            self.observers.remove(observer)

    def notify_observers(self, change_type, data):
        """通知所有观察者配置变更"""
        for observer in self.observers:
            try:
                observer.on_config_change(change_type, data)
            except Exception as e:
                logger.error(f"通知观察者时出错: {e}")

    def _init_db(self):
        """初始化数据库表"""
        try:
            with self.lock:  # 添加锁保护
                with sqlite3.connect(self.db_path) as conn:
                    cursor = conn.cursor()

                    # 创建系统设置表
                    cursor.execute(
                        """
                        CREATE TABLE IF NOT EXISTS system_settings (
                            id INTEGER PRIMARY KEY,
                            setting_key TEXT NOT NULL,
                            setting_value TEXT NOT NULL,
                            description TEXT,
                            last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            UNIQUE(setting_key)
                        )
                    """
                    )

                    # 创建股票配置表
                    cursor.execute(
                        """
                        CREATE TABLE IF NOT EXISTS stock_config (
                            id INTEGER PRIMARY KEY,
                            stock_code TEXT NOT NULL,
                            config_key TEXT NOT NULL,
                            config_value TEXT NOT NULL,
                            last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            UNIQUE(stock_code, config_key)
                        )
                    """
                    )

                    # 创建索引
                    cursor.execute(
                        "CREATE INDEX IF NOT EXISTS idx_setting_key ON system_settings(setting_key)"
                    )
                    cursor.execute(
                        "CREATE INDEX IF NOT EXISTS idx_stock_code ON stock_config(stock_code)"
                    )
                    cursor.execute(
                        "CREATE INDEX IF NOT EXISTS idx_config_key ON stock_config(config_key)"
                    )

                    conn.commit()
                    logger.info(f"配置管理数据库初始化完成: {self.db_path}")
        except Exception as e:
            logger.error(f"初始化配置管理数据库失败: {e}")
            raise

    def _load_from_file(self):
        """从配置文件加载初始状态到数据库"""
        try:
            # 加载系统设置
            settings_file = get_path(
                "stock_monitor", "settings_file", "./settings.json"
            )
            if os.path.exists(settings_file):
                logger.info(f"从配置文件{settings_file}加载系统设置...")
                with open(settings_file, "r", encoding="utf-8") as f:
                    settings = json.load(f)

                for key, value in settings.items():
                    self._set_system_setting_db(key, value)

            # 加载股票配置
            stocks_file = get_path("stock_monitor", "stocks_file", "./stocks.json")
            if os.path.exists(stocks_file):
                logger.info(f"从配置文件{stocks_file}加载股票配置...")
                with open(stocks_file, "r", encoding="utf-8") as f:
                    stocks = json.load(f)

                for stock in stocks:
                    self._save_stock_to_db(stock)

        except Exception as e:
            logger.error(f"从配置文件加载配置失败: {e}")

    def _set_system_setting_db(self, key, value):
        """直接写入系统设置到数据库（内部方法）"""
        with self.lock:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    INSERT OR REPLACE INTO system_settings
                    (setting_key, setting_value, last_updated)
                    VALUES (?, ?, ?)
                """,
                    (key, json.dumps(value), datetime.now().isoformat()),
                )
                conn.commit()

    def _save_stock_to_db(self, stock):
        """将股票配置保存到数据库"""
        with self.lock:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                # 保存股票的每个配置项
                for key, value in stock.items():
                    cursor.execute(
                        """
                        INSERT OR REPLACE INTO stock_config
                        (stock_code, config_key, config_value, last_updated)
                        VALUES (?, ?, ?, ?)
                    """,
                        (
                            stock["code"],
                            key,
                            json.dumps(value),
                            datetime.now().isoformat(),
                        ),
                    )

                conn.commit()

    def get_settings(self):
        """获取所有系统设置"""
        with self.lock:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT setting_key, setting_value FROM system_settings")
                rows = cursor.fetchall()

                settings = {}
                for key, value in rows:
                    try:
                        settings[key] = json.loads(value)
                    except json.JSONDecodeError:
                        settings[key] = value  # 如果不是JSON格式，直接返回原值

                return settings

    def update_settings(self, updates):
        """更新系统设置"""
        with self.lock:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                for key, value in updates.items():
                    cursor.execute(
                        """
                        INSERT OR REPLACE INTO system_settings
                        (setting_key, setting_value, last_updated)
                        VALUES (?, ?, ?)
                    """,
                        (key, json.dumps(value), datetime.now().isoformat()),
                    )

                conn.commit()

        # 记录变更，用于后台同步
        with self.pending_changes_lock:
            self.pending_changes.append(
                ("system_settings", updates, datetime.now().isoformat())
            )

        # 通知观察者系统设置变更
        self.notify_observers("settings_update", updates)

    def get_check_interval(self):
        """获取检查间隔"""
        settings = self.get_settings()
        return settings.get("check_interval", 180)  # 默认3分钟

    def set_check_interval(self, interval):
        """设置检查间隔"""
        self.update_settings({"check_interval": interval})

    def get_market_times(self):
        """获取开市时间设置"""
        settings = self.get_settings()
        return {
            "market_open_start": settings.get("market_open_start", "09:30"),
            "market_open_end": settings.get("market_open_end", "16:00"),
        }

    def set_market_times(self, open_time, close_time):
        """设置开市时间"""
        self.update_settings(
            {"market_open_start": open_time, "market_open_end": close_time}
        )

    def get_global_notification_enabled(self):
        """获取全局通知开关状态"""
        settings = self.get_settings()
        return settings.get("global_notification_enabled", True)

    def set_global_notification_enabled(self, enabled):
        """设置全局通知开关状态"""
        self.update_settings({"global_notification_enabled": enabled})

    def get_all_stocks(self):
        """获取所有股票配置"""
        with self.lock:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    SELECT stock_code, config_key, config_value
                    FROM stock_config
                    ORDER BY stock_code, config_key
                """
                )
                rows = cursor.fetchall()

                # 按股票代码分组
                stocks_dict = {}
                for code, key, value in rows:
                    if code not in stocks_dict:
                        stocks_dict[code] = {"code": code}

                    try:
                        stocks_dict[code][key] = json.loads(value)
                    except json.JSONDecodeError:
                        stocks_dict[code][key] = value  # 如果不是JSON格式，直接返回原值

                return list(stocks_dict.values())

    def get_stock_by_code(self, code):
        """根据代码获取单个股票"""
        with self.lock:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    SELECT config_key, config_value
                    FROM stock_config
                    WHERE stock_code = ?
                """,
                    (code,),
                )
                rows = cursor.fetchall()

                if not rows:
                    return None

                stock = {"code": code}
                for key, value in rows:
                    try:
                        stock[key] = json.loads(value)
                    except json.JSONDecodeError:
                        stock[key] = value  # 如果不是JSON格式，直接返回原值

                return stock

    def add_stock(self, stock_info):
        """添加股票"""
        self._save_stock_to_db(stock_info)

        # 记录变更，用于后台同步
        with self.pending_changes_lock:
            self.pending_changes.append(
                ("add_stock", stock_info, datetime.now().isoformat())
            )

        # 通知观察者股票添加
        self.notify_observers("stock_add", stock_info)

    def update_stock(self, code, updates):
        """更新股票"""
        # 先获取现有股票信息
        existing_stock = self.get_stock_by_code(code)
        if existing_stock:
            # 合并更新
            updated_stock = {**existing_stock, **updates}
            self._save_stock_to_db(updated_stock)
        else:
            # 如果股票不存在，使用提供的信息创建新股票
            updated_stock = {**updates, "code": code}
            self._save_stock_to_db(updated_stock)

        # 记录变更，用于后台同步
        with self.pending_changes_lock:
            self.pending_changes.append(
                (
                    "update_stock",
                    {"code": code, "updates": updates},
                    datetime.now().isoformat(),
                )
            )

        # 通知观察者股票更新
        self.notify_observers("stock_update", {"code": code, "updates": updates})

    def delete_stock(self, code):
        """删除股票"""
        with self.lock:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM stock_config WHERE stock_code = ?", (code,))
                conn.commit()

        # 记录变更，用于后台同步
        with self.pending_changes_lock:
            self.pending_changes.append(
                ("delete_stock", {"code": code}, datetime.now().isoformat())
            )

        # 通知观察者股票删除
        self.notify_observers("stock_delete", {"code": code})

    def get_stock_notification_enabled(self, stock_code):
        """获取个股通知开关状态"""
        stock = self.get_stock_by_code(stock_code)
        if stock and "notification_enabled" in stock:
            return stock["notification_enabled"]
        return True  # 默认启用

    def set_stock_notification_enabled(self, stock_code, enabled):
        """设置个股通知开关状态"""
        self.update_stock(stock_code, {"notification_enabled": enabled})

    def _sync_to_file_loop(self):
        """后台同步线程"""
        while self.sync_thread_running:
            try:
                time.sleep(60)  # 每60秒同步一次
                self._sync_to_file()
            except Exception as e:
                logger.error(f"后台同步线程出错: {e}")

    def _sync_to_file(self):
        """将数据库中的变更同步到文件"""
        with self.pending_changes_lock:
            if not self.pending_changes:
                return

            changes_to_process = self.pending_changes[:]
            self.pending_changes.clear()
            logger.debug(f"处理 {len(changes_to_process)} 个待同步的变更")

        if not changes_to_process:
            return

        # 按类型分组处理变更
        system_settings_updates = {}
        stocks_to_update = {}
        stocks_to_delete = set()

        for change_type, data, timestamp in changes_to_process:
            if change_type == "system_settings":
                system_settings_updates.update(data)
            elif change_type == "add_stock":
                stocks_to_update[data["code"]] = data
            elif change_type == "update_stock":
                code = data["code"]
                if code not in stocks_to_update:
                    existing_stock = self.get_stock_by_code(code)
                    if existing_stock:
                        stocks_to_update[code] = existing_stock
                    else:
                        stocks_to_update[code] = {"code": code}
                stocks_to_update[code].update(data["updates"])
            elif change_type == "delete_stock":
                stocks_to_delete.add(data["code"])

        logger.info(
            f"系统设置更新: {len(system_settings_updates)}, 股票更新: {len(stocks_to_update)}, 股票删除: {len(stocks_to_delete)}"
        )

        # 同步系统设置
        if system_settings_updates:
            self._write_system_settings_to_file(system_settings_updates)
        # 同步股票配置
        if stocks_to_update or stocks_to_delete:
            self._write_stocks_to_file(stocks_to_update, stocks_to_delete)

    def _write_system_settings_to_file(self, updates):
        """将系统设置写入settings.json"""
        try:
            settings_file = get_path(
                "stock_monitor", "settings_file", "./settings.json"
            )

            # 读取现有设置
            if os.path.exists(settings_file):
                with open(settings_file, "r", encoding="utf-8") as f:
                    settings = json.load(f)
            else:
                settings = {}

            # 更新设置
            settings.update(updates)

            # 写回文件
            with open(settings_file, "w", encoding="utf-8") as f:
                json.dump(settings, f, ensure_ascii=False, indent=2)

            logger.info(f"系统设置已同步到文件，更新了{len(updates)}项设置")
        except Exception as e:
            logger.error(f"写入系统设置到文件失败: {e}")

    def _write_stocks_to_file(self, stocks_to_update, stocks_to_delete):
        """将股票配置写入stocks.json"""
        try:
            stocks_file = get_path("stock_monitor", "stocks_file", "./stocks.json")

            # 读取现有股票配置
            if os.path.exists(stocks_file):
                with open(stocks_file, "r", encoding="utf-8") as f:
                    stocks = json.load(f)
            else:
                stocks = []

            # 更新相关股票
            updated_count = 0
            i = 0
            while i < len(stocks):
                stock = stocks[i]
                if stock["code"] in stocks_to_update:
                    # 合并更新
                    stocks[i] = {**stock, **stocks_to_update[stock["code"]]}
                    updated_count += 1
                    i += 1
                elif stock["code"] in stocks_to_delete:
                    # 从列表中移除
                    stocks.pop(i)
                    updated_count += 1
                    # 不增加i，因为列表长度减少了，下一个元素移动到了当前位置
                else:
                    i += 1

            # 添加新股票
            for code, stock_data in stocks_to_update.items():
                if not any(s["code"] == code for s in stocks):
                    stocks.append(stock_data)
                    updated_count += 1

            # 移除被删除的股票
            stocks = [s for s in stocks if s["code"] not in stocks_to_delete]

            # 写回文件
            with open(stocks_file, "w", encoding="utf-8") as f:
                json.dump(stocks, f, ensure_ascii=False, indent=2)

            logger.info(f"股票配置已同步到文件: 更新了{updated_count}只股票")
        except Exception as e:
            logger.error(f"写入股票配置到文件失败: {e}")

    def shutdown(self):
        """关闭配置管理系统，同步剩余变更"""
        self.sync_thread_running = False
        if self.sync_thread:
            self.sync_thread.join(timeout=5)  # 最多等待5秒

        # 同步剩余的变更
        self._sync_to_file()
        logger.info("统一配置管理系统已关闭")


# 全局配置管理实例
config_manager = ConfigManager()


def get_global_notification_enabled():
    """获取全局通知开关状态"""
    return config_manager.get_global_notification_enabled()


def set_global_notification_enabled(enabled):
    """设置全局通知开关状态"""
    config_manager.set_global_notification_enabled(enabled)


def get_stock_notification_enabled(stock_code):
    """获取个股通知开关状态"""
    return config_manager.get_stock_notification_enabled(stock_code)


def set_stock_notification_enabled(stock_code, enabled):
    """设置个股通知开关状态"""
    config_manager.set_stock_notification_enabled(stock_code, enabled)


def get_industry_page_enabled():
    """获取行业页面开关状态"""
    settings = config_manager.get_settings()
    return settings.get("industry_page_enabled", False)


if __name__ == "__main__":
    # 测试配置管理系统功能
    logger.info("测试配置管理系统...")

    # 测试系统设置
    config_manager.set_check_interval(300)
    interval = config_manager.get_check_interval()
    logger.info(f"检查间隔: {interval}")

    # 测试全局通知开关
    set_global_notification_enabled(True)
    global_enabled = get_global_notification_enabled()
    logger.info(f"全局开关状态: {global_enabled}")

    # 测试股票管理
    test_stock = {
        "name": "测试股票",
        "code": "000001",
        "low_alert_price": 10.0,
        "high_alert_price": 15.0,
        "notification_enabled": True,
    }
    config_manager.add_stock(test_stock)
    retrieved_stock = config_manager.get_stock_by_code("000001")
    logger.info(f"获取的股票: {retrieved_stock}")

    logger.info("配置管理系统测试完成")
