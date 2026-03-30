"""
数据库缓存实现方案
提供了Redis、SQLite和混合缓存三种方案
"""

import json
import os
from datetime import datetime, timedelta

from config import get_path, setup_logger

logger = setup_logger(__name__)

STOCK_CACHE_DURATOIN_SECONDS = int(get_path("cache", "stock_cache_timeout", 3 * 60))
INDUSTRY_CACHE_DURATION_SECONDS = int(
    get_path("cache", "industry_cache_timeout", 24 * 60 * 60)
)
ANALYST_CACHE_DURATION_SECONDS = int(
    get_path("cache", "analyst_cache_timeout", 24 * 60 * 60)
)
INDEX_CACHE_DURATION_SECONDS = int(
    get_path("cache", "index_cache_timeout", 1 * 24 * 60 * 60)
)
FUND_CACHE_DURATION_SECONDS = int(
    get_path("cache", "fund_cache_timeout", 1 * 24 * 60 * 60)
)


class LongTermStorage:
    """
    通用长期存储系统
    用于存储不需要自动清理的长期数据
    """

    def __init__(self, db_path="cache.db"):
        import sqlite3
        import threading

        db_dir = get_path(
            "stock_monitor", "database_dir", "/data/stock_monitor_data/database"
        )  # 使用配置中的数据库目录
        if db_dir is None:
            db_dir = "."  # 如果配置返回None，使用当前目录
        os.makedirs(db_dir, exist_ok=True)
        full_path = os.path.join(db_dir, db_path)
        self.db_path = full_path
        self.lock = threading.Lock()  # 线程安全锁
        self.init_db()

    def init_db(self):
        """初始化数据库表"""
        import sqlite3

        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                logger.info(f"初始化长期存储数据库: {self.db_path}")

                # 创建通用长期存储表
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS long_term_storage (
                        key TEXT PRIMARY KEY,
                        data TEXT NOT NULL,
                        created_at TIMESTAMP NOT NULL,
                        updated_at TIMESTAMP NOT NULL,
                        expires_at TIMESTAMP,
                        module_type TEXT NOT NULL
                    )
                """
                )

                # 创建索引以提高查询性能
                cursor.execute(
                    "CREATE INDEX IF NOT EXISTS idx_longterm_module ON long_term_storage(module_type)"
                )
                cursor.execute(
                    "CREATE INDEX IF NOT EXISTS idx_longterm_expires ON long_term_storage(expires_at)"
                )
                cursor.execute(
                    "CREATE INDEX IF NOT EXISTS idx_longterm_created ON long_term_storage(created_at)"
                )

                conn.commit()
                logger.info("长期存储数据库初始化完成")
        except Exception as e:
            logger.error(f"初始化长期存储数据库时出错: {e}")
            raise

    def store_data(self, key, data, module_type, expires_in_seconds=None):
        """存储数据到长期存储"""
        import json
        import sqlite3
        from datetime import datetime, timedelta

        try:
            now = datetime.now()
            expires_at = None
            if expires_in_seconds is not None:
                expires_at = now + timedelta(seconds=expires_in_seconds)

            with self.lock:  # 添加锁保护
                with sqlite3.connect(self.db_path) as conn:
                    cursor = conn.cursor()
                cursor.execute(
                    """
                    INSERT OR REPLACE INTO long_term_storage
                    (key, data, created_at, updated_at, expires_at, module_type)
                    VALUES (?, ?, ?, ?, ?, ?)
                """,
                    (
                        key,
                        json.dumps(data, ensure_ascii=False),
                        now.isoformat(),
                        now.isoformat(),
                        expires_at.isoformat() if expires_at else None,
                        module_type,
                    ),
                )
                conn.commit()
                logger.info(f"数据已存储到长期存储: {key} (模块: {module_type})")
                return True
        except Exception as e:
            logger.error(f"存储长期数据失败: {e}")
            return False

    def retrieve_data(self, key):
        """从长期存储中获取数据"""
        import json
        import sqlite3
        from datetime import datetime

        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    SELECT data, created_at, updated_at, expires_at, module_type
                    FROM long_term_storage
                    WHERE key = ?
                """,
                    (key,),
                )

                row = cursor.fetchone()
                if row:
                    (
                        data_str,
                        created_at_str,
                        updated_at_str,
                        expires_at_str,
                        module_type,
                    ) = row
                    # 检查是否过期
                    if expires_at_str:
                        expires_at = datetime.fromisoformat(expires_at_str)
                        if expires_at < datetime.now():
                            logger.info(f"长期存储数据已过期，删除: {key}")
                            # 删除过期数据
                            self.delete_data(key)
                            return None

                    return json.loads(data_str)
                return None
        except Exception as e:
            logger.error(f"获取长期数据失败: {e}")
            return None

    def delete_data(self, key):
        """删除长期存储的数据"""
        import sqlite3

        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM long_term_storage WHERE key = ?", (key,))
                conn.commit()
                deleted_count = cursor.rowcount
                if deleted_count > 0:
                    logger.info(f"已删除长期存储数据: {key}")
                return deleted_count > 0
        except Exception as e:
            logger.error(f"删除长期数据失败: {e}")
            return False

    def get_module_data(self, module_type, limit=None):
        """获取指定模块的所有数据"""
        import json
        import sqlite3
        from datetime import datetime

        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                if limit:
                    cursor.execute(
                        """
                        SELECT key, data, created_at, updated_at, expires_at, module_type
                        FROM long_term_storage
                        WHERE module_type = ?
                        ORDER BY updated_at DESC
                        LIMIT ?
                    """,
                        (module_type, limit),
                    )
                else:
                    cursor.execute(
                        """
                        SELECT key, data, created_at, updated_at, expires_at, module_type
                        FROM long_term_storage
                        WHERE module_type = ?
                        ORDER BY updated_at DESC
                    """,
                        (module_type,),
                    )

                rows = cursor.fetchall()
                result = []
                for row in rows:
                    (
                        data_str,
                        created_at_str,
                        updated_at_str,
                        expires_at_str,
                        module_type,
                    ) = (row[1], row[2], row[3], row[4], row[5])
                    try:
                        data = json.loads(data_str)
                    except json.JSONDecodeError:
                        data = data_str  # 如果不是JSON格式，直接返回原始字符串
                    result.append(
                        {
                            "key": row[0],
                            "data": data,
                            "created_at": created_at_str,
                            "updated_at": updated_at_str,
                            "expires_at": expires_at_str,
                            "module_type": module_type,
                        }
                    )
                return result
        except Exception as e:
            logger.error(f"获取模块数据失败: {e}")
            return []

    def cleanup_expired_data(self):
        """清理过期的长期存储数据"""
        import sqlite3
        from datetime import datetime

        try:
            current_time = datetime.now()

            with self.lock:  # 添加锁保护
                with sqlite3.connect(self.db_path) as conn:
                    cursor = conn.cursor()
                cursor.execute(
                    """
                    DELETE FROM long_term_storage
                    WHERE expires_at IS NOT NULL AND expires_at < ?
                """,
                    (current_time,),
                )
                deleted_count = cursor.rowcount
                if deleted_count > 0:
                    logger.info(f"清理了 {deleted_count} 条过期的长期存储数据")
                conn.commit()
                return deleted_count
        except Exception as e:
            logger.error(f"清理过期长期存储数据时出错: {e}")
            return 0


class SQLiteCache:
    """
    SQLite缓存实现
    适合轻量级、单机应用
    """

    def __init__(self, db_path="cache.db"):
        import sqlite3
        import threading

        db_dir = get_path(
            "stock_monitor", "database_dir", "/data/stock_monitor_data/database"
        )  # 使用配置中的数据库目录
        if db_dir is None:
            db_dir = "."  # 如果配置返回None，使用当前目录
        os.makedirs(db_dir, exist_ok=True)
        full_path = os.path.join(db_dir, db_path)
        logger.info(f"SQLite缓存数据库路径: {full_path}")
        self.db_path = full_path
        self.lock = threading.Lock()  # 线程安全锁
        self.init_db()

    def init_db(self):
        """初始化数据库表"""
        import sqlite3

        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                logger.info(f"初始化SQLite缓存数据库: {self.db_path}")
                # 创建股票数据缓存表
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS stock_cache (
                        cache_key TEXT PRIMARY KEY,
                        data TEXT NOT NULL,
                        cache_time TIMESTAMP NOT NULL,
                        cache_duration INTEGER NOT NULL
                    )
                """
                )

                # 创建行业数据缓存表
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS industry_cache (
                        cache_key TEXT PRIMARY KEY,
                        data TEXT NOT NULL,
                        cache_time TIMESTAMP NOT NULL,
                        cache_duration INTEGER NOT NULL
                    )
                """
                )

                # 创建分析师数据缓存表
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS analyst_cache (
                        cache_key TEXT PRIMARY KEY,
                        data TEXT NOT NULL,
                        cache_time TIMESTAMP NOT NULL,
                        cache_duration INTEGER NOT NULL
                    )
                """
                )

                # 创建指数数据缓存表
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS index_cache (
                        cache_key TEXT PRIMARY KEY,
                        data TEXT NOT NULL,
                        cache_time TIMESTAMP NOT NULL,
                        cache_duration INTEGER NOT NULL
                    )
                """
                )

                # 创建基金数据缓存表
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS fund_cache (
                        cache_key TEXT PRIMARY KEY,
                        data TEXT NOT NULL,
                        cache_time TIMESTAMP NOT NULL,
                        cache_duration INTEGER NOT NULL
                    )
                """
                )

                # 为缓存时间创建索引以提高查询性能
                cursor.execute(
                    "CREATE INDEX IF NOT EXISTS idx_stock_cache_time ON stock_cache(cache_time)"
                )
                cursor.execute(
                    "CREATE INDEX IF NOT EXISTS idx_industry_cache_time ON industry_cache(cache_time)"
                )
                cursor.execute(
                    "CREATE INDEX IF NOT EXISTS idx_index_cache_time ON index_cache(cache_time)"
                )
                cursor.execute(
                    "CREATE INDEX IF NOT EXISTS idx_fund_cache_time ON fund_cache(cache_time)"
                )

                conn.commit()
                logger.info("SQLite缓存数据库初始化完成")
        except Exception as e:
            logger.error(f"初始化SQLite数据库时出错: {e}")

    def cleanup_expired_cache(self):
        """清理过期的缓存数据"""
        import sqlite3

        try:
            current_time = datetime.now()

            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                # 清理过期的股票缓存
                cursor.execute(
                    """
                    DELETE FROM stock_cache
                    WHERE datetime(cache_time, '+' || cache_duration || ' seconds') < ?
                """,
                    (current_time,),
                )
                logger.info(f"清理了 {cursor.rowcount} 条股票过期缓存数据")

                # 清理过期的行业缓存
                cursor.execute(
                    """
                    DELETE FROM industry_cache
                    WHERE datetime(cache_time, '+' || cache_duration || ' seconds') < ?
                """,
                    (current_time,),
                )
                logger.info(f"清理了 {cursor.rowcount} 条行业过期缓存数据")

                # 清理过期的基金缓存
                cursor.execute(
                    """
                    DELETE FROM fund_cache
                    WHERE datetime(cache_time, '+' || cache_duration || ' seconds') < ?
                """,
                    (current_time,),
                )
                logger.info(f"清理了 {cursor.rowcount} 条基金过期缓存数据")

                deleted_count = cursor.rowcount
                if deleted_count > 0:
                    logger.info(f"清理了 {deleted_count} 条过期缓存数据")

                conn.commit()
        except Exception as e:
            logger.error(f"清理过期缓存时出错: {e}")

    def get_cached_data(self, cache_key, cache_type="stock", cache_duration=None):
        """从SQLite获取缓存数据"""
        import sqlite3

        try:
            current_time = datetime.now()

            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                if cache_type == "stock":
                    table_name = "stock_cache"
                elif cache_type == "industry":
                    table_name = "industry_cache"
                elif cache_type == "analyst":
                    table_name = "analyst_cache"
                elif cache_type == "index":
                    table_name = "index_cache"
                elif cache_type == "fund":
                    table_name = "fund_cache"
                else:  # 默认
                    logger.error(f"未知缓存类型 {cache_type}，使用默认表 stock_cache")
                    table_name = "stock_cache"

                cursor.execute(
                    f"""
                    SELECT data, cache_time, cache_duration
                    FROM {table_name}
                    WHERE cache_key = ?
                """,
                    (cache_key,),
                )

                row = cursor.fetchone()
                if row:
                    data_str, cache_time_str, stored_duration = row
                    cache_time = datetime.fromisoformat(cache_time_str)

                    # 使用传入的缓存时长或数据库中存储的时长
                    effective_duration = (
                        cache_duration
                        if cache_duration is not None
                        else stored_duration
                    )

                    if current_time - cache_time < timedelta(
                        seconds=effective_duration
                    ):
                        logger.info(f"从SQLite {cache_type} 缓存获取数据: {cache_key}")
                        return json.loads(data_str)
                    else:
                        # 缓存过期，删除它
                        cursor.execute(
                            f"DELETE FROM {table_name} WHERE cache_key = ?",
                            (cache_key,),
                        )
                        conn.commit()
                        logger.info(
                            f"SQLite {cache_type} 缓存已过期，删除: {cache_key}"
                        )
        except Exception as e:
            logger.error(f"从SQLite获取缓存数据时出错: {e}")

        return None

    def set_cache_data(self, cache_key, data, cache_type="stock", cache_duration=None):
        """设置SQLite缓存数据"""
        import sqlite3

        try:
            if cache_type == "stock":
                duration = (
                    cache_duration
                    if cache_duration is not None
                    else STOCK_CACHE_DURATOIN_SECONDS
                )
            elif cache_type == "industry":
                duration = (
                    cache_duration
                    if cache_duration is not None
                    else INDUSTRY_CACHE_DURATION_SECONDS
                )
            elif cache_type == "analyst":
                duration = (
                    cache_duration
                    if cache_duration is not None
                    else ANALYST_CACHE_DURATION_SECONDS
                )
            elif cache_type == "index":
                duration = (
                    cache_duration
                    if cache_duration is not None
                    else INDEX_CACHE_DURATION_SECONDS
                )
            elif cache_type == "fund":
                duration = (
                    cache_duration
                    if cache_duration is not None
                    else FUND_CACHE_DURATION_SECONDS
                )
            else:  # 默认
                logger.warning(
                    f"set_cache_data: unknow cache_type {cache_type} , use defalut industry cache duration..."
                )
                duration = (
                    cache_duration
                    if cache_duration is not None
                    else INDUSTRY_CACHE_DURATION_SECONDS
                )

            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                # 根据缓存类型选择表名
                if cache_type == "stock":
                    table_name = "stock_cache"
                elif cache_type == "industry":
                    table_name = "industry_cache"
                elif cache_type == "analyst":
                    table_name = "analyst_cache"
                elif cache_type == "index":
                    table_name = "index_cache"
                elif cache_type == "fund":
                    table_name = "fund_cache"
                else:  # analyst 或其他类型
                    logger.warning(
                        f"未知缓存类型 {cache_type}，使用默认表 industry_cache"
                    )
                    table_name = "analyst_cache"

                # 插入或替换缓存数据
                cursor.execute(
                    f"""
                    INSERT OR REPLACE INTO {table_name}
                    (cache_key, data, cache_time, cache_duration)
                    VALUES (?, ?, ?, ?)
                """,
                    (
                        cache_key,
                        json.dumps(data, ensure_ascii=False),
                        datetime.now().isoformat(),
                        duration,
                    ),
                )

                conn.commit()
                logger.info(f"数据已缓存到SQLite {table_name}: {cache_key}")
        except Exception as e:
            logger.error(f"设置SQLite缓存数据时出错: {e}")


class HybridCache:
    """
    混合缓存策略
    结合内存缓存和数据库缓存的优势
    """

    def __init__(self):
        import threading

        self.memory_cache = {}  # 一级缓存：内存
        self.memory_cache_lock = threading.Lock()

        # 二级缓存：默认使用SQLite
        self.secondary_cache = SQLiteCache()
        logger.info("使用混合缓存策略，二级缓存类型: sqlite")

    def get_cached_data(self, cache_key, cache_type="stock", cache_duration=None):
        """多级缓存获取数据"""
        # 1. 首先检查内存缓存
        with self.memory_cache_lock:
            if cache_key in self.memory_cache:
                cached_item = self.memory_cache[cache_key]
                cache_time = cached_item["time"]
                data = cached_item["data"]

                if cache_type == "stock":
                    duration = (
                        cache_duration
                        if cache_duration is not None
                        else STOCK_CACHE_DURATOIN_SECONDS
                    )
                elif cache_type == "industry":
                    duration = (
                        cache_duration
                        if cache_duration is not None
                        else INDUSTRY_CACHE_DURATION_SECONDS
                    )
                elif cache_type == "analyst":
                    duration = (
                        cache_duration
                        if cache_duration is not None
                        else ANALYST_CACHE_DURATION_SECONDS
                    )
                elif cache_type == "index":
                    duration = (
                        cache_duration
                        if cache_duration is not None
                        else INDUSTRY_CACHE_DURATION_SECONDS
                    )  # 指数数据使用与行业数据相同的缓存时长
                elif cache_type == "fund":
                    duration = (
                        cache_duration
                        if cache_duration is not None
                        else FUND_CACHE_DURATION_SECONDS
                    )
                else:
                    duration = (
                        cache_duration
                        if cache_duration is not None
                        else STOCK_CACHE_DURATOIN_SECONDS
                    )
                    logger.warning(f"未知缓存类型 {cache_type}，使用默认时长")

                if datetime.now() - cache_time < timedelta(seconds=duration):
                    logger.info(f"从内存缓存获取数据: {cache_key}")
                    return data
                else:
                    # 内存缓存过期，删除它
                    del self.memory_cache[cache_key]

        # 2. 检查二级缓存
        if cache_type == "stock":
            data = self.secondary_cache.get_cached_data(
                cache_key, cache_type, cache_duration
            )
        elif cache_type == "industry":
            data = self.secondary_cache.get_cached_data(
                cache_key, cache_type, cache_duration
            )
        elif cache_type == "analyst":
            data = self.secondary_cache.get_cached_data(
                cache_key, cache_type, cache_duration
            )
        elif cache_type == "index":
            data = self.secondary_cache.get_cached_data(
                cache_key, cache_type, cache_duration
            )
        elif cache_type == "fund":
            data = self.secondary_cache.get_cached_data(
                cache_key, cache_type, cache_duration
            )
        else:
            logger.warning(f"未知缓存类型 {cache_type}，从stock缓存获取数据")
            data = self.secondary_cache.get_cached_data(
                cache_key, "stock", cache_duration
            )

        if data is not None:
            # 将数据放回内存缓存（热点数据）
            with self.memory_cache_lock:
                self.memory_cache[cache_key] = {"time": datetime.now(), "data": data}
            # logger.info(f"从二级缓存获取数据并存入内存: {cache_key}")
            return data

        return None

    def set_cache_data(self, cache_key, data, cache_type="stock", cache_duration=None):
        """多级缓存设置数据"""
        # 设置内存缓存
        with self.memory_cache_lock:
            self.memory_cache[cache_key] = {"time": datetime.now(), "data": data}

        # 设置二级缓存
        self.secondary_cache.set_cache_data(cache_key, data, cache_type, cache_duration)

    def get_index_cached_data(self, cache_key, cache_duration=None):
        """从多级缓存获取指数数据"""
        return self.get_cached_data(cache_key, "index", cache_duration)

    def set_index_cache_data(self, cache_key, data, cache_duration=None):
        """设置多级指数数据缓存"""
        self.set_cache_data(cache_key, data, "index", cache_duration)

    def get_fund_cached_data(self, cache_key, cache_duration=None):
        """从多级缓存获取基金数据"""
        return self.get_cached_data(cache_key, "fund", cache_duration)

    def set_fund_cache_data(self, cache_key, data, cache_duration=None):
        """设置多级基金数据缓存"""
        self.set_cache_data(cache_key, data, "fund", cache_duration)


# 全局缓存实例
def initialize_cache():
    """初始化缓存系统"""
    cache_type = os.getenv("CACHE_TYPE", "hybrid").lower()
    if cache_type == "sqlite":
        logger.info("使用SQLite作为缓存系统")
        return SQLiteCache()
    elif cache_type == "hybrid":
        logger.info("使用混合缓存作为缓存系统")
        return HybridCache()
    else:
        # 默认使用混合缓存
        logger.info("使用混合缓存作为默认缓存系统")
        return HybridCache()


# 根据配置初始化缓存
cache_system = initialize_cache()


def get_cached_data(cache_key, cache_duration=None):
    """从缓存获取数据"""
    return cache_system.get_cached_data(cache_key, "stock", cache_duration)


def set_cache_data(cache_key, data):
    """设置缓存数据"""
    cache_system.set_cache_data(cache_key, data, "stock")


def get_industry_cached_data(cache_key, cache_duration=None):
    """从行业数据缓存获取数据"""
    return cache_system.get_cached_data(cache_key, "industry", cache_duration)


def set_industry_cache_data(cache_key, data):
    """设置行业数据缓存"""
    cache_system.set_cache_data(cache_key, data, "industry")


def get_analyst_cached_data(cache_key, cache_duration=None):
    """从分析师数据缓存获取数据"""
    return cache_system.get_cached_data(cache_key, "analyst", cache_duration)


def set_analyst_cache_data(cache_key, data, cache_duration=None):
    """设置分析师数据缓存"""
    cache_system.set_cache_data(cache_key, data, "analyst", cache_duration)


def get_index_cached_data(cache_key, cache_duration=None):
    """从指数数据缓存获取数据"""
    return cache_system.get_cached_data(cache_key, "index", cache_duration)


def set_index_cache_data(cache_key, data, cache_duration=None):
    """设置指数数据缓存"""
    cache_system.set_cache_data(cache_key, data, "index", cache_duration)


def get_fund_cached_data(cache_key, cache_duration=None):
    """从基金数据缓存获取数据"""
    return cache_system.get_cached_data(cache_key, "fund", cache_duration)


def set_fund_cache_data(cache_key, data, cache_duration=None):
    """设置基金数据缓存"""
    cache_system.set_cache_data(cache_key, data, "fund", cache_duration)


# 全局长期存储实例
long_term_storage = LongTermStorage()


# 通用长期存储函数
def store_long_term_data(key, data, module_type, expires_in_seconds=None):
    """通用存储函数"""
    return long_term_storage.store_data(key, data, module_type, expires_in_seconds)


def retrieve_long_term_data(key):
    """通用获取函数"""
    return long_term_storage.retrieve_data(key)


def delete_long_term_data(key):
    """通用删除函数"""
    return long_term_storage.delete_data(key)


def get_module_long_term_data(module_type, limit=None):
    """获取指定模块的长期数据"""
    return long_term_storage.get_module_data(module_type, limit)


def cleanup_expired_long_term_data():
    """清理过期的长期存储数据"""
    return long_term_storage.cleanup_expired_data()


# 使用示例
if __name__ == "__main__":
    # 测试缓存功能
    test_key = "test_stock_data"
    test_data = {"price": 100.5, "change_pct": 2.5, "volume": 1000000}

    logger.info("测试缓存系统...")

    # 设置缓存
    set_cache_data(test_key, test_data)

    # 获取缓存
    retrieved_data = get_cached_data(test_key)
    logger.info(f"从缓存获取的数据: {retrieved_data}")

    # 测试行业数据缓存
    industry_key = "test_industry_data"
    industry_data = {"name": "科技行业", "change_pct": 3.2, "stocks_count": 50}

    set_industry_cache_data(industry_key, industry_data)
    retrieved_industry_data = get_industry_cached_data(industry_key)
    logger.info(f"从行业缓存获取的数据: {retrieved_industry_data}")

    # 测试分析师数据缓存
    analyst_key = "test_analyst_data"
    analyst_data = {"name": "分析师数据测试", "rankings": [1, 2, 3], "stocks_count": 10}

    set_analyst_cache_data(analyst_key, analyst_data)
    retrieved_analyst_data = get_analyst_cached_data(analyst_key)
    logger.info(f"从分析师缓存获取的数据: {retrieved_analyst_data}")

    # 测试长期存储功能
    logger.info("测试长期存储系统...")
    long_term_key = "test_long_term_data"
    long_term_data = {
        "message": "这是一个长期存储的数据测试",
        "timestamp": datetime.now().isoformat(),
    }
    store_long_term_data(long_term_key, long_term_data, "test_module")
    retrieved_long_term_data = retrieve_long_term_data(long_term_key)
    logger.info(f"从长期存储获取的数据: {retrieved_long_term_data}")

    logger.info("缓存系统测试完成")
