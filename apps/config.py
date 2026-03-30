"""
统一配置模块 - 供 crawlers 和 stock_monitor 使用
"""

import configparser
import logging
import os
# 检测运行环境，如果是Windows则使用当前目录下的config.ini
import platform
import sys

CONFIG_FILE = os.environ.get("CONFIG_FILE", "/root/apps/config.ini")

# ==================== 配置读取 ====================


def get_config():
    """读取配置文件"""
    config = configparser.ConfigParser()
    config.read(CONFIG_FILE, encoding="utf-8")
    return config


def get_path(section, key, fallback=None):
    """获取路径配置，优先使用环境变量"""
    # 首先检查环境变量
    env_key = f"STOCK_MONITOR_{section.upper()}_{key.upper()}".replace(
        ".", "_"
    ).replace("-", "_")
    env_value = os.environ.get(env_key)
    if env_value is not None:
        return env_value

    # 如果环境变量不存在，使用配置文件中的值
    config = get_config()
    try:
        return config.get(section, key)
    except (configparser.NoSectionError, configparser.NoOptionError):
        return fallback


def get_paths():
    """获取所有路径"""
    config = get_config()
    return {
        "root_dir": config.get("paths", "root_dir", fallback="/root/apps"),
        "data_dir": config.get("paths", "data_dir", fallback="/data"),
        "log_dir": config.get("paths", "log_dir", fallback="/var/log"),
        # Crawlers
        "xueqiu_dir": config.get(
            "crawlers", "xueqiu_dir", fallback="/root/apps/crawlers/xueqiu"
        ),
        "eastmoney_dir": config.get(
            "crawlers", "eastmoney_dir", fallback="/root/apps/crawlers/eastmoney"
        ),
        "iptv_dir": config.get("iptv", "iptv_dir", fallback="/root/apps/iptv"),
        "iptv_data_dir": config.get(
            "iptv", "iptv_data_dir", fallback="/root/apps/iptv_data"
        ),
        "news_dir": config.get("news", "news_dir", fallback="/root/apps/news"),
        "news_data_dir": config.get(
            "news", "news_data_dir", fallback="/root/apps/news_data"
        ),
        "xueqiu_data_dir": config.get(
            "crawlers", "xueqiu_data_dir", fallback="/data/xueqiu_data"
        ),
        "analyst_data_dir": config.get(
            "crawlers", "analyst_data_dir", fallback="/data/analyst_data"
        ),
        # Stock Monitor
        "stock_monitor_dir": config.get(
            "stock_monitor", "stock_monitor_dir", fallback="/root/apps/stock_monitor"
        ),
        "stock_monitor_data_dir": config.get(
            "stock_monitor",
            "stock_monitor_data_dir",
            fallback="/data/stock_monitor_data",
        ),
        "database_dir": config.get(
            "stock_monitor",
            "database_dir",
            fallback="/data/stock_monitor_data/database",
        ),
    }


# ==================== 日志配置 ====================


def get_log_file_path(name="stock_monitor"):
    """
    根据名称获取日志文件路径
    """
    paths = get_paths()

    if name == "eastmoney_analyst":
        return paths["analyst_data_dir"] + "/log.txt"
    elif name == "xueqiu_scraper":
        return paths["xueqiu_data_dir"] + "/log.txt"
    elif name == "analyst_reports":
        return paths["analyst_data_dir"] + "/analyst_reports_log.txt"
    else:
        return paths["stock_monitor_data_dir"] + "/log.txt"


def setup_logger(name=__name__, log_file=None):
    """
    设置并返回一个 logger 实例
    """
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)

    # 避免重复添加处理器
    if logger.handlers:
        return logger

    # 创建格式化器
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    # 日志文件处理器
    if log_file is None:
        log_file = get_log_file_path(name)

    if log_file:
        try:
            # 确保日志目录存在
            os.makedirs(os.path.dirname(log_file), exist_ok=True)

            file_handler = logging.FileHandler(log_file, encoding="utf-8")
            file_handler.setLevel(logging.INFO)
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)
        except (PermissionError, OSError) as e:
            # 如果无法创建日志文件，输出警告但继续运行
            print(f"Warning: Could not create log file {log_file}: {e}")
            print("Falling back to console-only logging")

    # 控制台处理器（始终添加）
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    return logger
