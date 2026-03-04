import time
import akshare as ak
from datetime import datetime
from logger_config import logger

# 使用混合缓存（内存+数据库），以SQLite作为二级缓存
from cache_with_database import cache_system


def _format_stock_symbol(symbol):
    """
    格式化股票代码，确保其带有正确的市场前缀
    :param symbol: 股票代码，可能是纯数字或已带前缀的格式
    :return: 格式化后的股票代码
    """
    if not symbol:
        return symbol

    # 如果已经包含市场前缀，直接返回
    if symbol.startswith(('SH', 'SZ', 'BJ')):
        return symbol.upper()

    # 如果是纯数字，根据代码规则添加前缀
    symbol = str(symbol).strip()
    if symbol.startswith(('00', '15', '16', '18', '19', '20', '30', '39')):
        # 深圳市场：00开头的股票（如000408是深圳市场股票）
        return f"SZ{symbol}"
    elif symbol.startswith(('50', '51', '60', '68')):
        # 上海市场：60、68开头的股票
        return f"SH{symbol}"
    elif symbol.startswith('4'):
        # 北交所：4开头的股票
        return f"BJ{symbol}"
    else:
        # 默认为深圳市场（因为000408是深圳市场股票）
        return f"SZ{symbol}"


def _convert_dates_to_strings(obj):
    """
    递归地将对象中的日期类型转换为字符串，以便JSON序列化
    :param obj: 需要处理的对象
    :return: 处理后的对象
    """
    import pandas as pd
    from datetime import date, datetime
    import numpy as np

    if isinstance(obj, dict):
        return {key: _convert_dates_to_strings(value) for key, value in obj.items()}
    elif isinstance(obj, list):
        return [_convert_dates_to_strings(item) for item in obj]
    elif isinstance(obj, (date, datetime)):
        return obj.isoformat()
    elif isinstance(obj, str):
        # 检查是否为日期格式的字符串，如果是则保持不变
        # 这样可以避免pandas错误地尝试将普通字符串当作日期处理
        try:
            # 尝试解析日期字符串，但不改变其格式
            if '-' in obj and len(obj) >= 8:  # 简单检查是否可能是日期格式
                parts = obj.split('-')
                if len(parts) == 3 and all(part.isdigit() for part in parts):
                    # 验证是否为有效日期，但返回原始字符串
                    year, month, day = parts
                    if 1 <= int(month) <= 12 and 1 <= int(day) <= 31:
                        return obj  # 保持原始日期字符串格式
        except:
            pass  # 如果解析失败，继续下面的逻辑
        return obj
    elif isinstance(obj, pd.Timestamp):
        return obj.isoformat() if hasattr(obj, 'isoformat') else str(obj)
    elif isinstance(obj, pd.Timedelta):
        return str(obj)
    elif obj is pd.NaT or obj is pd.NA:
        return None
    elif isinstance(obj, np.datetime64):
        # 如果是 datetime64 类型且不是 NaT，则转换为字符串
        if str(obj) != 'NaT':
            return str(obj)
        else:
            return None
    elif isinstance(obj, np.ndarray) and np.issubdtype(obj.dtype, np.datetime64):
        return [str(item) if str(item) != 'NaT' else None for item in obj.tolist()]
    else:
        # 对于其他类型，只处理pandas的NA值
        if hasattr(pd, 'isna') and pd.isna(obj) and obj is not None:
            return None
        return obj

def get_analyst_cached_data(cache_key, cache_duration=None):
    """从分析师数据缓存获取数据"""
    # 为了调试，我们添加一些日志
    cached_data = cache_system.get_cached_data(cache_key, 'analyst', cache_duration)
    if cached_data is not None:
        logger.debug(f"从缓存获取数据，缓存键: {cache_key}")
    else:
        logger.debug(f"缓存未命中，缓存键: {cache_key}")
    return cached_data


def set_analyst_cache_data(cache_key, data, cache_duration=None):
    """设置分析师数据缓存"""
    processed_data = _convert_dates_to_strings(data)
    cache_system.set_cache_data(cache_key, processed_data, 'analyst', cache_duration)
    logger.debug(f"数据已缓存，缓存键: {cache_key}")

def save_analyst_history_data(stock_code, date, analyst_count):
    """保存分析师历史数据到长期存储"""
    try:
        # 构造唯一键
        key = f"analyst_history:{stock_code}:{date}"
        data = {
            "stock_code": stock_code,
            "date": date,
            "analyst_count": analyst_count
        }
        # 存储到长期存储系统，永不过期
        from cache_with_database import store_long_term_data
        result = store_long_term_data(key, data, "analyst", None)
        if result:
            logger.info(f"分析师历史数据已保存: {key} (关注数量: {analyst_count})")
        else:
            logger.warning(f"保存分析师历史数据失败: {key}")
        return result
    except Exception as e:
        logger.error(f"保存分析师历史数据失败: {e}")
        return False



def _fetch_analyst_stocks(analyst_id, analyst_name, indicator="最新跟踪成分股", add_delay=True):
    """辅助函数：获取单个分析师的股票数据，带缓存功能"""
    try:
        # 为单个分析师的数据创建缓存键
        cache_key = f"analyst_stocks_{analyst_id}_{indicator}"
        
        # 首先尝试从缓存获取数据
        cached_data = get_analyst_cached_data(cache_key)
        if cached_data is not None:
            logger.info(f"从缓存获取分析师 {analyst_name}({analyst_id}) 的跟踪股票数据")
            return cached_data, analyst_name, indicator
        
        # 如果缓存中没有数据，则从API获取
        from akshare import stock_analyst_detail_em
        if add_delay:
            time.sleep(0.1)  # 避免请求过快
        analyst_detail_df = stock_analyst_detail_em(analyst_id=analyst_id, indicator=indicator)
        analyst_stocks = analyst_detail_df.to_dict('records')
        
        # 将获取到的数据存入缓存
        set_analyst_cache_data(cache_key, analyst_stocks)
        
        logger.info(f"!akshare!分析师 {analyst_name}({analyst_id}) 获取到 {len(analyst_stocks)} 只 {indicator} 股票")
        return analyst_stocks, analyst_name, indicator
    except Exception as e:
        logger.warning(f"获取分析师 {analyst_name}({analyst_id}) 的跟踪股票数据时出错: {str(e)}")
        return [], analyst_name, indicator


def get_analyst_rank_data(period="2026"):
    """
    获取分析师排行榜数据
    :param period: 时间周期，固定返回2025年数据，参数没用
    :return: 分析师排行榜数据
    """
    year = datetime.today().year
    cache_key = f"analyst_rank_{year}"
    cached_data = get_analyst_cached_data(cache_key)
    if cached_data is not None:
        logger.info(f"从缓存返回分析师 2025 年数据")
        return cached_data

    try:
        logger.info(f"开始获取分析师 2025 年排行榜数据")
        # 使用akshare获取分析师排行榜数据
        df = ak.stock_analyst_rank_em(year=year)
        analyst_rank_data = df.to_dict('records')
        set_analyst_cache_data(cache_key, analyst_rank_data, cache_duration=24*3600)
        logger.info(f"!akshare!获取到 {len(analyst_rank_data)} 条分析师排行榜数据")
        return analyst_rank_data
    except Exception as e:
        logger.error(f"获取分析师 2025 年排行榜数据时出错: {str(e)}")
        return []


def _get_combined_analyst_data(top_analysts=50, top_stocks=50, period="3个月"):
    """
    组合函数：一次性获取分析师重点关注股票和最新跟踪成份股数据，避免重复获取排行榜数据
    :param top_analysts: 前N名分析师，默认20
    :param top_stocks: 返回前N只重点关注股票，默认50
    :param period: 时间周期，默认"3个月"
    :return: 包含重点关注股票和最新跟踪数据的字典
    """

    combined_cache_key = f"combined_analyst_data_{period}_{top_analysts}_{top_stocks}"
    # 检查组合缓存
    cached_data = get_analyst_cached_data(combined_cache_key)
    if cached_data is not None:
        logger.info(f"从缓存返回组合分析师数据")
        return cached_data

    try:
        logger.info(f"开始获取组合分析师数据（前{top_analysts}名分析师，前{top_stocks}只股票）")
        analyst_rank_data = get_analyst_rank_data("2026")
        if not analyst_rank_data:
            logger.warning("未能获取分析师排行榜数据")
            return {'top_focus_stocks': [], 'latest_tracking': []}


        # 按指定周期的收益率排序
        if period == "2025年":
            analyst_rank_data.sort(key=lambda x: float(x.get('2025年收益率', 0) or 0), reverse=True)
        elif period == "3个月":
            analyst_rank_data.sort(key=lambda x: float(x.get('3个月收益率', 0) or 0), reverse=True)
        elif period == "6个月":
            analyst_rank_data.sort(key=lambda x: float(x.get('6个月收益率', 0) or 0), reverse=True)
        elif period == "12个月":
            analyst_rank_data.sort(key=lambda x: float(x.get('12个月收益率', 0) or 0), reverse=True)
        else:
            analyst_rank_data.sort(key=lambda x: float(x.get('3个月收益率', 0) or 0), reverse=True)

        total_analysts = len(analyst_rank_data)
        top_analysts_data = analyst_rank_data[:top_analysts]
        logger.info(f"获取到前{top_analysts}名分析师数据，共{total_analysts}名分析师可用")

        # 统计所有分析师的最新跟踪成份股，统计出现次数
        stock_counter = {}
        all_latest_tracking = []

        # 串行处理每个分析师的数据
        processed_analyst_count = 0 # 统计实际处理的分析师数量
        for idx, analyst in enumerate(top_analysts_data, 1):
            indicator="最新跟踪成分股"
            analyst_name = analyst.get('分析师名称', '')
            analyst_id = analyst.get('分析师ID', '')
            # 串行获取单个分析师的股票数据
            analyst_stocks, _, _ = _fetch_analyst_stocks(analyst_id, analyst_name, indicator)
            logger.info(f"分析师 {analyst_name}({analyst_id}) 获取到 {len(analyst_stocks)} 只跟踪股票")
            for stock in analyst_stocks:
                stock_code = stock.get('股票代码', '')
                stock_name = stock.get('股票名称', '')
                if stock_code and stock_name:
                    # 标准化股票代码和名称，确保准确统计
                    stock_code = stock_code.strip().upper()  # 标准化股票代码
                    stock_name = stock_name.strip()  # 标准化股票名称

                    # 统计股票出现次数（被多少个分析师关注）- 用于重点关注股票
                    if stock_code in stock_counter:
                        stock_counter[stock_code]['analyst_count'] += 1
                        # 收集价格信息
                        trade_price_str = stock.get('成交价格(前复权)', '')
                        latest_price_str = stock.get('最新价格', '')

                        if trade_price_str and trade_price_str != '' and trade_price_str != '--':
                            try:
                                trade_price = float(trade_price_str)
                                stock_counter[stock_code]['trade_prices'].append(trade_price)
                            except ValueError:
                                pass  # 如果无法转换为数字则跳过

                        if latest_price_str and latest_price_str != '' and latest_price_str != '--' and not stock_counter[stock_code]['latest_price']:
                            try:
                                stock_counter[stock_code]['latest_price'] = float(latest_price_str)
                            except ValueError:
                                # 如果无法转换为数字，则设置为None，避免前端出现类型错误
                                stock_counter[stock_code]['latest_price'] = None

                    else:
                        # 初始化股票统计信息
                        stock_info_dict = {
                            'analyst_count': 1,
                            'stock_name': stock_name,
                            'stock_code': stock_code,
                            'first_seen': stock,
                            'trade_prices': [],
                            'latest_price': '',
                            'avg_price': 0,
                            'max_price': 0,
                            'min_price': 0
                        }

                        # 收集价格信息
                        trade_price_str = stock.get('成交价格(前复权)', '')
                        latest_price_str = stock.get('最新价格', '')

                        if trade_price_str and trade_price_str != '' and trade_price_str != '--':
                            try:
                                trade_price = float(trade_price_str)
                                stock_info_dict['trade_prices'].append(trade_price)
                            except ValueError:
                                pass  # 如果无法转换为数字则跳过

                        if latest_price_str and latest_price_str != '' and latest_price_str != '--':
                            try:
                                stock_info_dict['latest_price'] = float(latest_price_str)
                            except ValueError:
                                # 如果无法转换为数字，则设置为None，避免前端出现类型错误
                                stock_info_dict['latest_price'] = None

                        stock_counter[stock_code] = stock_info_dict

                    # 为最新跟踪数据添加额外字段
                    stock_info_latest = stock.copy()
                    stock_info_latest['analyst_name'] = analyst_name
                    stock_info_latest['analyst_rank'] = idx
                    stock_info_latest['analyst_industry'] = analyst.get('行业') or '未知'
                    stock_info_latest['analyst_stocks_num'] = analyst.get('成分股个数') or 0
                    stock_info_latest['analyst_total_return'] = analyst.get('2025年收益率') or ''

                    if period == "3个月":
                        stock_info_latest['analyst_period_return'] = analyst.get('3个月收益率') or ''
                    elif period == "6个月":
                        stock_info_latest['analyst_period_return'] = analyst.get('6个月收益率') or ''
                    elif period == "12个月":
                        stock_info_latest['analyst_period_return'] = analyst.get('12个月收益率') or ''
                    all_latest_tracking.append(stock_info_latest)
            processed_analyst_count += 1

        latest_unique_stocks = len(stock_counter)
        latest_focus_stocks = len([s for s in stock_counter.values() if s['analyst_count'] > 1])
        logger.info(f"实际处理了 {processed_analyst_count} 个分析师的数据")
        logger.info(f"统计到 {latest_unique_stocks} 只唯一股票，其中被多个分析师关注的股票有 {latest_focus_stocks} 只")
        logger.info(f"获取到最新跟踪共{len(all_latest_tracking)}条记录")

        # 计算每只股票的统计信息并按分析师关注数量排序
        for stock_code, stock_info in stock_counter.items():
            if stock_info['trade_prices']:
                avg_trade_price = sum(stock_info['trade_prices']) / len(stock_info['trade_prices'])
                max_trade_price = max(stock_info['trade_prices'])
                min_trade_price = min(stock_info['trade_prices'])
            else:
                avg_trade_price = 0
                max_trade_price = 0
                min_trade_price = 0

            # 更新股票信息，包含价格统计
            stock_info['avg_price'] = round(avg_trade_price, 2) if avg_trade_price != 0 else 0
            stock_info['max_price'] = max_trade_price
            stock_info['min_price'] = min_trade_price
            stock_info['latest_price'] = stock_info['latest_price']

        # 按分析师关注数量排序，取前top_stocks只股票
        sorted_stocks = sorted(stock_counter.values(), key=lambda x: x['analyst_count'], reverse=True)
        top_focus_stocks = sorted_stocks[:top_stocks]
        logger.info(f"获取到分析师重点关注股票 {len(top_focus_stocks)} 只")

        # 保存历史数据 - 只在默认参数时保存（3个月、50只股票、20名分析师）
        from datetime import date
        today = date.today().strftime('%Y-%m-%d')
        # 只在默认参数组合时保存历史数据
        if top_analysts == 50 and top_stocks == 50 and period == "3个月":
            for stock_info in top_focus_stocks:
                stock_code = stock_info['stock_code']
                analyst_count = stock_info['analyst_count']
                save_analyst_history_data(stock_code, today, analyst_count)
            logger.info("历史分析师数据保存完成（默认参数组合）")

        result = {
            'top_focus_stocks': top_focus_stocks,
            'latest_tracking': all_latest_tracking,
            'total_analysts_processed': processed_analyst_count,
            'latest_focus_stocks': latest_focus_stocks,
            'latest_unique_stocks': latest_unique_stocks
        }

        # 设置组合缓存，缓存时间适当延长
        set_analyst_cache_data(combined_cache_key, result)
        logger.info(f"组合分析师数据获取完成，共{len(top_focus_stocks)}只重点股票，{len(all_latest_tracking)}条最新跟踪记录")
        return result

    except Exception as e:
        logger.error(f"获取组合分析师数据时出错: {str(e)}")
        import traceback
        traceback.print_exc()
        return {'top_focus_stocks': [], 'latest_tracking': []}


def get_analyst_focus_stocks(top_analysts=50, top_stocks=50, period="3个月"):
    """
    获取分析师重点关注股票（前50个），通过获取前20名分析师的最新跟踪成份股后统计得出
    :param top_analysts: 前N名分析师，默认20
    :param top_stocks: 返回前N只重点关注股票，默认50
    :param period: 时间周期，默认"3个月"
    :return: 分析师重点关注股票列表
    """
    cache_key = f"analyst_focus_stocks_{period}_{top_analysts}"
    cached_data = get_analyst_cached_data(cache_key)
    if cached_data is not None:
        logger.info(f"从缓存返回分析师重点关注股票数据")
        return cached_data

    # 使用组合函数获取数据，然后只返回关注股票部分
    combined_data = _get_combined_analyst_data(top_analysts, top_stocks, period)
    result = {
        'top_focus_stocks': combined_data.get('top_focus_stocks', []),
        'total_analysts_processed': combined_data.get('total_analysts_processed', 0),
        'latest_unique_stocks': combined_data.get('latest_unique_stocks', 0),
        'latest_focus_stocks': combined_data.get('latest_focus_stocks', 0)
    }

    set_analyst_cache_data(cache_key, result)
    logger.info(f"分析师重点关注股票数据获取完成，共{len(result['top_focus_stocks'])}只重点股票")
    return result


def get_analyst_latest_tracking(top_analysts=50, top_stocks=50, period="3个月"):
    """
    获取最新跟踪成份股（前20名分析师），获取前20名分析师的最新跟踪成份股数据
    :param top_analysts: 前N名分析师，默认20
    :param top_stocks: 前N只股票，默认50
    :param period: 时间周期，默认"3个月"
    :return: 最新跟踪成份股数据
    """
    cache_key = f"latest_analyst_tracking_{period}_{top_analysts}_{top_stocks}"
    cached_data = get_analyst_cached_data(cache_key)
    if cached_data is not None:
        logger.info(f"从缓存返回最新跟踪成份股数据")
        return cached_data

    # 使用组合函数获取数据，然后只返回最新跟踪部分
    combined_data = _get_combined_analyst_data(top_analysts, top_stocks, period) # 使用传入的top_stocks参数
    latest_tracking = combined_data.get('latest_tracking', [])

    set_analyst_cache_data(cache_key, latest_tracking)
    logger.info(f"最新跟踪成份股数据获取完成，共{len(latest_tracking)}条记录")
    return latest_tracking


def get_analyst_combined_data(top_analysts=50, top_stocks=50, period="3个月"):
    """
    为报告生成获取完整的分析师数据（包含重点关注股票和最新跟踪数据）
    :param top_analysts: 前N名分析师，默认20
    :param top_stocks: 返回前N只重点关注股票，默认50
    :param period: 时间周期，默认"3个月"
    :return: 包含重点关注股票和最新跟踪数据的字典
    """
    # 使用内部组合函数获取完整数据
    combined_data = _get_combined_analyst_data(top_analysts, top_stocks, period)
    return combined_data


def get_analyst_updated_stocks(days=30, indicator="最新跟踪成分股"):
    """
    获取最近更新的股票列表
    :param days: 天数阈值，只返回此天数内更新的股票
    :return: 最近更新的股票列表
    """
    from datetime import datetime, timedelta
    date_threshold = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
    
    cache_key = f"recently_updated_stocks_{days}_{indicator}"
    cached_data = get_analyst_cached_data(cache_key)
    if cached_data is not None:
        logger.info(f"从缓存返回最近更新的股票数据，天数阈值: {days}天, 指标: {indicator}")
        return cached_data

    try:
        logger.info(f"开始获取最近更新的股票数据，天数阈值: {days}天, 指标: {indicator}")
        # 获取分析师排行榜数据
        analyst_rank_data = get_analyst_rank_data(period="2026")

        # 筛选在指定日期之后更新的分析师
        filtered_analysts = []
        for analyst in analyst_rank_data:
            update_date_str = analyst.get('更新日期', '')
            if update_date_str:
                try:
                    # 将字符串日期转换为datetime对象进行比较
                    if isinstance(update_date_str, str):
                        # 解析日期字符串
                        try:
                            update_date = datetime.strptime(update_date_str, '%Y-%m-%d').date()
                        except ValueError:
                            # 如果格式不是YYYY-MM-DD，尝试其他可能的格式
                            try:
                                update_date = datetime.strptime(update_date_str, '%Y-%m-%d %H:%M:%S').date()
                            except ValueError:
                                logger.warning(f"无法解析日期格式: {update_date_str}")
                                continue
                    else:
                        update_date = update_date_str  # 如果已经是date/datetime对象
                        
                    threshold_date = datetime.strptime(date_threshold, '%Y-%m-%d').date()
                    
                    # 比较日期，只保留指定日期之后的记录
                    if update_date >= threshold_date:
                        filtered_analysts.append(analyst)
                except Exception as e:
                    logger.warning(f"日期比较出错: {str(e)}，分析师: {analyst.get('分析师名称', '')}，更新日期: {update_date_str}")

        logger.info(f"筛选出 {len(filtered_analysts)} 位在 {date_threshold} 之后更新的分析师, indicator: {indicator}")

        # 获取这些分析师的所有股票
        all_recent_stocks = []
        for analyst in filtered_analysts:
            analyst_name = analyst.get('分析师名称', '')
            analyst_id = analyst.get('分析师ID', '')
            if analyst_id:
                try:
                    # 获取该分析师的所有股票数据
                    #indicator="最新跟踪成分股"
                    analyst_stocks, _, _ = _fetch_analyst_stocks(analyst_id, analyst_name, indicator)
                    for stock in analyst_stocks:
                        # 检查股票的调入日期是否也满足条件
                        entry_date_str = stock.get('最新评级日期', '')
                        if entry_date_str:
                            try:
                                # 将字符串日期转换为datetime对象进行比较
                                if isinstance(entry_date_str, str):
                                    # 解析日期字符串
                                    try:
                                        entry_date = datetime.strptime(entry_date_str, '%Y-%m-%d').date()
                                    except ValueError:
                                        # 如果格式不是YYYY-MM-DD，尝试其他可能的格式
                                        try:
                                            entry_date = datetime.strptime(entry_date_str, '%Y-%m-%d %H:%M:%S').date()
                                        except ValueError:
                                            logger.warning(f"无法解析日期格式: {entry_date_str}")
                                            continue
                                else:
                                    entry_date = entry_date_str  # 如果已经是date/datetime对象
                                    
                                threshold_date = datetime.strptime(date_threshold, '%Y-%m-%d').date()
                                
                                # 比较日期，只保留指定日期之后的记录
                                if entry_date >= threshold_date:
                                    stock['analyst_name'] = analyst_name
                                    stock['analyst_period_3m_return'] = analyst.get('3个月收益率', '')
                                    stock['analyst_period_6m_return'] = analyst.get('6个月收益率', '')
                                    stock['analyst_period_12m_return'] = analyst.get('12个月收益率', '')
                                    stock['analyst_industry'] = analyst.get('行业', 'Unknown')
                                    all_recent_stocks.append(stock)
                            except Exception as e:
                                logger.warning(f"股票日期比较出错: {str(e)}，股票: {stock.get('股票名称', '')}，评级日期: {entry_date_str}")
                except Exception as e:
                    logger.warning(f"获取分析师 {analyst_name}({analyst_id}) {indicator}  的股票数据时出错: {str(e)}")
                    continue

        logger.info(f"获取到 {len(all_recent_stocks)} 只符合条件 {indicator}  的最近更新股票")

        # 设置缓存
        set_analyst_cache_data(cache_key, all_recent_stocks)
        return all_recent_stocks

    except Exception as e:
        logger.error(f"获取最近更新的股票数据时出错: {str(e)}")
        import traceback
        traceback.print_exc()
        return []


def get_analyst_history_tracking(stock_code, days=360):
    """从长期存储中获取股票历史分析师跟踪数据"""
    try:
        from datetime import datetime, timedelta
        from cache_with_database import get_module_long_term_data
        import json
        
        # 计算日期范围
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=days)
        
        # 获取该股票的所有历史数据
        all_data = get_module_long_term_data("analyst")
        
        # 筛选指定股票和日期范围的数据
        filtered_data = []
        for item in all_data:
            data = item['data']
            if (data.get('stock_code') == stock_code and 
                data.get('date') and 
                start_date <= datetime.strptime(data['date'], '%Y-%m-%d').date() <= end_date):
                filtered_data.append(data)
        
        # 按日期排序
        filtered_data.sort(key=lambda x: x['date'])
        
        # 提取日期和数量
        dates = [item['date'] for item in filtered_data]
        counts = [item['analyst_count'] for item in filtered_data]
        
        logger.info(f"获取到 {len(dates)} 条 {stock_code} 的历史分析师跟踪数据")
        return {
            "dates": dates,
            "analyst_counts": counts
        }
    except Exception as e:
        logger.error(f"获取股票 {stock_code} 历史数据失败: {e}")
        return None




if __name__ == "__main__":
    print("测试分析师数据获取功能...")
    print("\n1. 测试获取分析师排行榜数据:")
    try:
        # rank_data = get_analyst_rank_data("3个月")
        # print(f"获取到 {len(rank_data)} 条分析师排行榜数据")
        # if rank_data:
        #     print(f"示例数据: {rank_data[0] if len(rank_data) > 0 else '无数据'}")
        
        
        # print(f"获取到 {len(combined_data.get('top_focus_stocks', []))} 只重点关注股票")
        # print(f"获取到 {len(combined_data.get('latest_tracking', []))} 条最新跟踪记录")

        # print(f"top_focus_stocks: combined_data.get('top_focus_stocks', [])")
        # #print(f"latest_tracking: combined_data.get('latest_tracking', [])")

        # if combined_data.get('top_focus_stocks'):
        #     print(f"示例数据: {combined_data['top_focus_stocks'][0] if len(combined_data['top_focus_stocks']) > 0 else '无数据'}")
        
        # print("\n3. 测试获取分析师重点关注股票:")
        # focus_stocks = get_analyst_focus_stocks(20, 7, "3个月")  # 减少数量以便快速测试
        # print(f"获取到 {len(focus_stocks.get('top_focus_stocks', []))} 只重点关注股票")

        # for stock in focus_stocks.get('top_focus_stocks', []):
        #     print(stock)

        # if focus_stocks.get('top_focus_stocks'):
        #     print(f"示例数据: {focus_stocks['top_focus_stocks'][0] if len(focus_stocks['top_focus_stocks']) > 0 else '无数据'}")
        
        # print("\n4. 测试获取最新跟踪成份股:")
        # latest_tracking = get_latest_analyst_tracking(5, "3个月")  # 减少数量以便快速测试
        # print(f"获取到 {len(latest_tracking)} 条最新跟踪记录")
        # if latest_tracking:
        #     print(f"示例数据: {latest_tracking[0] if len(latest_tracking) > 0 else '无数据'}")
        #all_recent_stocks = get_analyst_updated_stocks(days=30, indicator="历史跟踪成分股")
        #print(f"获取到: {all_recent_stocks}")
        # print("\n5. 测试获取股票同行比较数据:")
        # stock_symbol = "SZ000408"
        # #stock_symbol = "SZ000895"
        # df = ak.stock_zh_growth_comparison_em(symbol=stock_symbol)
        # result = df.to_dict('records')
        # print(f"result: {result}")

        result = get_analyst_combined_data(20, 50, '3个月')
        print(f"result: {result}")

        #peer_comparison = get_stock_growth_comparison(stock_symbol)
        #print(f"获取到股票 {stock_symbol} 的同行比较数据: {peer_comparison}")

    except Exception as e:
        logger.error(f"测试分析师数据时出错: {str(e)}")
        print(f"测试分析师数据时出错: {str(e)}")
