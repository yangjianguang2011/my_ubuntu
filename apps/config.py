"""
统一配置模块 - 供各爬虫模块（apps/xueqiu、apps/eastmoney、apps/iptv、apps/news）
和 stock_monitor 使用。

路径解析规则
============
`config.ini` 里写的是**容器内视角**的绝对路径（`/data`、`/root/apps`、`/var/log`）：

* **容器 / Linux（生产）**：原样使用（`/data` 就是挂载点）。
* **Windows（本机开发）**：按 `[mount_point]` 映射到项目内目录，
  例如 `/data` → `<项目根>/run`、`/root/apps` → `<项目根>`、`/var/log` → `<项目根>/logs`。

另外支持 `${key}` 变量展开（引用**同一段**内的其它键），
例如 `[stockdb] pybao_dir = ${dir}/pybao`。

非路径型配置（数字、布尔、URL、枚举）不受影响：它们不以 `/` 开头，解析函数会原样返回。
"""

import configparser
import logging
import os
import platform
import re
from pathlib import Path

_APPS_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _APPS_DIR.parent  # apps/ 的上一级 = 项目根

CONFIG_FILE = os.environ.get("CONFIG_FILE")
if not CONFIG_FILE:
    if platform.system() == "Windows":
        CONFIG_FILE = str(_APPS_DIR / "config.ini")
    else:
        CONFIG_FILE = "/root/apps/config.ini"

_VAR_RE = re.compile(r"\$\{(\w+)\}")


# ==================== 配置读取 ====================


def get_config():
    """读取配置文件（每次重新读取，便于运行时改动即时生效）。"""
    config = configparser.ConfigParser()
    config.read(CONFIG_FILE, encoding="utf-8")
    return config


def _mount_map(config):
    """[mount_point]：容器内路径 → 本机相对路径（相对项目根）。按前缀长度降序，便于最长匹配。"""
    pairs = []
    if config.has_section("mount_point"):
        for prefix, local in config.items("mount_point"):
            prefix = prefix.strip().rstrip("/")
            if prefix:
                pairs.append((prefix, local.strip()))
    pairs.sort(key=lambda p: len(p[0]), reverse=True)
    return pairs


def _expand(config, section, value):
    """展开 ${key}：引用同一段内的键；找不到则原样保留。"""
    def repl(match):
        name = match.group(1)
        if config.has_option(section, name):
            return config.get(section, name)
        return match.group(0)

    return _VAR_RE.sub(repl, value)


def _host_path(local):
    """[mount_point] 的值 → 本机绝对路径。

    以 `/`、`\\` 或盘符开头视为本机绝对路径；否则相对项目根。
    """
    if not local or local == ".":
        return str(_PROJECT_ROOT)
    if local.startswith(("/", "\\")) or re.match(r"^[A-Za-z]:", local):
        return local
    return os.path.join(str(_PROJECT_ROOT), local)


def _resolve(config, value):
    """把配置里的路径值解析为本机可用路径（见模块 docstring 的解析规则）。"""
    if not value or not value.startswith("/"):
        return value  # 非容器绝对路径（数字/URL/枚举/Windows 盘符/相对路径）：原样
    if platform.system() != "Windows":
        return value  # 容器/Linux：容器内路径原样使用

    for prefix, local in _mount_map(config):
        if value == prefix or value.startswith(prefix + "/"):
            rest = value[len(prefix):].strip("/")
            base = _host_path(local)
            return os.path.normpath(os.path.join(base, rest)) if rest else os.path.normpath(base)
    return value  # 未登记映射的容器路径：原样返回（交由调用方/容器决定）


def get_path(section, key, fallback=None):
    """获取配置值（路径会按平台解析、`${var}` 会展开）；优先使用环境变量。

    环境变量名：`STOCK_MONITOR_<SECTION>_<KEY>`（点/横线转下划线），
    例如 `[stockdb] host` → `STOCK_MONITOR_STOCKDB_HOST`。
    """
    env_key = f"STOCK_MONITOR_{section.upper()}_{key.upper()}".replace(
        ".", "_"
    ).replace("-", "_")
    env_value = os.environ.get(env_key)
    if env_value is not None:
        return _resolve(get_config(), env_value)

    config = get_config()
    try:
        raw = config.get(section, key)
    except (configparser.NoSectionError, configparser.NoOptionError):
        return fallback
    return _resolve(config, _expand(config, section, raw))


def get_paths():
    """获取所有路径（均已按平台解析，可直接使用）。"""
    config = get_config()

    def path(section, key, fallback):
        try:
            raw = config.get(section, key)
        except (configparser.NoSectionError, configparser.NoOptionError):
            return _resolve(config, fallback)
        return _resolve(config, _expand(config, section, raw))

    return {
        # 通用
        "root_dir": path("paths", "root_dir", "/root/apps"),
        "data_dir": path("paths", "data_dir", "/data"),
        "log_dir": path("paths", "log_dir", "/data/logs"),
        # 爬虫模块
        "xueqiu_dir": path("xueqiu", "dir", "/root/apps/xueqiu"),
        "xueqiu_data_dir": path("xueqiu", "data_dir", "/data/xueqiu_data"),
        "eastmoney_dir": path("eastmoney", "dir", "/root/apps/eastmoney"),
        "analyst_data_dir": path("eastmoney", "data_dir", "/data/analyst_data"),
        "iptv_dir": path("iptv", "dir", "/root/apps/iptv"),
        "iptv_data_dir": path("iptv", "data_dir", "/data/iptv"),
        "news_dir": path("news", "dir", "/root/apps/news"),
        "news_data_dir": path("news", "data_dir", "/data/news"),
        # Stock Monitor
        "stock_monitor_dir": path(
            "stock_monitor", "stock_monitor_dir", "/root/apps/stock_monitor"
        ),
        "stock_monitor_data_dir": path(
            "stock_monitor", "stock_monitor_data_dir", "/data/stock_monitor_data"
        ),
        "database_dir": path(
            "stock_monitor", "database_dir", "/data/stock_monitor_data/database"
        ),
    }


# ==================== 日志配置 ====================


def get_log_file_path(name="stock_monitor"):
    """
    根据名称获取日志文件路径。

    Python 日志统一落在**数据目录**下（容器内 `/data/...`，随数据卷持久化），
    不使用 `/var/log`（容器内非持久）。
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
