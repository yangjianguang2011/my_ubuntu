import easyquotation
import pandas as pd
import akshare as ak
from logger_config import logger

# 使用混合缓存（内存+数据库），以SQLite作为二级缓存
from cache_with_database import cache_system

def get_stock_cached_data(cache_key, cache_duration=None):
    """
    从缓存获取数据
    :param cache_key: 缓存键
    :param cache_duration: 缓存有效时间（秒），如果为None则使用环境变量配置
    :return: 缓存的数据或None
    """
    return cache_system.get_cached_data(cache_key, 'stock', cache_duration)

def set_stock_cache_data(cache_key, data):
    """
    设置缓存数据
    :param cache_key: 缓存键
    :param data: 要缓存的数据
    """
    cache_system.set_cache_data(cache_key, data, 'stock')
    #logger.info(f"股票数据已缓存: {cache_key}")

def determine_market_type(stock_code):
    """
    根据股票代码确定市场类型
    :param stock_code: 股票代码
    :return: tuple (normalized_code, is_hk_stock)
    """
    original_code = stock_code

    # 根据用户要求，简化判断逻辑：5位数字就是港股，其余的都补6位数字
    if len(original_code) == 4:
        # 4位代码补全为6位
        is_hk_stock = False
        normalized_code = original_code.zfill(6)  # 补全为6位A股代码，如2738 -> 002738
    elif len(original_code) == 5:
        # 5位数字代码是港股
        is_hk_stock = original_code.isdigit()
        normalized_code = original_code  # 保持5位港股代码不变
    elif len(original_code) == 6:
        # 6位代码
        is_hk_stock = False  # 默认为A股
        normalized_code = original_code # 保持6位A股代码不变
    else:
        logger.warning(f"股票代码格式不正确: {stock_code}")
        return stock_code, None  # 返回None表示格式错误
    
    return normalized_code, is_hk_stock


def get_stock_info(stock):
    """
    根据股票对象获取股票信息
    :param stock: 股票对象，包含name和code字段
    :return: 包含股票信息的字典
    """
    stock_code = stock['code']
    stock_name = stock['name']
    
    # 使用股票名称和代码作为缓存键
    cache_key = f"stock_info_{stock_name}_{stock_code}"
    cached_data = get_stock_cached_data(cache_key)
    if cached_data is not None:
        #logger.info(f"从缓存返回股票 {stock_name}({stock_code}) 的信息")
        return cached_data

    logger.info(f"开始获取股票 {stock_name}({stock_code}) 的详细信息")
    
    try:
        # 使用新的市场判断函数
        normalized_code, is_hk_stock = determine_market_type(stock_code)
        
        if is_hk_stock is None:
            # 格式错误的情况
            result = {
                'stock_code': stock_code,
                'stock_name': stock_name,
                'price': None,
                'change_amount': None,
                'change_pct': None,
                'turnover_rate': None,
                'pe_ratio': None,
                'total_market_value': None,
                'volume': None
            }
            # 不缓存失败的结果，以便下次重试
            return result

        if is_hk_stock:
            # 港股，使用hkquote接口
            quotation = easyquotation.use('hkquote')
            stock_data = quotation.stocks([normalized_code])
        else:
            # A股使用sina接口
            quotation = easyquotation.use('sina')
            stock_data = quotation.stocks([normalized_code])
        
        if not stock_data or normalized_code not in stock_data:
            logger.warning(f"无法获取股票 {normalized_code} 的数据")
            result = {
                'stock_code': normalized_code,
                'stock_name': stock_name,
                'price': None,
                'change_amount': None,
                'change_pct': None,
                'turnover_rate': None,
                'pe_ratio': None,
                'total_market_value': None,
                'volume': None
            }
            # 不缓存失败的结果，以便下次重试
            return result

        stock_info = stock_data[normalized_code]

        # 初始化返回值 - 根据股票类型处理不同的数据格式
        if is_hk_stock:
            # 港股数据格式
            result = {
                'stock_code': normalized_code,
                'stock_name': stock_name,
                'price': float(stock_info['price']) if stock_info.get('price') and stock_info['price'] != '' and stock_info['price'] != '0' else None,  # 当前价格
                'open_price': float(stock_info['openPrice']) if stock_info.get('openPrice') and stock_info['openPrice'] != '' and stock_info['openPrice'] != '0' else None, # 开盘价
                'prev_close': float(stock_info['lastPrice']) if stock_info.get('lastPrice') and stock_info['lastPrice'] != '' and stock_info['lastPrice'] != '0' else None, # 昨收
                'high_price': float(stock_info['high']) if stock_info.get('high') and stock_info['high'] != '' and stock_info['high'] != '0' else None, # 最高价
                'low_price': float(stock_info['low']) if stock_info.get('low') and stock_info['low'] != '' and stock_info['low'] != '0' else None,  # 最低价
                'volume': stock_info.get('volume_2'),  # 成交量
                'turnover_value': stock_info.get('amountYuan'),  # 成交额
                'date': stock_info.get('date'),  # 日期
                'time': stock_info.get('time'),  # 时间
                'change_amount': float(stock_info['price']) - float(stock_info['lastPrice']) if stock_info.get('price') and stock_info.get('lastPrice') else None,  # 涨跌额
                'change_pct': float(stock_info['dtd']) if stock_info.get('dtd') else None,  # 涨跌幅
            }
        else:
            # A股数据格式
            result = {
                'stock_code': normalized_code,
                'stock_name': stock_name,
                'price': float(stock_info['now']) if stock_info.get('now') and stock_info['now'] != '' and stock_info['now'] != '0' else None,  # 当前价格
                'open_price': float(stock_info['open']) if stock_info.get('open') and stock_info['open'] != '' and stock_info['open'] != '0' else None,  # 开盘价
                'prev_close': float(stock_info['close']) if stock_info.get('close') and stock_info['close'] != '' and stock_info['close'] != '0' else None,  # 昨收
                'high_price': float(stock_info['high']) if stock_info.get('high') and stock_info['high'] != '' and stock_info['high'] != '0' else None, # 最高价
                'low_price': float(stock_info['low']) if stock_info.get('low') and stock_info['low'] != '' and stock_info['low'] != '0' else None,  # 最低价
                'volume': stock_info.get('turnover'),  # 成交量
                'turnover_value': stock_info.get('volume'),  # 成交额
                'date': stock_info.get('date'),  # 日期
                'time': stock_info.get('time'),  # 时间
            }

            # 计算涨跌额和涨跌幅
            if result.get('prev_close') is not None and result.get('price') is not None:
                result['change_amount'] = round(result['price'] - result['prev_close'], 2)
                result['change_pct'] = round((result['change_amount'] / result['prev_close']) * 100, 2)
            else:
                result['change_amount'] = None
                result['change_pct'] = None

        # 从API数据中提取更多字段
        result['turnover_rate'] = stock_info.get('turnover') if stock_info.get('turnover') else None # 换手率
        result['pe_ratio'] = None      # 市盈率
        result['total_market_value'] = stock_info.get('MarketCap') if stock_info.get('MarketCap') else None # 总市值

        # 缓存获取到的数据
        set_stock_cache_data(cache_key, result)
        #logger.info(f"股票 {stock_name}({stock_code}) 详细信息获取完成: {result}")
        logger.info(f"股票 {stock_name}({normalized_code}) 详细信息获取完成")
        return result
    except Exception as e:
        logger.error(f"获取股票 {stock_name}({stock_code}) 详细信息时出错: {str(e)}")
        # 不缓存失败的结果，以便下次重试
        return {
            'stock_code': stock_code,
            'stock_name': stock_name,
            'price': None,
            'change_amount': None,
            'change_pct': None,
            'turnover_rate': None,
            'pe_ratio': None,
            'total_market_value': None,
            'volume': None
        }

def get_stock_price_by_code(stock_code):
    """
    根据股票代码获取股票价格
    :param stock_code: 股票代码
    :return: 股票价格（浮点数）或None
    """
    # 创建一个模拟的股票对象用于调用新的get_stock_info函数
    stock = {'name': 'Unknown', 'code': stock_code}
    stock_info = get_stock_info(stock)
    if stock_info and 'price' in stock_info:
        return stock_info['price']
    return None

if __name__ == "__main__":
    print("测试股票数据获取功能...")
    
    # 从配置文件加载股票信息
    import os
    import json
    from logger_config import gconfig
    stocks_file = gconfig.get('stocks_file', './stocks.json')
    
    print(f"从配置文件 {stocks_file} 加载股票信息...")
    
    # 检查配置文件是否存在
    if os.path.exists(stocks_file):
        with open(stocks_file, 'r', encoding='utf-8') as f:
            stocks = json.load(f)
        print(f"成功加载 {len(stocks)} 只监控股票")
    else:
        print(f"配置文件 {stocks_file} 不存在，使用默认股票进行测试")
        # 使用默认股票列表进行测试
        stocks = [
            {'name': '平安银行', 'code': '000001'},
            {'name': '贵州茅台', 'code': '600519'},
            {'name': '招商银行', 'code': '600036'}
        ]
    
    if stocks:
        print("\n1. 测试获取配置文件中的股票信息:")
        for i, stock in enumerate(stocks[:3]):  # 只测试前3只股票
            print(f"\n测试第 {i+1} 只股票: {stock['name']}({stock['code']})")
            stock_info = get_stock_info(stock)
            print(f"获取到股票信息: 价格={stock_info.get('price')}, 涨跌幅={stock_info.get('change_pct')}")
        
        print("\n2. 测试获取股票价格:")
        for i, stock in enumerate(stocks[:3]):  # 只测试前3只股票
            stock_price = get_stock_price_by_code(stock['code'])
            print(f"股票 {stock['code']}({stock['name']}) 的价格: {stock_price}")
    else:
        print("配置文件中没有股票信息，使用默认股票进行测试")
        # 使用默认股票进行测试
        default_stock = {'name': '平安银行', 'code': '00001'}
        print(f"\n测试股票: {default_stock['name']}({default_stock['code']})")
        stock_info = get_stock_info(default_stock)
        print(f"获取到股票信息: 价格={stock_info.get('price')}, 涨跌幅={stock_info.get('change_pct')}")
        
        stock_price = get_stock_price_by_code(default_stock['code'])
        print(f"股票 {default_stock['code']} 的价格: {stock_price}")
