from datetime import datetime, timedelta
import akshare as ak
import pandas as pd
from logger_config import logger


# 使用混合缓存（内存+数据库），以SQLite作为二级缓存
from cache_with_database import cache_system

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
    elif obj is pd.NaT:
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


def get_industry_cached_data(cache_key, cache_duration=None):
    """
    从行业数据缓存获取数据
    :param cache_key: 缓存键
    :param cache_duration: 缓存有效时间（秒），如果为None则使用环境变量配置
    :return: 缓存的数据或None
    """
    return cache_system.get_cached_data(cache_key, 'industry', cache_duration)

def set_industry_cache_data(cache_key, data, cache_duration=None):
    """
    设置行业数据缓存
    :param cache_key: 缓存键
    :param data: 要缓存的数据
    :param cache_duration: 缓存有效时间（秒），如果为None则使用默认值
    """
    # 处理数据中的日期类型，确保可以JSON序列化
    processed_data = _convert_dates_to_strings(data)
    cache_system.set_cache_data(cache_key, processed_data, 'industry', cache_duration)
    #logger.info(f"行业数据已缓存: {cache_key}")


def get_industry_names():
    """
    获取行业名称列表
    :return: 行业名称列表
    """
    cache_key = "industry_names"
    cached_data = get_industry_cached_data(cache_key)
    if cached_data is not None:
        #logger.info("从缓存返回行业名称列表")
        return cached_data

    try:
        logger.info("开始获取行业名称列表")
        # 使用akshare获取行业名称
        df = ak.stock_board_industry_name_em()
        industry_list = df.to_dict('records')
        set_industry_cache_data(cache_key, industry_list, cache_duration=1*24*3600) 
        logger.info(f"获取到 {len(industry_list)} 个行业名称")
        return industry_list
    except Exception as e:
        logger.error(f"获取行业名称列表时出错: {str(e)}")
        return []


def get_industry_constituents(industry_name):
    """
    获取行业成份股列表
    :param industry_name: 行业名称
    :return: 行业成份股列表
    """
   
    cache_key = f"industry_constituents_{industry_name}"
    cached_data = get_industry_cached_data(cache_key) 
    if cached_data is not None:
        #logger.info(f"从缓存返回行业 {industry_name} 的成份股列表")
        return cached_data

    try:
        logger.info(f"开始获取行业 {industry_name} 的成份股列表")
        # 获取行业成份股数据
        df = ak.stock_board_industry_cons_em(symbol=industry_name)
        # 处理NaN值，将其转换为None
        df = df.where(pd.notna(df), None)
        constituents = df.to_dict('records')
        set_industry_cache_data(cache_key, constituents, cache_duration=6*24*60*60)
        logger.info(f"获取到行业 {industry_name} {len(constituents)} 个成份股")
        return constituents
    except Exception as e:
        logger.error(f"获取行业 {industry_name} 成份股列表时出错: {str(e)}")
        return []

###所有行业的指定天数内的涨幅排行榜
#1.获得所有行业的名称列表
#2.获得行业的历史数据并按涨幅排列
def get_industry_ranking(period="30"):
    """
    获取行业涨跌幅排行
    :param period: 时间周期（天数），如1, 30, 60, 120, 365
    :return: 行业涨跌幅排行列表
    """
    
    cache_key = f"industry_ranking_{period}"
    cached_data = get_industry_cached_data(cache_key)
    if cached_data is not None:
        #logger.info(f"从缓存返回行业 {period}天 涨跌幅排行")
        return cached_data

    try:
        logger.info(f"开始获取行业 {period}天 涨跌幅排行")

        # 使用akshare获取行业板块信息
        ranking_data = []
        industry_list = get_industry_names()
        
        # 获取当前日期
        from datetime import datetime, timedelta
        current_date = datetime.now()
        end_date = current_date.strftime('%Y%m%d')
        start_date = (current_date - timedelta(days=int(period))).strftime('%Y%m%d')
        
        # 对于最近1天，我们使用前一天作为开始日期，今天作为结束日期
        if period == "1":
            start_date = (current_date - timedelta(days=1)).strftime('%Y%m%d')
            end_date = current_date.strftime('%Y%m%d')
        
        for industry in industry_list:
            industry_name = industry.get('板块名称', '')
            if not industry_name:
                continue
                
            try:
                # 获取该行业的历史数据，指定开始和结束日期
                if period == "1":
                    # 对于最近1天，我们先获取近期的数据，然后筛选
                    # 由于akshare的API限制，我们获取最近3天的数据，然后选择最近的2天
                    recent_start_date = (current_date - timedelta(days=3)).strftime('%Y%m%d')
                    df = get_single_industry_history(industry_name, recent_start_date, end_date)
                else:
                    df = get_single_industry_history(industry_name, start_date, end_date)
                
                if df.empty:
                    continue
                    
                # 按日期排序
                df = df.sort_values(by='日期').reset_index(drop=True)
                
                # 处理NaN值，将其转换为None
                df = df.where(pd.notna(df), None)
                
                # 对于最近1天的特殊处理
                if period == "1":
                    # 选择最近的两个日期数据进行比较
                    unique_dates = df['日期'].unique()
                    if len(unique_dates) >= 2:
                        # 获取最近两天的数据
                        last_two_dates = unique_dates[-2:] # 最近的两个日期
                        period_data = df[
                            df['日期'].isin(last_two_dates)
                        ].copy()
                        
                        if len(period_data) >= 2:
                            first_record = period_data.iloc[0]  # 前一天的数据
                            last_record = period_data.iloc[-1]  # 最新一天的数据
                        else:
                            continue  # 数据不足，跳过
                    elif len(unique_dates) == 1:
                        # 只有一天数据，无法计算涨跌幅，跳过
                        continue
                    else:
                        continue # 没有数据，跳过
                else:
                    # 对于其他周期，选择周期内的数据
                    if len(df) < 2:
                        continue
                        
                    # 获取周期内的第一条和最后一条数据
                    start_idx = max(0, len(df) - int(period))
                    period_data = df.iloc[start_idx:]
                    
                    if len(period_data) < 2:
                        continue
                        
                    first_record = period_data.iloc[0]  # 周期内较早的数据
                    last_record = period_data.iloc[-1]  # 周期内最新的数据
                
                # 检查收盘价是否为None
                if first_record['收盘'] is None or last_record['收盘'] is None:
                    continue
                    
                start_price = float(first_record['收盘'])
                end_price = float(last_record['收盘'])
                
                if start_price == 0:
                    continue
                    
                change_pct = round(((end_price - start_price) / start_price) * 100, 2)
                
                ranking_data.append({
                    'industry_name': industry_name,
                    'start_price': start_price,
                    'end_price': end_price,
                    'change_pct': change_pct,
                    'start_date': str(first_record['日期']),
                    'end_date': str(last_record['日期']),
                    'volume': float(last_record['成交量']) if last_record['成交量'] and last_record['成交量'] != '-' else 0
                })
            except Exception as e:
                logger.warning(f"获取行业 {industry_name} 的历史数据时出错: {str(e)}")
                continue
        
        # 按涨跌幅排序，处理None值
        ranking_data.sort(key=lambda x: (x['change_pct'] is None, x['change_pct']), reverse=True)
        set_industry_cache_data(cache_key, ranking_data) 
        logger.info(f"获取到 {len(ranking_data)} 个行业的 {period}天 涨跌幅排行数据")
        return ranking_data
    except Exception as e:
        logger.error(f"获取行业 {period}天 涨跌幅排行时出错: {str(e)}")
        return []


def get_single_industry_history(industry_name, start_date, end_date):
    """
    获取单个行业的历史数据，用于缓存优化
    :param industry_name: 行业名称
    :param start_date: 开始日期
    :param end_date: 结束日期
    :param period: 时间周期（用于缓存键）
    :return: 行业历史数据DataFrame
    """
    cache_key = f"single_industry_history_{industry_name}_{start_date}_{end_date}"
    cached_data = get_industry_cached_data(cache_key)
    if cached_data is not None:
        logger.debug(f"从缓存返回行业 {industry_name} 的历史数据")
        # 将缓存的列表数据转换为DataFrame
        import pandas as pd
        if cached_data:
            return pd.DataFrame(cached_data)
        else:
            return pd.DataFrame()    
    try:
        # 获取该行业的历史数据，指定开始和结束日期
        df = ak.stock_board_industry_hist_em(symbol=industry_name, start_date=start_date, end_date=end_date, adjust="")
        # 缓存原始数据
        set_industry_cache_data(cache_key, df.to_dict('records'))
        return df
    except Exception as e:
        logger.error(f"获取行业 {industry_name} 的历史数据时出错: {str(e)}")
        import pandas as pd
        return pd.DataFrame()


def get_multiple_industry_history(industry_names, period="365"):
    """
    获取多个行业的历史数据，用于图表展示
    :param industry_names: 行业名称列表
    :param period: 时间周期（天数），如30, 90, 180, 365, 1825
    :return: 格式化的图表数据 {dates: [], series: {行业名: [数据]}}
    """
    if not industry_names or len(industry_names) == 0:
        logger.warning("未提供行业名称列表")
        return None
    
    try:
        logger.info(f"开始获取 {len(industry_names)} 个行业的历史数据，周期: {period}天")
        
        # 计算日期范围
        current_date = datetime.now()
        end_date = current_date.strftime('%Y%m%d')
        start_date = (current_date - timedelta(days=int(period))).strftime('%Y%m%d')
        
        # 存储所有行业的数据
        industry_data_dict = {}
        all_dates_set = set()
        
        # 获取每个行业的历史数据
        for industry_name in industry_names:
            try:
                df = get_single_industry_history(industry_name=industry_name,start_date=start_date,end_date=end_date)
                if df.empty:
                    logger.warning(f"行业 {industry_name} 没有历史数据")
                    continue
                
                # 确保日期列是字符串格式
                df['日期'] = pd.to_datetime(df['日期']).dt.strftime('%Y-%m-%d')
                
                # 存储该行业的数据
                industry_data_dict[industry_name] = df
                
                # 收集所有日期
                all_dates_set.update(df['日期'].tolist())
                
                logger.info(f"成功获取行业 {industry_name} 的 {len(df)} 条数据")
                
            except Exception as e:
                logger.error(f"获取行业 {industry_name} 数据时出错: {str(e)}")
                continue
        
        if not industry_data_dict:
            logger.error("没有成功获取任何行业数据")
            return None
        
        # 对所有日期排序
        all_dates = sorted(list(all_dates_set))
        logger.info(f"共有 {len(all_dates)} 个交易日")
        
        # 构建返回数据结构
        chart_data = {
            "dates": all_dates,
            "series": {}
        }
        
        # 为每个行业构建完整的数据序列
        for industry_name, df in industry_data_dict.items():
            # 创建日期到收盘价的映射
            date_price_map = dict(zip(df['日期'], df['收盘']))
            
            # 构建完整的价格序列（对缺失日期使用前一天的价格）
            price_series = []
            last_valid_price = None
            
            # 首先找到起始价格作为基准
            base_price = None
            for date in all_dates:
                if date in date_price_map and date_price_map[date] is not None and date_price_map[date] != 'None':
                    base_price = float(date_price_map[date])
                    break # 使用第一个可用的价格作为基准
            
            for date in all_dates:
                if date in date_price_map:
                    price = date_price_map[date]
                    if price is not None and price != 'None':
                        current_price = float(price)
                        last_valid_price = current_price
                        
                        # 计算相对于起始价格的增长率
                        if base_price is not None and base_price != 0:
                            growth_rate = ((current_price - base_price) / base_price) * 100
                            price_series.append(round(growth_rate, 2))
                        else:
                            price_series.append(None)
                    elif last_valid_price is not None:
                        # 使用前向填充
                        if base_price is not None and base_price != 0:
                            growth_rate = ((last_valid_price - base_price) / base_price) * 100
                            price_series.append(round(growth_rate, 2))
                        else:
                            price_series.append(None)
                    else:
                        price_series.append(None)
                elif last_valid_price is not None:
                    # 使用前向填充
                    if base_price is not None and base_price != 0:
                        growth_rate = ((last_valid_price - base_price) / base_price) * 100
                        price_series.append(round(growth_rate, 2))
                    else:
                        price_series.append(None)
                else:
                    price_series.append(None)
            
            chart_data["series"][industry_name] = price_series
        
        logger.info(f"成功生成 {len(chart_data['series'])} 个行业的图表数据")
        return chart_data

    except Exception as e:
        logger.error(f"生成行业图表数据时出错: {str(e)}")
        return None


def format_chart_data_for_echarts(chart_data):
    """
    将图表数据格式化为ECharts所需的格式
    :param chart_data: 原始图表数据
    :return: ECharts格式的数据
    """
    if not chart_data:
        return None
    
    try:
        echarts_data = {
            "xAxis": {
                "data": chart_data["dates"]
            },
            "yAxis": {
                "name": "增长率 (%)",
                "axisLabel": {
                    "formatter": "{value} %"
                }
            },
            "series": []
        }
        
        # 为每个行业创建series配置
        colors = [
            '#ff4d4f', '#1890ff', '#52c41a', '#faad14', '#722ed1',
            '#eb2f96', '#13c2c2', '#fa8c16', '#a0d911', '#2f54eb'
        ]
        
        for idx, (industry_name, data) in enumerate(chart_data["series"].items()):
            series_config = {
                "name": industry_name,
                "type": "line",
                "data": data,
                "smooth": True,
                "symbol": "none",
                "lineStyle": {
                    "width": 2,
                    "color": colors[idx % len(colors)]
                }
            }
            echarts_data["series"].append(series_config)
        
        return echarts_data
        
    except Exception as e:
        logger.error(f"格式化ECharts数据时出错: {str(e)}")
        return None




if __name__ == "__main__":
    # print("测试行业数据获取功能...")
    # print("\n1. 测试获取行业名称列表:")
    # industry_names = get_industry_names()
    # print(f"获取到 {len(industry_names)} 个行业名称")
    # if industry_names:
    #     print(f"示例数据: {industry_names[0] if len(industry_names) > 0 else '无数据'}")
    
    # print("\n2. 测试获取行业历史数据:")
    # # 从行业列表中取第一个行业进行测试
    # if industry_names:
    #     test_industry = industry_names[0]['板块名称']
    #     print(f"使用行业: {test_industry}")
    #     history_data = get_industry_history(test_industry, "10")  # 使用较短周期以便快速测试
    #     print(f"获取到 {len(history_data)} 条历史数据")
    #     if history_data:
    #         print(f"示例数据: {history_data[0] if len(history_data) > 0 else '无数据'}")
    # else:
    #     print("没有获取到行业名称，跳过历史数据测试")
    
    # print("\n3. 测试获取行业成份股:")
    # if industry_names:
    #     test_industry = industry_names[0]['板块名称']
    #     constituents = get_industry_constituents(test_industry)
    #     print(f"获取到 {len(constituents)} 个成份股")
    #     if constituents:
    #         print(f"示例数据: {constituents[0] if len(constituents) > 0 else '无数据'}")
    # else:
    #     print("没有获取到行业名称，跳过成份股测试")
    
    print("\n4. 测试获取行业涨跌幅排行:")
    ranking_data = get_industry_ranking("30")  # 使用较短周期以便快速测试
    print(f"获取到 {len(ranking_data)} 个行业的涨跌幅排行数据")
    if ranking_data:
        print(f"示例数据: {ranking_data[0] if len(ranking_data) > 0 else '无数据'}")
