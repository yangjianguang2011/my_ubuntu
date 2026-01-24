import logging
import os
import sys
from datetime import datetime

def get_global_config():
    """
    根据操作系统确定配置文件路径
    Windows系统：使用当前目录下的settings.json
    Linux系统：使用/data/stock_monitor/settings.json
    """
    cdir = os.path.dirname(os.path.abspath(__file__))
    default_template_dir = os.path.join(cdir, "web_templates")
    default_static_dir = os.path.join(cdir, "web_static")
    default_setting_file = os.path.join(cdir, 'settings.json')
    default_stocks_file = '/data/stock_monitor/stocks.json'
    default_analyst_dir = '/data/stock_monitor/analyst_data'
    default_xueqiu_dir = '/data/stock_monitor/xueqiu_data'
    default_log_file = '/data/stock_monitor/log.txt'
    default_analyst_log_file = '/data/stock_monitor/analyst_data/log.txt'
    default_database_dir = '/data/stock_monitor/database'

    default_message_server = 'https://message.jgyang.cn:5555'
    default_message_username = 'root'
    default_message_token = '12123121'
    default_message_channel = 'wechat'

    default_platform = 'linux'

    defalt_stock_cache_timeout_seconds = 3 * 60  # 默认3分钟
    default_industry_cache_timeout_seconds = 24 * 60 * 60 
    default_analyst_cache_timeout_seconds = 24 * 60 * 60

    config = {"web_template_dir": default_template_dir,
                    "web_static_dir": default_static_dir,
                    "analyst_data_dir": default_analyst_dir,
                    "xueqiu_data_dir": default_xueqiu_dir,
                    "settings_file": default_setting_file,
                    "stocks_file": default_stocks_file,
                    "log_file": default_log_file,
                    "analyst_log_file": default_analyst_log_file,
                    "database_dir": default_database_dir,
                    "message_server": default_message_server,
                    "message_username": default_message_username,
                    "message_token": default_message_token,
                    "message_channel": default_message_channel,
                    "platform": default_platform,
                    "stock_cache_timeout": defalt_stock_cache_timeout_seconds,
                    "industry_cache_timeout": default_industry_cache_timeout_seconds,
                    "analyst_cache_timeout": default_analyst_cache_timeout_seconds
                    }
    
    if sys.platform.startswith('win'):
        config['stocks_file'] = os.path.join(cdir, '..', 'run', 'stock_monitor', 'stocks.json')
        config['log_file'] = os.path.join(cdir, '..', 'run', 'stock_monitor', 'log.txt')
        config['analyst_data_dir'] = os.path.join(cdir, '..', 'run', 'stock_monitor', 'analyst_data')
        config['xueqiu_data_dir'] = os.path.join(cdir,'..', 'run', 'stock_monitor', 'xueqiu_data')
        config['analyst_log_file'] = os.path.join(cdir, '..', 'run', 'stock_monitor','analyst_data','log.txt')
        config['database_dir'] =  os.path.join(cdir, '..', 'run', 'stock_monitor', 'database')
        config['platform'] = 'windows'

    #make sure dir exists
    os.makedirs(config['analyst_data_dir'], exist_ok=True)
    os.makedirs(config['database_dir'], exist_ok=True)
    os.makedirs(config['xueqiu_data_dir'], exist_ok=True)

    # print(f"配置文件路径: {config}")  # 注释掉函数内的打印，避免重复输出

    return config

def get_log_file_path(name='stock_monitor'):

    gconfig = get_global_config()

    if name == 'eastmoney_analyst':
        log_file_path = gconfig['analyst_log_file']
    else:
        log_file_path = gconfig['log_file']

    return log_file_path

def setup_logger(name=__name__):
    """
    设置并返回一个logger实例
    """
    # 获取日志文件路径
    log_file_path = get_log_file_path(name)
    
    # 创建logger
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    
    # 避免重复添加处理器 - 更严格的检查
    if not logger.handlers:
        # 创建格式化器
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        
        # 创建文件处理器
        file_handler = logging.FileHandler(log_file_path, encoding='utf-8')
        file_handler.setLevel(logging.INFO)
        file_handler.setFormatter(formatter)
        
        # 创建控制台处理器
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(formatter)
        
        # 添加处理器到logger
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)
    
    return logger


# 创建根日志记录器
logger = setup_logger('stock_monitor')
gconfig = get_global_config()
print(f"配置文件路径: {gconfig}")
