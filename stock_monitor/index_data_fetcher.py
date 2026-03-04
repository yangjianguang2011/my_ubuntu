"""
指数数据获取模块
支持A股主要指数的获取和处理
"""
import akshare as ak
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from logger_config import logger
from cache_with_database import get_index_cached_data, set_index_cache_data



#############################sina interface###################

SINA_ALL_INDEX = [
    {"symbol": "sz980018", "name": "卫星通信", "interface": "sina"},
    {"symbol": "sz399434", "name": "数字传媒", "interface": "sina"},
    {"symbol": "sz399971", "name": "中证传媒", "interface": "sina"},
    {"symbol": "sz399654", "name": "深证文化", "interface": "sina"},
    {"symbol": "sz399264", "name": "创业软件", "interface": "sina"},
    {"symbol": "sz980076", "name": "通用航空", "interface": "sina"},
    {"symbol": "sz399959", "name": "军工指数", "interface": "sina"},
    {"symbol": "sz399973", "name": "中证国防", "interface": "sina"},
    {"symbol": "sh000823", "name": "800有色", "interface": "sina"},
    {"symbol": "sz399652", "name": "中创高新", "interface": "sina"},
    {"symbol": "sz399368", "name": "国证军工", "interface": "sina"},
    {"symbol": "sz399397", "name": "国证文化", "interface": "sina"},
    {"symbol": "sz399262", "name": "数字经济", "interface": "sina"},
    {"symbol": "sz399608", "name": "科技100", "interface": "sina"},
    {"symbol": "sz980015", "name": "疫苗生科", "interface": "sina"},
    {"symbol": "sz399615", "name": "深证工业", "interface": "sina"},
    {"symbol": "sz399913", "name": "300医药", "interface": "sina"},
    {"symbol": "sz399808", "name": "中证新能", "interface": "sina"},
    {"symbol": "sh000037", "name": "上证医药", "interface": "sina"},
    {"symbol": "sz399439", "name": "国证油气", "interface": "sina"},
    {"symbol": "sh000906", "name": "中证800", "interface": "sina"},
    {"symbol": "sz399235", "name": "建筑指数", "interface": "sina"},
    {"symbol": "sh000991", "name": "全指医药", "interface": "sina"},
    {"symbol": "sz399643", "name": "创业新兴", "interface": "sina"},
    {"symbol": "sz399007", "name": "深证300", "interface": "sina"},
    {"symbol": "sz399618", "name": "深证医药", "interface": "sina"},
    {"symbol": "sz399995", "name": "基建工程", "interface": "sina"},
    {"symbol": "sz399339", "name": "深证科技", "interface": "sina"},
    {"symbol": "sh000047", "name": "上证全指", "interface": "sina"},
    {"symbol": "sh000065", "name": "上证龙头", "interface": "sina"},
    {"symbol": "sh000001", "name": "上证指数", "interface": "sina"},
    {"symbol": "sz399006", "name": "创业板指", "interface": "sina"},
    {"symbol": "sz399266", "name": "创新能源", "interface": "sina"},
    {"symbol": "sz980016", "name": "医疗健康", "interface": "sina"},
    {"symbol": "sh000121", "name": "医药主题", "interface": "sina"},
    {"symbol": "sz399688", "name": "深成电信", "interface": "sina"},
    {"symbol": "sh000510", "name": "中证A500", "interface": "sina"},
    {"symbol": "sz399613", "name": "深证能源", "interface": "sina"},
    {"symbol": "sz399655", "name": "深证绩效", "interface": "sina"},
    {"symbol": "sz399698", "name": "优势成长", "interface": "sina"},
    {"symbol": "sz399379", "name": "国证基金", "interface": "sina"},
    {"symbol": "sh000139", "name": "上证转债", "interface": "sina"},
    {"symbol": "sz399705", "name": "深证中游", "interface": "sina"},
    {"symbol": "sz399348", "name": "深证价值", "interface": "sina"},
    {"symbol": "sz399312", "name": "国证300", "interface": "sina"},
    {"symbol": "sz399630", "name": "1000成长", "interface": "sina"},
    {"symbol": "sz399412", "name": "国证新能", "interface": "sina"},
    {"symbol": "sz399240", "name": "金融指数", "interface": "sina"},
    {"symbol": "sz399626", "name": "中创成长", "interface": "sina"},
    {"symbol": "sh000075", "name": "医药等权", "interface": "sina"},
    #{"symbol": "sh000070", "name": "能源等权", "interface": "sina"},
    {"symbol": "sz399363", "name": "国证算力", "interface": "sina"},
    {"symbol": "sh000109", "name": "380医药", "interface": "sina"},
    {"symbol": "sh000118", "name": "380价值", "interface": "sina"},
    {"symbol": "sz399933", "name": "中证医药", "interface": "sina"},
    {"symbol": "sz399814", "name": "大农业", "interface": "sina"},
    {"symbol": "sz399234", "name": "水电指数", "interface": "sina"},
    {"symbol": "sz399636", "name": "深证装备", "interface": "sina"},
    {"symbol": "sh000072", "name": "工业等权", "interface": "sina"},
    {"symbol": "sh000034", "name": "上证工业", "interface": "sina"},
    {"symbol": "sz399261", "name": "创业制造", "interface": "sina"},
    #{"symbol": "sz399680", "name": "深成能源", "interface": "sina"},
    {"symbol": "sh000063", "name": "上证周期", "interface": "sina"},
    {"symbol": "sh000016", "name": "上证50", "interface": "sina"},
    {"symbol": "sh000867", "name": "港中小企", "interface": "sina"},
    {"symbol": "sz399812", "name": "养老产业", "interface": "sina"},
    #{"symbol": "sh000986", "name": "全指能源", "interface": "sina"},
    {"symbol": "sz399686", "name": "深成金融", "interface": "sina"},
    {"symbol": "sz399300", "name": "沪深300", "interface": "sina"},
    {"symbol": "sz399259", "name": "创业低碳", "interface": "sina"},
    {"symbol": "sz399293", "name": "创业大盘", "interface": "sina"},
    {"symbol": "sh000032", "name": "上证能源", "interface": "sina"},
    {"symbol": "sz399346", "name": "深证成长", "interface": "sina"},
    {"symbol": "sh000989", "name": "全指可选", "interface": "sina"},
    {"symbol": "sz399619", "name": "深证金融", "interface": "sina"},
    {"symbol": "sz399371", "name": "国证价值", "interface": "sina"},
    {"symbol": "sz399381", "name": "1000能源", "interface": "sina"},
    {"symbol": "sz399365", "name": "国证粮食", "interface": "sina"},
    {"symbol": "sh000827", "name": "中证环保", "interface": "sina"},
    {"symbol": "sz399436", "name": "绿色煤炭", "interface": "sina"},
    {"symbol": "sz399437", "name": "证券龙头", "interface": "sina"},
    {"symbol": "sz399990", "name": "煤炭等权", "interface": "sina"},
    {"symbol": "sz399928", "name": "中证能源", "interface": "sina"},
    {"symbol": "sz399638", "name": "深证环保", "interface": "sina"},
    {"symbol": "sz399669", "name": "深证农业", "interface": "sina"},
    {"symbol": "sz399975", "name": "证券公司", "interface": "sina"},
    {"symbol": "sz399637", "name": "深证地产", "interface": "sina"},
    {"symbol": "sh000122", "name": "农业主题", "interface": "sina"},
    {"symbol": "sh000076", "name": "金融等权", "interface": "sina"},
    {"symbol": "sz399353", "name": "国证物流", "interface": "sina"},
    {"symbol": "sz980028", "name": "龙头家电", "interface": "sina"},
    {"symbol": "sz399622", "name": "深证公用", "interface": "sina"},
    {"symbol": "sz399260", "name": "先进制造", "interface": "sina"},
    {"symbol": "sz399433", "name": "国证交运", "interface": "sina"},
    {"symbol": "sz399241", "name": "地产指数", "interface": "sina"},
    {"symbol": "sz399998", "name": "中证煤炭", "interface": "sina"},
    {"symbol": "sh000992", "name": "全指金融", "interface": "sina"},
    {"symbol": "sh000015", "name": "红利指数", "interface": "sina"},
    {"symbol": "sz399934", "name": "中证金融", "interface": "sina"},
    {"symbol": "sh000074", "name": "消费等权", "interface": "sina"},
    {"symbol": "sh000038", "name": "上证金融", "interface": "sina"},
    {"symbol": "sz399358", "name": "国证环保", "interface": "sina"},
    {"symbol": "sz399983", "name": "地产等权", "interface": "sina"},
    {"symbol": "sz399438", "name": "绿色电力", "interface": "sina"},
    {"symbol": "sz399328", "name": "深证治理", "interface": "sina"},
    {"symbol": "sh000152", "name": "上央红利", "interface": "sina"},
    {"symbol": "sh000036", "name": "上证消费", "interface": "sina"},
    {"symbol": "sz399237", "name": "运输指数", "interface": "sina"},
    {"symbol": "sz399431", "name": "国证银行", "interface": "sina"},
    {"symbol": "sh000134", "name": "上证银行", "interface": "sina"},
    {"symbol": "sz399359", "name": "国证基建", "interface": "sina"},
    {"symbol": "sh000012", "name": "国债指数", "interface": "sina"},
    {"symbol": "sz399986", "name": "中证银行", "interface": "sina"},
    {"symbol": "sz399396", "name": "国证食品", "interface": "sina"},
    {"symbol": "sz399435", "name": "国证农牧", "interface": "sina"},
    {"symbol": "sh000932", "name": "中证消费", "interface": "sina"},
    {"symbol": "sz399231", "name": "农林指数", "interface": "sina"},
    {"symbol": "sz399997", "name": "中证白酒", "interface": "sina"}
]

# 创建指数代码到名称的映射，提高查找效率
INDEX_SYMBOL_TO_NAME_MAP = {idx['symbol']: idx['name'] for idx in SINA_ALL_INDEX}


def get_index_dynamic_list(top_n=28, cache_duration=86400):
    """
    获取动态选择的主要指数（前N名+沪深300）
    使用天级别缓存
    """
    cache_key = f"dynamic_selected_indices_{top_n}"
    
    # 尝试从缓存获取数据
    cached_data = get_index_cached_data(cache_key)
    if cached_data is not None and isinstance(cached_data, list) and len(cached_data) > 0:
        logger.info(f"从缓存获取动态选择的指数列表（前{top_n}名+沪深300）")
        return cached_data

    try:
        # 获取最近 30 天排名
        top_ranking = get_index_ranking(period_days=30)
        
        # 检查沪深 300 是否在排名中
        sz300_data = next((idx for idx in top_ranking if idx['symbol'] == 'sz399300'), None)
        
        if sz300_data:
            # 沪深 300 在排名中，确保它在结果中
            # 先取前 top_n-1 名（为沪深 300 预留位置）
            top_indices = top_ranking[:top_n-1]
            
            # 检查沪深 300 是否已在前 top_n-1 名中
            sz300_in_top = any(idx['symbol'] == 'sz399300' for idx in top_indices)
            
            if not sz300_in_top:
                # 沪深 300 不在前 top_n-1 名，添加到结果中
                result = list(top_indices) + [sz300_data]
                logger.info(f"沪深 300 不在前{top_n-1}名，已添加到结果中（排名外）")
            else:
                # 沪深 300 已在前 top_n-1 名中
                result = list(top_indices)
                logger.info(f"沪深 300 在前{top_n-1}名内")
        else:
            # 理论上不会发生，因为 get_index_ranking 会遍历 SINA_ALL_INDEX
            logger.warning(f"沪深 300 不在排名数据中，返回前{top_n}名")
            result = list(top_ranking[:top_n])
        
        set_index_cache_data(cache_key, result, cache_duration=cache_duration)
        logger.info(f"成功获取并缓存动态选择的 {len(result)} 个指数数据（包含沪深 300）")
        return result
    except Exception as e:
        logger.error(f"获取动态选择指数失败：{e}")
        # 返回缓存数据或空列表
        cached_data = get_index_cached_data(cache_key)
        if cached_data:
            return cached_data
        return []


def get_sina_index_spot_data():
    """
    获取新浪指数实时数据并加入缓存
    """
    cache_key = "sina_index_spot_data"

    # 尝从缓存获取数据
    cached_data = get_index_cached_data(cache_key)
    if cached_data is not None and isinstance(cached_data, pd.DataFrame) and not cached_data.empty:
        logger.info("从缓存获取新浪指数实时数据")
        return cached_data
    elif cached_data is not None and isinstance(cached_data, list):
        # 如果缓存的是字典列表，转换回DataFrame
        df_from_cache = pd.DataFrame(cached_data) if cached_data else pd.DataFrame()
        logger.info("从缓存获取新浪指数实时数据")
        return df_from_cache
    try:
        df = ak.stock_zh_index_spot_sina()
        # 将DataFrame转换为字典列表进行缓存，避免JSON序列化问题
        df_dict = df.to_dict('records') if not df.empty else []
        set_index_cache_data(cache_key, df_dict)
        logger.info(f"!akshare!使用新浪接口获取到 {len(df)} 条指数实时数据并存入缓存")
        return df
    except Exception as e:
        logger.error(f"获取新浪指数实时数据失败: {e}")
        return pd.DataFrame()

def get_index_daily_data(symbol):
    """
    获取单个指数日线数据，所有历史数据
    :param symbol: 指数代码
    """
    cache_key = f"sina_index_{symbol}_daily"
    cached_data = get_index_cached_data(cache_key)
    if cached_data is not None and isinstance(cached_data, pd.DataFrame) and not cached_data.empty:
        logger.info(f"从缓存获取新浪{symbol}daily数据")
        return cached_data
    elif cached_data is not None and isinstance(cached_data, list):
        # 如果缓存的是字典列表，转换回DataFrame
        df_from_cache = pd.DataFrame(cached_data) if cached_data else pd.DataFrame()
        logger.info(f"从缓存获取新浪{symbol}daily数据")
        return df_from_cache
    try:
        df = ak.stock_zh_index_daily(symbol=symbol)
        # 确保日期列是datetime类型并转换为字符串格式，避免JSON序列化问题
        if not df.empty and 'date' in df.columns:
            df['date'] = pd.to_datetime(df['date']).dt.strftime('%Y-%m-%d')
        # 将DataFrame转换为字典列表进行缓存，避免JSON序列化问题
        df_dict = df.to_dict('records') if not df.empty else []
        set_index_cache_data(cache_key, df_dict)
        logger.info(f"!akshare!使用新浪接口获取到{symbol}的{len(df)}条日线数据并存入缓存")
        return df
    except Exception as e:
        logger.error(f"获取新浪指数实时数据失败: {e}")
        return pd.DataFrame()

def get_index_history(symbol: str, period: str = "12M"):
    """
    获取单个指数历史数据
    :param symbol: 指数代码
    :param period: 时间周期，默认12个月
    从所有历史数据中筛选出指定周期的数据
    """
    cache_key = f"index_history_{symbol}_{period}"

    # 尝试从缓存获取数据
    cached_data = get_index_cached_data(cache_key)
    if cached_data is not None and isinstance(cached_data, list) and len(cached_data) > 0:
        logger.info(f"从缓存获取指数历史数据: {symbol}")
        return cached_data

    try:
        df = get_index_daily_data(symbol)

        # 如果是中文列名，转换为英文
        if '日期' in df.columns:
            df.rename(columns={
                '日期': 'date',
                '开盘': 'open',
                '收盘': 'close',
                '最高': 'high',
                '最低': 'low',
                '成交量': 'volume',
                '成交额': 'amount'
            }, inplace=True)
        # 确保所需的列存在
        required_columns = ['date', 'open', 'close', 'high', 'low', 'volume', 'amount']
        for col in required_columns:
            if col not in df.columns:
                df[col] = 0 if col != 'date' else pd.NaT

        # 转换日期格式
        df['date'] = pd.to_datetime(df['date'])

        # 计算时间范围
        end_date = datetime.now()
        if period.endswith('D'):
            # 处理天数周期
            days = int(period[:-1])
            start_date = end_date - timedelta(days=days)
        elif period.endswith('M'):
            months = int(period[:-1])
            start_date = end_date - timedelta(days=months*30)
        elif period.endswith('Y'):
            years = int(period[:-1])
            start_date = end_date - timedelta(days=years*365)
        else:
            start_date = end_date - timedelta(days=365)  # 默认一年

        # 筛选指定时间范围内的数据
        df = df[df['date'] >= start_date]
        df = df.sort_values('date')

        # 转换为字典列表格式
        result = []
        for _, row in df.iterrows():
            item = {
                'date': row['date'].strftime('%Y-%m-%d'),
                'open': float(row['open']) if pd.notna(row['open']) else 0.0,
                'close': float(row['close']) if pd.notna(row['close']) else 0.0,
                'high': float(row['high']) if pd.notna(row['high']) else 0.0,
                'low': float(row['low']) if pd.notna(row['low']) else 0.0,
                'volume': int(row['volume']) if pd.notna(row['volume']) else 0,
                'amount': float(row['amount']) if pd.notna(row['amount']) else 0.0
            }
            result.append(item)

        # 在缓存前确保所有数据都是JSON可序列化的
        set_index_cache_data(cache_key, result)

        return result
    except Exception as e:
        logger.error(f"获取指数历史数据失败 {symbol}: {e}")
        return []


def get_index_ranking(period_days=30):
    """
    优化版本的获取指数涨跌幅排名函数（移除use_sina_ranking参数）
    :param period_days: 时间周期（天数），默认30天
    :返回前所有指数排名
    """
    logger.info(f"开始获取指数排名（优化版），周期: {period_days}天")

    # 缓存键
    cache_key = f"index_ranking_main_optimized_{period_days}"

    # 尝试从缓存获取数据
    cached_data = get_index_cached_data(cache_key)
    if cached_data is not None and isinstance(cached_data, list) and len(cached_data) > 0:
        logger.info(f"从缓存获取指数排名（优化版，{period_days}天周期）")
        return cached_data

    try:
        def _calculate_change_percent_optimized(symbol, name, history_data, period_days):
            """计算指数涨跌幅的内部函数（优化版）"""
            if not history_data or len(history_data) == 0:
                return None

            # 获取最新的价格
            latest_data = history_data[-1]
            latest_close = latest_data['close']
            logger.debug(f"指数 {name} ({symbol}) 最新价格: {latest_close}")

            # 获取period_days天前的价格
            target_date = datetime.now() - timedelta(days=period_days)
            start_price = None

            # 直接查找最接近目标日期的价格
            # 从最近的数据向前查找，找到最接近目标日期的数据
            for hist_item in reversed(history_data):  # 从后往前遍历
                hist_date = datetime.strptime(hist_item['date'], '%Y-%m-%d')
                if hist_date.date() <= target_date.date():
                    start_price = hist_item['close']
                    break

            # 如果没找到合适的价格，使用最早的可用数据
            if start_price is None and len(history_data) > 0:
                start_price = history_data[0]['close']

            logger.debug(f"指数 {name} ({symbol}) 起始价格: {start_price}, 最终价格: {latest_close}")

            if start_price is not None and start_price != 0:
                change_percent = ((latest_close - start_price) / start_price) * 100
                return {
                    'symbol': symbol,
                    'name': name,
                    'current_price': latest_close,
                    'change_percent': round(change_percent, 2),
                    'change_amount': round(latest_close - start_price, 2),
                    'volume': 0,  # 历史周期数据无法获得累计成交量
                    'amount': 0.0  # 历史周期数据无法获得累计成交额
                }
            return None

        logger.info(f"使用动态选择的指数列表计算 {period_days} 天周期的指数排名")
        selected_indices = SINA_ALL_INDEX
        ranking_list = []
        # 批量获取所有指数的历史数据以提高效率
        symbol_history_map = {}
        for idx in selected_indices:
            history_data = get_index_history(idx['symbol'], period=f"{period_days}D")
            symbol_history_map[idx['symbol']] = history_data

        # 计算每个指数的涨跌幅
        for idx in selected_indices:
            symbol = idx['symbol']
            history_data = symbol_history_map.get(symbol, [])
            name = idx['name']
            rank_item = _calculate_change_percent_optimized(symbol, name, history_data, period_days)

            if rank_item:
                ranking_list.append(rank_item)
                logger.debug(f"添加指数 {symbol} 到排名列表，涨跌幅: {rank_item['change_percent']}%")
            else:
                logger.warning(f"无法计算指数 {symbol} 的涨跌幅")

        # 按涨跌幅排序
        ranking_list.sort(key=lambda x: x['change_percent'], reverse=True)
        logger.info(f"排序后排名列表长度: {len(ranking_list)}，已按涨跌幅排序")

        # 添加排名
        for i, item in enumerate(ranking_list):
            item['rank'] = i + 1
            logger.debug(f"排名 {i+1}: {item['name']} ({item['symbol']}) 涨跌幅: {item['change_percent']}%")

        set_index_cache_data(cache_key, ranking_list)
        logger.info(f"成功获取并缓存 {len(ranking_list)} 个指数的排名数据（优化版，{period_days}天周期）")
        return ranking_list
    except Exception as e:
        logger.error(f"获取指数排名失败（优化版）: {e}", exc_info=True)
        # 返回缓存的数据
        cached_data = get_index_cached_data(cache_key)
        if cached_data is not None and isinstance(cached_data, list) and len(cached_data) > 0:
            logger.info(f"返回缓存的指数排名（优化版，{period_days}天周期）")
            return cached_data
        return []


def get_multiple_index_history(symbols: List[str], period: str = "12M"):
    """
    获取多个指数历史数据用于对比
    :param symbols: 指数代码列表
    :param period: 时间周期
    """
    cache_key = f"multiple_index_history_{','.join(sorted(symbols))}_{period}"

    # 尝试从缓存获取数据
    cached_data = get_index_cached_data(cache_key)
    if cached_data is not None and isinstance(cached_data, dict) and len(cached_data) > 0:
        logger.info(f"从缓存获取多指数历史数据: {symbols}")
        return cached_data

    try:
        result = {}
        for symbol in symbols:
            history_data = get_index_history(symbol, period)
            result[symbol] = history_data

        set_index_cache_data(cache_key, result)

        return result
    except Exception as e:
        logger.error(f"获取多个指数历史数据失败: {e}")
        return {}


def calculate_growth_rate(history_data: List[Dict], base_date: Optional[str] = None):
    """
    计算相对于基准日期的增长率
    :param history_data: 历史数据
    :param base_date: 基准日期，默认使用第一个数据点
    """
    if not history_data:
        logger.warning("历史数据为空，无法计算增长率")
        return []

    # 排序确保按日期顺序
    sorted_data = sorted(history_data, key=lambda x: x['date'])

    # 确定基准值
    if base_date:
        base_value = None
        for item in sorted_data:
            if item['date'] == base_date:
                base_value = item['close']
                break
        if base_value is None or base_value == 0:
            base_value = sorted_data[0]['close'] if sorted_data[0]['close'] != 0 else 1
            logger.warning(f"基准日期 {base_date} 的数据未找到或价格为0，使用第一个数据点作为基准值: {base_value}")
    else:
        base_value = sorted_data[0]['close'] if sorted_data[0]['close'] != 0 else 1
        logger.info(f"使用第一个数据点作为基准值: {base_value} (日期: {sorted_data[0]['date']})")

    # 计算增长率
    growth_data = []
    for item in sorted_data:
        growth_rate = ((item['close'] - base_value) / base_value) * 100 if base_value != 0 else 0
        growth_item = {
            'date': item['date'],
            'growth_rate': round(growth_rate, 2),
            'close': item['close']
        }
        growth_data.append(growth_item)

    logger.info(f"成功计算增长率，共 {len(growth_data)} 个数据点")
    return growth_data


def get_index_chart_data(symbols: List[str], period: str = "12M", use_growth_rate: bool = True):
    """
    准备指数图表数据，返回适合ECharts展示的格式
    :param symbols: 指数代码列表
    :param period: 时间周期
    :param use_growth_rate: 是否使用增长率对比
    :return: 适合ECharts展示的数据格式
    """
    cache_key = f"prepared_index_chart_data_{','.join(sorted(symbols))}_{period}_{use_growth_rate}"

    # 尝试从缓存获取数据
    cached_data = get_index_cached_data(cache_key)
    if cached_data is not None and isinstance(cached_data, dict):
        logger.info(f"从缓存获取准备好的指数图表数据: {symbols}")
        return cached_data

    try:
        # 获取多个指数历史数据
        multi_history_data = get_multiple_index_history(symbols, period)
        if not multi_history_data:
            logger.error("获取指数历史数据失败")
            return None

        # 构建图表数据格式
        chart_data = {
            "dates": [],
            "series": []
        }

        # 收集所有日期并去重排序
        all_dates = set()
        for symbol, history in multi_history_data.items():
            for item in history:
                all_dates.add(item['date'])
        chart_data["dates"] = sorted(list(all_dates))

        # 为每个指数生成系列数据
        for symbol in symbols:
            if symbol in multi_history_data:
                history = multi_history_data[symbol]
                # 为了匹配日期轴，创建完整的数据序列（缺失日期填充为None）
                series_data = []
                date_to_value = {item['date']: item for item in history}

                if use_growth_rate and len(history) > 0:
                    # 使用增长率计算
                    growth_rates = calculate_growth_rate(history)
                    # 将增长率映射到对应日期
                    date_to_growth = {item['date']: item['growth_rate'] for item in growth_rates}
                    for date in chart_data["dates"]:
                        if date in date_to_growth:
                            series_data.append(date_to_growth[date])
                        else:
                            series_data.append(None)
                else:
                    # 使用原始价格数据
                    for date in chart_data["dates"]:
                        if date in date_to_value:
                            series_data.append(date_to_value[date]['close'])
                        else:
                            series_data.append(None)

                # 获取指数名称
                index_name = INDEX_SYMBOL_TO_NAME_MAP.get(symbol, symbol)

                chart_data["series"].append({
                    "name": index_name,
                    "data": series_data
                })

        # 缓存数据
        set_index_cache_data(cache_key, chart_data)
        logger.info(f"准备好的指数图表数据已缓存: {symbols}")

        return chart_data
    except Exception as e:
        logger.error(f"准备指数图表数据失败: {e}")
        return None


if __name__ == "__main__":
    # 测试函数
    print("测试指数代码到名称映射:")
    print(f"SINA_ALL_INDEX 包含 {len(SINA_ALL_INDEX)} 个指数")
    print(f"INDEX_SYMBOL_TO_NAME_MAP 包含 {len(INDEX_SYMBOL_TO_NAME_MAP)} 个映射")

    # 显示前几个映射示例
    for idx in SINA_ALL_INDEX[:5]:  # 只打印前5个
        print(f"  {idx['symbol']}: {idx['name']}")

    print("\n测试指数排名获取:")
    ranking = get_index_ranking()
    print(f"获取到 {len(ranking)} 个指数的排名数据")
    for r in ranking[:3]:  # 打印前3名
        print(r)