"""
指数数据获取模块
支持A股主要指数的获取和处理
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional

import akshare as ak
import numpy as np
import pandas as pd

from config import setup_logger

logger = setup_logger(__name__)
from ..core.cache_with_database import get_index_cached_data, set_index_cache_data

#############################sina interface###################

SINA_ALL_INDEX = [
    {"symbol": "sz399300", "name": "沪深300", "interface": "sina"},
    {"symbol": "sz980018", "name": "卫星通信", "interface": "sina"},
    {"symbol": "sz399434", "name": "数字传媒", "interface": "sina"},
    {"symbol": "sz399971", "name": "中证传媒", "interface": "sina"},
    {"symbol": "sz399264", "name": "创业软件", "interface": "sina"},
    {"symbol": "sz980076", "name": "通用航空", "interface": "sina"},
    {"symbol": "sz399959", "name": "军工指数", "interface": "sina"},
    {"symbol": "sz399973", "name": "中证国防", "interface": "sina"},
    {"symbol": "sh000823", "name": "800有色", "interface": "sina"},
    {"symbol": "sz399652", "name": "中创高新", "interface": "sina"},
    {"symbol": "sz399368", "name": "国证军工", "interface": "sina"},
    {"symbol": "sz399397", "name": "国证文化", "interface": "sina"},
    # {"symbol": "sz399654", "name": "深证文化", "interface": "sina"},
    {"symbol": "sz399262", "name": "数字经济", "interface": "sina"},
    {"symbol": "sz399608", "name": "科技100", "interface": "sina"},
    {"symbol": "sz980015", "name": "疫苗生科", "interface": "sina"},
    {"symbol": "sz399615", "name": "深证工业", "interface": "sina"},
    {"symbol": "sz399808", "name": "中证新能", "interface": "sina"},
    # {"symbol": "sh000037", "name": "上证医药", "interface": "sina"},
    # {"symbol": "sz399618", "name": "深证医药", "interface": "sina"},
    # {"symbol": "sh000109", "name": "380医药", "interface": "sina"},
    # {"symbol": "sh000121", "name": "医药主题", "interface": "sina"},
    {"symbol": "sz399913", "name": "300医药", "interface": "sina"},
    {"symbol": "sz399933", "name": "中证医药", "interface": "sina"},
    {"symbol": "sh000991", "name": "全指医药", "interface": "sina"},
    {"symbol": "sz399439", "name": "国证油气", "interface": "sina"},
    {"symbol": "sh000906", "name": "中证800", "interface": "sina"},
    {"symbol": "sz399235", "name": "建筑指数", "interface": "sina"},
    {"symbol": "sz399643", "name": "创业新兴", "interface": "sina"},
    {"symbol": "sz399007", "name": "深证300", "interface": "sina"},
    {"symbol": "sz399995", "name": "基建工程", "interface": "sina"},
    {"symbol": "sz399339", "name": "深证科技", "interface": "sina"},
    {"symbol": "sh000047", "name": "上证全指", "interface": "sina"},
    {"symbol": "sh000065", "name": "上证龙头", "interface": "sina"},
    {"symbol": "sh000001", "name": "上证指数", "interface": "sina"},
    {"symbol": "sz399006", "name": "创业板指", "interface": "sina"},
    # {"symbol": "sz399266", "name": "创新能源", "interface": "sina"},
    {"symbol": "sz980016", "name": "医疗健康", "interface": "sina"},
    {"symbol": "sz399688", "name": "深成电信", "interface": "sina"},
    {"symbol": "sh000510", "name": "中证A500", "interface": "sina"},
    {"symbol": "sz399613", "name": "深证能源", "interface": "sina"},
    # {"symbol": "sz399655", "name": "深证绩效", "interface": "sina"},
    # {"symbol": "sz399698", "name": "优势成长", "interface": "sina"},
    {"symbol": "sz399379", "name": "国证基金", "interface": "sina"},
    {"symbol": "sh000139", "name": "上证转债", "interface": "sina"},
    # {"symbol": "sz399705", "name": "深证中游", "interface": "sina"},
    {"symbol": "sz399348", "name": "深证价值", "interface": "sina"},
    {"symbol": "sz399312", "name": "国证300", "interface": "sina"},
    # {"symbol": "sz399630", "name": "1000成长", "interface": "sina"},
    {"symbol": "sz399412", "name": "国证新能", "interface": "sina"},
    {"symbol": "sz399626", "name": "中创成长", "interface": "sina"},
    {"symbol": "sh000075", "name": "医药等权", "interface": "sina"},
    # {"symbol": "sh000070", "name": "能源等权", "interface": "sina"},
    {"symbol": "sz399363", "name": "国证算力", "interface": "sina"},
    # {"symbol": "sh000118", "name": "380价值", "interface": "sina"},
    # {"symbol": "sz399814", "name": "大农业", "interface": "sina"},
    {"symbol": "sz399234", "name": "水电指数", "interface": "sina"},
    {"symbol": "sz399636", "name": "深证装备", "interface": "sina"},
    {"symbol": "sh000072", "name": "工业等权", "interface": "sina"},
    {"symbol": "sh000034", "name": "上证工业", "interface": "sina"},
    {"symbol": "sz399261", "name": "创业制造", "interface": "sina"},
    # {"symbol": "sz399680", "name": "深成能源", "interface": "sina"},
    {"symbol": "sh000063", "name": "上证周期", "interface": "sina"},
    {"symbol": "sh000016", "name": "上证50", "interface": "sina"},
    {"symbol": "sh000867", "name": "港中小企", "interface": "sina"},
    {"symbol": "sz399812", "name": "养老产业", "interface": "sina"},
    # {"symbol": "sh000986", "name": "全指能源", "interface": "sina"},
    {"symbol": "sz399259", "name": "创业低碳", "interface": "sina"},
    {"symbol": "sz399293", "name": "创业大盘", "interface": "sina"},
    # {"symbol": "sh000032", "name": "上证能源", "interface": "sina"},
    {"symbol": "sz399346", "name": "深证成长", "interface": "sina"},
    {"symbol": "sh000989", "name": "全指可选", "interface": "sina"},
    {"symbol": "sz399619", "name": "深证金融", "interface": "sina"},
    # {"symbol": "sz399371", "name": "国证价值", "interface": "sina"},
    # {"symbol": "sz399381", "name": "1000能源", "interface": "sina"},
    {"symbol": "sz399365", "name": "国证粮食", "interface": "sina"},
    {"symbol": "sh000827", "name": "中证环保", "interface": "sina"},
    # {"symbol": "sz399436", "name": "绿色煤炭", "interface": "sina"},
    {"symbol": "sz399437", "name": "证券龙头", "interface": "sina"},
    # {"symbol": "sz399990", "name": "煤炭等权", "interface": "sina"},
    {"symbol": "sz399928", "name": "中证能源", "interface": "sina"},
    {"symbol": "sz399638", "name": "深证环保", "interface": "sina"},
    # {"symbol": "sz399669", "name": "深证农业", "interface": "sina"},
    {"symbol": "sz399975", "name": "证券公司", "interface": "sina"},
    # {"symbol": "sz399637", "name": "深证地产", "interface": "sina"},
    # {"symbol": "sh000122", "name": "农业主题", "interface": "sina"},
    {"symbol": "sz399353", "name": "国证物流", "interface": "sina"},
    {"symbol": "sz980028", "name": "龙头家电", "interface": "sina"},
    {"symbol": "sz399622", "name": "深证公用", "interface": "sina"},
    {"symbol": "sz399260", "name": "先进制造", "interface": "sina"},
    {"symbol": "sz399433", "name": "国证交运", "interface": "sina"},
    {"symbol": "sz399241", "name": "地产指数", "interface": "sina"},
    {"symbol": "sz399998", "name": "中证煤炭", "interface": "sina"},
    # {"symbol": "sh000992", "name": "全指金融", "interface": "sina"},
    # {"symbol": "sh000038", "name": "上证金融", "interface": "sina"},
    # {"symbol": "sh000076", "name": "金融等权", "interface": "sina"},
    # {"symbol": "sz399686", "name": "深成金融", "interface": "sina"},
    # {"symbol": "sz399240", "name": "金融指数", "interface": "sina"},
    {"symbol": "sz399934", "name": "中证金融", "interface": "sina"},
    {"symbol": "sh000015", "name": "红利指数", "interface": "sina"},
    {"symbol": "sh000074", "name": "消费等权", "interface": "sina"},
    {"symbol": "sz399358", "name": "国证环保", "interface": "sina"},
    # {"symbol": "sz399983", "name": "地产等权", "interface": "sina"},
    {"symbol": "sz399438", "name": "绿色电力", "interface": "sina"},
    # {"symbol": "sz399328", "name": "深证治理", "interface": "sina"},
    {"symbol": "sh000152", "name": "上央红利", "interface": "sina"},
    {"symbol": "sh000036", "name": "上证消费", "interface": "sina"},
    {"symbol": "sz399237", "name": "运输指数", "interface": "sina"},
    # {"symbol": "sz399431", "name": "国证银行", "interface": "sina"},
    # {"symbol": "sh000134", "name": "上证银行", "interface": "sina"},
    # {"symbol": "sz399359", "name": "国证基建", "interface": "sina"},
    {"symbol": "sh000012", "name": "国债指数", "interface": "sina"},
    {"symbol": "sz399986", "name": "中证银行", "interface": "sina"},
    {"symbol": "sz399396", "name": "国证食品", "interface": "sina"},
    # {"symbol": "sz399435", "name": "国证农牧", "interface": "sina"},
    {"symbol": "sh000932", "name": "中证消费", "interface": "sina"},
    {"symbol": "sz399231", "name": "农林指数", "interface": "sina"},
    {"symbol": "sz399997", "name": "中证白酒", "interface": "sina"},
]

# 大盘指数·**真实估值组**（乐咕 legulegu 有真实 PE/PB）：在列表中恒排最前、与行业/主题指数区分。
# 顺序即展示优先级。若 SINA_ALL_INDEX 中缺某只，自动补到清单最前。
REAL_VALUATION_INDEXES = [
    ("sz399300", "沪深300"),
    ("sh000016", "上证50"),
    ("sh000905", "中证500"),
    ("sh000852", "中证1000"),
    ("sz399673", "创业板50"),
    ("sh000010", "上证180"),
]
_REAL_SYMBOLS = {s for s, _ in REAL_VALUATION_INDEXES}


def _ensure_real_indexes_in_list() -> None:
    """确保真实估值大盘指数都在 SINA_ALL_INDEX 中（缺则补到最前）。"""
    have = {idx["symbol"] for idx in SINA_ALL_INDEX}
    prepend = [{"symbol": s, "name": n, "interface": "sina"}
               for s, n in REAL_VALUATION_INDEXES if s not in have]
    if prepend:
        SINA_ALL_INDEX[:0] = prepend
        logger.info(f"指数清单补充真实估值大盘指数: {[p['name'] for p in prepend]}")


_ensure_real_indexes_in_list()

# 创建指数代码到名称的映射，提高查找效率
INDEX_SYMBOL_TO_NAME_MAP = {idx["symbol"]: idx["name"] for idx in SINA_ALL_INDEX}


def index_group(symbol: str) -> str:
    """指数分组标签：大盘指数(真实估值) / 行业主题(估算)。"""
    return "大盘指数(真实估值)" if symbol in _REAL_SYMBOLS else "行业主题(估算)"

# 乐咕乐股（legulegu）**真实**指数估值覆盖范围（月频，含滚动市盈率/市净率）。
# 仅这些大盘指数有第三方权威 PE/PB；其余行业/主题指数无公开估值源，
# 页面回退到"价格缩放估算"（estimate_*，非真实估值，`valuation_source` 会标注）。
_LG_INDEX_NAME = {
    "sh000016": "上证50",
    "sh000300": "沪深300", "sz399300": "沪深300",
    "sh000905": "中证500", "sz399905": "中证500",
    "sh000852": "中证1000", "sz399852": "中证1000",
    "sz399673": "创业板50",
    "sh000010": "上证180",
}


def get_index_dynamic_list(top_n=28, cache_duration=86400):
    """动态指数列表：**大盘指数(真实估值)恒包含并置顶** + 其余按涨幅取前 N。

    （旧实现硬编码"沪深300 预留 1 位"，且 `sz300_data` 可能为 None 会污染列表；已重写。）
    """
    cache_key = f"dynamic_selected_indices_v4_{top_n}"
    cached_data = get_index_cached_data(cache_key)
    if isinstance(cached_data, list) and cached_data:
        return cached_data
    try:
        ranking = get_index_ranking(period_days=30)
        real = [x for x in ranking if x["symbol"] in _REAL_SYMBOLS]
        rest = [x for x in ranking if x["symbol"] not in _REAL_SYMBOLS]
        result = real + rest[:max(0, top_n)]
        set_index_cache_data(cache_key, result, cache_duration=cache_duration)
        logger.info(f"动态指数列表：大盘指数 {len(real)} + 其余 {len(result)-len(real)} = {len(result)}")
        return result
    except Exception as e:
        logger.error(f"获取动态选择指数失败：{e}")
        return []


def get_sina_index_spot_data():
    """
    获取新浪指数实时数据并加入缓存
    """
    cache_key = "sina_index_spot_data"

    # 尝从缓存获取数据
    cached_data = get_index_cached_data(cache_key)
    if (
        cached_data is not None
        and isinstance(cached_data, pd.DataFrame)
        and not cached_data.empty
    ):
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
        df_dict = df.to_dict("records") if not df.empty else []
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
    if (
        cached_data is not None
        and isinstance(cached_data, pd.DataFrame)
        and not cached_data.empty
    ):
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
        if not df.empty and "date" in df.columns:
            df["date"] = pd.to_datetime(df["date"]).dt.strftime("%Y-%m-%d")
        # 将DataFrame转换为字典列表进行缓存，避免JSON序列化问题
        df_dict = df.to_dict("records") if not df.empty else []
        set_index_cache_data(cache_key, df_dict)
        logger.info(
            f"!akshare!使用新浪接口获取到{symbol}的{len(df)}条日线数据并存入缓存"
        )
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
    if (
        cached_data is not None
        and isinstance(cached_data, list)
        and len(cached_data) > 0
    ):
        logger.info(f"从缓存获取指数历史数据: {symbol}")
        return cached_data

    try:
        df = get_index_daily_data(symbol)
        if df is None or df.empty:
            logger.warning(f"指数 {symbol} 无日线数据")
            return []

        # 新浪指数日线字段：date/open/high/low/close/volume（无 amount，故成交额恒缺）
        required_columns = ["date", "open", "close", "high", "low", "volume"]
        for col in required_columns:
            if col not in df.columns:
                df[col] = 0 if col != "date" else pd.NaT

        # 转换日期格式
        df["date"] = pd.to_datetime(df["date"])

        # 计算时间范围
        end_date = datetime.now()
        if period.endswith("D"):
            # 处理天数周期
            days = int(period[:-1])
            start_date = end_date - timedelta(days=days)
        elif period.endswith("M"):
            months = int(period[:-1])
            start_date = end_date - timedelta(days=months * 30)
        elif period.endswith("Y"):
            years = int(period[:-1])
            start_date = end_date - timedelta(days=years * 365)
        else:
            start_date = end_date - timedelta(days=365)  # 默认一年

        # 筛选指定时间范围内的数据
        df = df[df["date"] >= start_date]
        df = df.sort_values("date")

        # 转换为字典列表格式（amount 新浪指数日线不提供，缺则记 0）
        has_amount = "amount" in df.columns
        result = []
        for _, row in df.iterrows():
            item = {
                "date": row["date"].strftime("%Y-%m-%d"),
                "open": float(row["open"]) if pd.notna(row["open"]) else 0.0,
                "close": float(row["close"]) if pd.notna(row["close"]) else 0.0,
                "high": float(row["high"]) if pd.notna(row["high"]) else 0.0,
                "low": float(row["low"]) if pd.notna(row["low"]) else 0.0,
                "volume": int(row["volume"]) if pd.notna(row["volume"]) else 0,
                "amount": (float(row["amount"]) if has_amount and pd.notna(row["amount"])
                           else 0.0),
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
    cache_key = f"index_ranking_main_optimized_v3_{period_days}"

    # 尝试从缓存获取数据
    cached_data = get_index_cached_data(cache_key)
    if (
        cached_data is not None
        and isinstance(cached_data, list)
        and len(cached_data) > 0
    ):
        logger.info(f"从缓存获取指数排名（优化版，{period_days}天周期）")
        return cached_data

    try:

        def _calculate_change_percent_optimized(
            symbol, name, history_data, period_days
        ):
            """计算指数涨跌幅的内部函数（优化版）"""
            if not history_data or len(history_data) == 0:
                return None

            # 获取最新的价格
            latest_data = history_data[-1]
            latest_close = latest_data["close"]
            logger.debug(f"指数 {name} ({symbol}) 最新价格: {latest_close}")

            # 获取period_days天前的价格
            target_date = datetime.now() - timedelta(days=period_days)
            start_price = None

            # 直接查找最接近目标日期的价格
            # 从最近的数据向前查找，找到最接近目标日期的数据
            for hist_item in reversed(history_data):  # 从后往前遍历
                hist_date = datetime.strptime(hist_item["date"], "%Y-%m-%d")
                if hist_date.date() <= target_date.date():
                    start_price = hist_item["close"]
                    break

            # 如果没找到合适的价格，使用最早的可用数据
            if start_price is None and len(history_data) > 0:
                start_price = history_data[0]["close"]

            logger.debug(
                f"指数 {name} ({symbol}) 起始价格: {start_price}, 最终价格: {latest_close}"
            )

            if start_price is not None and start_price != 0:
                change_percent = ((latest_close - start_price) / start_price) * 100
                # 注意：估值字段不在此处计算（原先对每只指数调用 get_enhanced_index_data，
                # 与 get_detailed_index_ranking 重复且昂贵）。需要估值请走 detailed_ranking。
                return {
                    "symbol": symbol,
                    "name": name,
                    "current_price": latest_close,
                    "change_percent": round(change_percent, 2),
                    "change_amount": round(latest_close - start_price, 2),
                    "volume": 0,  # 指数日线（新浪）无成交量/额，见 get_index_history 说明
                    "amount": 0.0,
                    "pe": None,
                    "pb": None,
                    "pe_percentile": None,
                    "pb_percentile": None,
                }
            return None

        logger.info(f"使用动态选择的指数列表计算 {period_days} 天周期的指数排名")
        selected_indices = SINA_ALL_INDEX
        ranking_list = []
        # 批量获取所有指数的历史数据以提高效率
        symbol_history_map = {}
        for idx in selected_indices:
            history_data = get_index_history(idx["symbol"], period=f"{period_days}D")
            symbol_history_map[idx["symbol"]] = history_data

        # 计算每个指数的涨跌幅
        for idx in selected_indices:
            symbol = idx["symbol"]
            history_data = symbol_history_map.get(symbol, [])
            name = idx["name"]
            rank_item = _calculate_change_percent_optimized(
                symbol, name, history_data, period_days
            )

            if rank_item:
                ranking_list.append(rank_item)
                logger.debug(
                    f"添加指数 {symbol} 到排名列表，涨跌幅: {rank_item['change_percent']}%"
                )
            else:
                logger.warning(f"无法计算指数 {symbol} 的涨跌幅")

        # 按涨跌幅排序
        ranking_list.sort(key=lambda x: x["change_percent"], reverse=True)
        logger.info(f"排序后排名列表长度: {len(ranking_list)}，已按涨跌幅排序")

        # 添加排名
        for i, item in enumerate(ranking_list):
            item["rank"] = i + 1
            logger.debug(
                f"排名 {i+1}: {item['name']} ({item['symbol']}) 涨跌幅: {item['change_percent']}%"
            )

        # 分组字段在此**统一给出**（唯一来源）：/api/index/ranking 与 /api/index/dynamic_list
        # 都由本函数派生，前端只认 `index_group`，不再自带硬编码符号表。
        for item in ranking_list:
            item["is_real_valuation"] = item["symbol"] in _REAL_SYMBOLS
            item["index_group"] = index_group(item["symbol"])

        set_index_cache_data(cache_key, ranking_list)
        logger.info(
            f"成功获取并缓存 {len(ranking_list)} 个指数的排名数据（优化版，{period_days}天周期）"
        )
        return ranking_list
    except Exception as e:
        logger.error(f"获取指数排名失败（优化版）: {e}", exc_info=True)
        # 返回缓存的数据
        cached_data = get_index_cached_data(cache_key)
        if (
            cached_data is not None
            and isinstance(cached_data, list)
            and len(cached_data) > 0
        ):
            logger.info(f"返回缓存的指数排名（优化版，{period_days}天周期）")
            return cached_data
        return []


def get_detailed_index_ranking(period_days=30, include_valuation=True):
    """
    获取详细的指数排名数据，包含估值信息
    :param period_days: 时间周期（天数），默认30天
    :param include_valuation: 是否包含估值数据
    :return: 包含详细信息的排名列表
    """
    logger.info(f"开始获取详细指数排名（包含估值），周期: {period_days}天")

    # 缓存键
    cache_key = f"detailed_index_ranking_v8_{period_days}_{include_valuation}"

    # 尝试从缓存获取数据
    cached_data = get_index_cached_data(cache_key)
    if (
        cached_data is not None
        and isinstance(cached_data, list)
        and len(cached_data) > 0
    ):
        logger.info(f"从缓存获取详细指数排名（{period_days}天周期）")
        return cached_data

    try:
        # 获取基础排名数据
        basic_ranking = get_index_ranking(period_days)

        if include_valuation:
            # 为每个指数补充估值数据（真实优先，见 get_enhanced_index_data）
            for item in basic_ranking:
                symbol = item["symbol"]
                enhanced_data = get_enhanced_index_data(symbol)
                item["pe"] = enhanced_data.get("pe")
                item["pb"] = enhanced_data.get("pb")
                item["pe_percentile"] = enhanced_data.get("pe_percentile")
                item["pb_percentile"] = enhanced_data.get("pb_percentile")
                item["valuation_source"] = enhanced_data.get("valuation_source")
                item["valuation_status"] = _get_valuation_status(
                    enhanced_data.get("pe_percentile"),
                    enhanced_data.get("pb_percentile"),
                )

        # 分组与展示顺序：大盘指数(真实估值)恒排最前，其余按涨幅；组内保持涨幅排序
        # （`is_real_valuation`/`index_group` 的**权威来源**是 `get_index_ranking`；
        #   这里再断言一次，防止读到缺字段的旧缓存导致分组/置顶失效）
        for item in basic_ranking:
            item["is_real_valuation"] = item["symbol"] in _REAL_SYMBOLS
            item["index_group"] = index_group(item["symbol"])
        _real = [x for x in basic_ranking if x["is_real_valuation"]]
        _rest = [x for x in basic_ranking if not x["is_real_valuation"]]
        ranking_out = _real + _rest
        for i, item in enumerate(ranking_out):
            item["display_order"] = i

        # 大盘指数若**仍有回退到估算**的（乐咕真实估值后台补齐中），只缓存 10 分钟以便尽快刷新；
        # 否则默认 24h。注：`get_enhanced_index_data` 内层也有 600s 逻辑，但若外层缓存 24h
        # 会把内层的快速刷新完全盖住 → 大盘指数会卡在"估算"最长一天。
        _fallback = any(
            x["symbol"] in _REAL_SYMBOLS
            and str(x.get("valuation_source") or "").startswith("estimate")
            for x in ranking_out
        )
        set_index_cache_data(cache_key, ranking_out,
                             cache_duration=600 if _fallback else None)
        logger.info(
            f"成功获取并缓存 {len(ranking_out)} 个指数的详细排名"
            f"（大盘指数真实估值 {len(_real)} 个置顶；"
            f"{'存在估算回退，缓存 600s' if _fallback else '全部就绪，缓存默认时长'}）"
        )
        return ranking_out
    except Exception as e:
        logger.error(f"获取详细指数排名失败: {e}", exc_info=True)
        # 返回缓存的数据
        cached_data = get_index_cached_data(cache_key)
        if (
            cached_data is not None
            and isinstance(cached_data, list)
            and len(cached_data) > 0
        ):
            logger.info(f"返回缓存的详细指数排名")
            return cached_data
        return []


def _get_valuation_status(pe_percentile, pb_percentile):
    """
    根据PE和PB百分位数判断估值状态
    :param pe_percentile: PE百分位数
    :param pb_percentile: PB百分位数
    :return: 估值状态描述
    """
    if pe_percentile is None and pb_percentile is None:
        return "数据不足"
    elif pe_percentile is None:
        # 仅基于PB判断
        if pb_percentile <= 20:
            return "低估"
        elif pb_percentile >= 80:
            return "高估"
        else:
            return "合理"
    elif pb_percentile is None:
        # 仅基于PE判断
        if pe_percentile <= 20:
            return "低估"
        elif pe_percentile >= 80:
            return "高估"
        else:
            return "合理"
    else:
        # 同时基于PE和PB判断
        pe_low = pe_percentile <= 20
        pe_high = pe_percentile >= 80
        pb_low = pb_percentile <= 20
        pb_high = pb_percentile >= 80

        if (
            (pe_low and pb_low)
            or (pe_low and pb_percentile < 50)
            or (pb_low and pe_percentile < 50)
        ):
            return "低估"
        elif (
            (pe_high and pb_high)
            or (pe_high and pb_percentile > 50)
            or (pb_high and pe_percentile > 50)
        ):
            return "高估"
        else:
            return "合理"


def get_multiple_index_history(symbols: List[str], period: str = "12M"):
    """
    获取多个指数历史数据用于对比
    :param symbols: 指数代码列表
    :param period: 时间周期
    """
    cache_key = f"multiple_index_history_v3_{','.join(sorted(symbols))}_{period}"

    # 尝试从缓存获取数据
    cached_data = get_index_cached_data(cache_key)
    if (
        cached_data is not None
        and isinstance(cached_data, dict)
        and len(cached_data) > 0
    ):
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
    sorted_data = sorted(history_data, key=lambda x: x["date"])

    # 确定基准值
    if base_date:
        base_value = None
        for item in sorted_data:
            if item["date"] == base_date:
                base_value = item["close"]
                break
        if base_value is None or base_value == 0:
            base_value = sorted_data[0]["close"] if sorted_data[0]["close"] != 0 else 1
            logger.warning(
                f"基准日期 {base_date} 的数据未找到或价格为0，使用第一个数据点作为基准值: {base_value}"
            )
    else:
        base_value = sorted_data[0]["close"] if sorted_data[0]["close"] != 0 else 1
        logger.info(
            f"使用第一个数据点作为基准值: {base_value} (日期: {sorted_data[0]['date']})"
        )

    # 计算增长率
    growth_data = []
    for item in sorted_data:
        growth_rate = (
            ((item["close"] - base_value) / base_value) * 100 if base_value != 0 else 0
        )
        growth_item = {
            "date": item["date"],
            "growth_rate": round(growth_rate, 2),
            "close": item["close"],
        }
        growth_data.append(growth_item)

    logger.info(f"成功计算增长率，共 {len(growth_data)} 个数据点")
    return growth_data


def _series_percentile(series, years: int = 10) -> Optional[float]:
    """序列末端值在近 years 年（月频≈12点/年）中的百分位（0~100）。"""
    s = pd.Series(series).dropna()
    if len(s) < 2:
        return None
    win = s.tail(years * 12 + 1) if len(s) > years * 12 else s
    return float((win <= win.iloc[-1]).mean() * 100)


_LG_FAIL_COOLDOWN = 600           # 单只失败后的冷却秒数（逐只，避免一只失败拖累全部）
_LG_MIN_INTERVAL = 2.0            # 两次 HTTP 调用最小间隔（秒）
_LG_LAST_CALL = {"ts": 0.0}
_LG_FAIL_TS: Dict[str, float] = {}


def _lg_throttle() -> None:
    """确保乐咕两次 HTTP 调用间隔 ≥ _LG_MIN_INTERVAL。"""
    import time as _t
    wait = _LG_MIN_INTERVAL - (_t.time() - _LG_LAST_CALL["ts"])
    if wait > 0:
        _t.sleep(wait)
    _LG_LAST_CALL["ts"] = _t.time()


def _lg_fetch(fn, name: str, attempts: int = 3):
    """带重试/退避地调用一次乐咕接口；失败返回 None。"""
    import time as _t
    for i in range(attempts):
        try:
            _lg_throttle()
            df = fn(symbol=name)
            if df is not None and not df.empty:
                return df
        except Exception as e:  # noqa: BLE001
            logger.warning(f"乐咕接口失败 {name} 第{i+1}/{attempts}次: {type(e).__name__}")
        _t.sleep(1.5 * (i + 1))
    return None


def _valuation_from_legulegu(symbol: str, years: int = 10, allow_fetch: bool = True) -> Dict:
    """真实指数估值（乐咕乐股 legulegu，**月频**，含滚动市盈率 TTM 与市净率）。

    仅覆盖少数大盘指数（见 `_LG_INDEX_NAME`）；其余指数返回 {}。
    `allow_fetch=False` 时**只读缓存、不发起网络请求**（供页面请求路径使用，避免阻塞；
    缺失值由 `warm_real_valuations()` 在后台线程补齐）。
    抗限流：请求间节流、逐只重试、逐只失败冷却；PE/PB 允许部分成功。
    """
    name = _LG_INDEX_NAME.get(symbol)
    if not name:
        return {}
    cache_key = f"index_val_lg_v6_{symbol}"
    cached = get_index_cached_data(cache_key)
    if isinstance(cached, dict) and cached.get("pe") is not None and cached.get("pb") is not None:
        return cached
    if not allow_fetch:
        return {}   # 页面路径：不阻塞，交给后台补齐

    import time as _t
    if _t.time() - _LG_FAIL_TS.get(symbol, 0.0) < _LG_FAIL_COOLDOWN:
        return {}   # 该指数处于冷却期（逐只，避免一只失败拖累全部）

    # PE / PB 各自独立重试，允许部分成功（一次 flaky 不丢整只）
    pe_df = _lg_fetch(ak.stock_index_pe_lg, name)
    pb_df = _lg_fetch(ak.stock_index_pb_lg, name)
    if pe_df is None and pb_df is None:
        _LG_FAIL_TS[symbol] = _t.time()
        return {}
    out: Dict = {}
    try:
        if pe_df is not None:
            pe_col = "滚动市盈率" if "滚动市盈率" in pe_df.columns else "静态市盈率"
            out["pe"] = float(pe_df[pe_col].iloc[-1])
            out["pe_percentile"] = _series_percentile(pe_df[pe_col], years)
            out["pe_date"] = str(pd.Timestamp(pe_df["日期"].iloc[-1]).date())
        if pb_df is not None:
            pb_col = "市净率" if "市净率" in pb_df.columns else "等权市净率"
            out["pb"] = float(pb_df[pb_col].iloc[-1])
            out["pb_percentile"] = _series_percentile(pb_df[pb_col], years)
    except (KeyError, ValueError, IndexError) as e:
        logger.warning(f"乐咕估值解析失败 {symbol}: {e}")
        return {}
    out["valuation_source"] = f"legulegu(月频·{name})"
    # 完整结果缓存 1 天；部分结果缓存 1 小时（便于稍后补齐）
    ttl = 86400 if ("pe" in out and "pb" in out) else 3600
    set_index_cache_data(cache_key, out, cache_duration=ttl)
    logger.info(f"乐咕真实估值 {symbol}: PE={out.get('pe')} PB={out.get('pb')} ttl={ttl}s")
    return out


_WARMING = {"on": False}


def warm_real_valuations(symbols=None) -> None:
    """在**后台线程**里为大盘指数逐个补齐真实估值（节流，不阻塞页面）。"""
    symbols = symbols or [s for s, _ in REAL_VALUATION_INDEXES]
    if _WARMING["on"]:
        return
    _WARMING["on"] = True

    def _worker():
        try:
            for sym in symbols:
                try:
                    _valuation_from_legulegu(sym, allow_fetch=True)
                except Exception as e:  # noqa: BLE001
                    logger.warning(f"后台补齐估值失败 {sym}: {type(e).__name__}")
        finally:
            _WARMING["on"] = False
            logger.info("大盘指数真实估值后台补齐完成")

    import threading
    threading.Thread(target=_worker, daemon=True, name="index_valuation_warm").start()


def estimate_historical_pe(
    symbol: str, price_history_df: pd.DataFrame, period_years: int = 10
):
    """⚠ 估算历史PE序列（**非真实估值**）。

    模型：`PE ≈ 典型区间中值 × (价格 / 价格中位数)`，再夹到硬编码区间。
    也就是说该"PE"本质是**价格的线性缩放**，不含任何基本面信息；
    由此算出的"PE 分位"实际是**价格分位**。仅在无真实估值源（乐咕）时兜底，
    调用方应以 `valuation_source` 标注"estimate"。
    """
    try:
        # 这里使用一个简化的PE估算模型
        # 实际应用中，需要获取指数成分股的财务数据来精确计算

        # 方法1: 使用历史PE均值作为参考
        # 从外部数据源获取一个大致的PE范围（这里使用常见指数的典型PE范围）

        # 根据指数类型设定初始PE估算
        typical_pe_ranges = {
            "sh000001": (8, 25),  # 上证指数
            "sz399300": (10, 20),  # 沪深300
            "sh000300": (10, 20),  # 沪深300
            "sz399001": (15, 35),  # 深证成指
            "sz399006": (20, 50),  # 创业板指
            "sh000688": (30, 80),  # 科创50
            "sh000016": (8, 20),  # 上证50
            "sz399905": (15, 30),  # 中证500
        }

        # 获取典型PE范围
        if symbol in typical_pe_ranges:
            min_pe, max_pe = typical_pe_ranges[symbol]
            avg_pe = (min_pe + max_pe) / 2
        else:
            # 默认使用一个常见的PE范围
            avg_pe = 15.0

        # 基于价格波动估算PE变化
        # 假设PE与价格成反比变化（价格高时PE高，价格低时PE低）
        prices = price_history_df["close"].values
        base_price = np.median(prices)  # 使用中位数作为基准

        # 简化的PE估算：价格相对于基准的变化会影响PE
        pe_estimates = []
        for price in prices:
            # 价格越高，PE相对越高；价格越低，PE相对越低
            # 使用线性插值在典型范围内调整
            price_ratio = price / base_price
            estimated_pe = avg_pe * price_ratio
            # 限制在合理范围内
            estimated_pe = max(
                min_pe if symbol in typical_pe_ranges else 5,
                min(max_pe if symbol in typical_pe_ranges else 30, estimated_pe),
            )
            pe_estimates.append(estimated_pe)

        return pe_estimates
    except Exception as e:
        logger.error(f"估算 {symbol} 历史PE失败: {e}")
        return None


def estimate_historical_pb(
    symbol: str, price_history_df: pd.DataFrame, period_years: int = 10
):
    """⚠ 估算历史PB序列（**非真实估值**）。

    模型：`PB ≈ 典型区间中值 × (0.8 + 0.4×价格/价格中位数)`，夹到硬编码区间 ——
    同样只是价格的缩放，不含基本面信息。仅作无真实估值源时的兜底。
    """
    try:
        # PB估算模型
        # PB反映了市场价格相对于净资产的溢价程度

        typical_pb_ranges = {
            "sh000001": (1.0, 2.5),  # 上证指数
            "sz399300": (1.2, 2.0),  # 沪深300
            "sh000300": (1.2, 2.0),  # 沪深300
            "sz399001": (1.5, 3.5),  # 深证成指
            "sz399006": (2.0, 6.0),  # 创业板指
            "sh000688": (2.5, 6.0),  # 科创50
            "sh000016": (0.8, 2.0),  # 上证50
            "sz399905": (1.0, 2.5),  # 中证500
        }

        # 获取典型PB范围
        if symbol in typical_pb_ranges:
            min_pb, max_pb = typical_pb_ranges[symbol]
            avg_pb = (min_pb + max_pb) / 2
        else:
            # 默认使用一个常见的PB范围
            avg_pb = 1.8

        # 基于价格波动估算PB变化
        prices = price_history_df["close"].values
        base_price = np.median(prices)

        # 简化的PB估算：市场情绪会影响PB水平
        pb_estimates = []
        for price in prices:
            # 根据市场情绪和价格水平估算PB
            price_ratio = price / base_price
            estimated_pb = avg_pb * (0.8 + 0.4 * price_ratio)  # 在一定范围内波动
            # 限制在合理范围内
            estimated_pb = max(
                min_pb if symbol in typical_pb_ranges else 0.5,
                min(max_pb if symbol in typical_pb_ranges else 5.0, estimated_pb),
            )
            pb_estimates.append(estimated_pb)

        return pb_estimates
    except Exception as e:
        logger.error(f"估算 {symbol} 历史PB失败: {e}")
        return None


def get_enhanced_index_data(symbol: str):
    """单只指数的综合数据：价格 + 估值（PE/PB/分位）。

    估值优先级：
      1) `_valuation_from_legulegu` —— **真实** PE/PB（仅少数大盘指数，月频）；
      2) 回退：价格缩放估算（`estimate_historical_pe/pb`，**非真实估值**），
         `valuation_source` 标注为 estimate，前端可据此提示"估算"。
    性能：估值分位与当前值共用**同一次**历史取数（原先分别取 3 次）。
    """
    cache_key = f"enhanced_index_data_v8_{symbol}"
    cached_data = get_index_cached_data(cache_key)
    if cached_data is not None and isinstance(cached_data, dict):
        return cached_data

    try:
        # 1) 真实估值（乐咕，月频）：**页面路径只读缓存，不阻塞**；缺失则触发后台补齐
        real = _valuation_from_legulegu(symbol, allow_fetch=False)
        if not real and symbol in _REAL_SYMBOLS:
            warm_real_valuations()          # 后台线程补齐，本次先用兜底值
        if real.get("pe") is not None:
            pe, pb = real["pe"], real["pb"]
            pe_pct, pb_pct = real.get("pe_percentile"), real.get("pb_percentile")
            source = real.get("valuation_source")
            valuation_data = real
        else:
            # 2) 回退：一次 10Y 历史，同时算当前值(末值)与分位
            history = get_index_history(symbol, period="10Y")
            df = pd.DataFrame(history or [])
            if not df.empty:
                df["date"] = pd.to_datetime(df["date"])
                df = df.sort_values("date").reset_index(drop=True)
            pe_hist = estimate_historical_pe(symbol, df, 10) if not df.empty else None
            pb_hist = estimate_historical_pb(symbol, df, 10) if not df.empty else None
            pe = float(pd.Series(pe_hist).dropna().iloc[-1]) if pe_hist else None
            pb = float(pd.Series(pb_hist).dropna().iloc[-1]) if pb_hist else None
            pe_pct = _series_percentile(pe_hist, 10) if pe_hist else None
            pb_pct = _series_percentile(pb_hist, 10) if pb_hist else None
            source = "estimate(价格缩放·非真实估值)" if pe is not None else None
            valuation_data = {}

        # 价格快照（spot 全量，模块内已缓存 24h）
        spot_data = get_sina_index_spot_data()
        current_data = (spot_data[spot_data["代码"] == symbol]
                        if not spot_data.empty else pd.DataFrame())
        price_data = {}
        if not current_data.empty:
            try:
                price_data = current_data.iloc[0].to_dict()
            except Exception as e:  # noqa: BLE001
                logger.error(f"获取价格数据时出现错误 {symbol}: {e}")

        enhanced_data = {
            "symbol": symbol,
            "name": INDEX_SYMBOL_TO_NAME_MAP.get(symbol, ""),
            "price_data": price_data,
            "valuation_data": valuation_data,
            "pe": pe, "pb": pb,
            "pe_percentile": pe_pct, "pb_percentile": pb_pct,
            "valuation_source": source,
            "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
        # 大盘指数若暂时回退到估算（真实估值后台补齐中），只缓存 10 分钟以便尽快刷新
        _fallback_real = (symbol in _REAL_SYMBOLS
                          and str(source or "").startswith("estimate"))
        ttl = 600 if _fallback_real else 3 * 24 * 3600
        set_index_cache_data(cache_key, enhanced_data, cache_duration=ttl)
        return enhanced_data
    except Exception as e:
        logger.error(f"获取增强的指数数据失败 {symbol}: {e}")
        return {}


def get_index_chart_data(
    symbols: List[str], period: str = "12M", use_growth_rate: bool = True
):
    """
    准备指数图表数据，返回适合ECharts展示的格式
    :param symbols: 指数代码列表
    :param period: 时间周期
    :param use_growth_rate: 是否使用增长率对比
    :return: 适合ECharts展示的数据格式
    """
    cache_key = f"prepared_index_chart_data_v3_{','.join(sorted(symbols))}_{period}_{use_growth_rate}"

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
        chart_data = {"dates": [], "series": []}

        # 收集所有日期并去重排序
        all_dates = set()
        for symbol, history in multi_history_data.items():
            for item in history:
                all_dates.add(item["date"])
        chart_data["dates"] = sorted(list(all_dates))

        # 为每个指数生成系列数据
        for symbol in symbols:
            if symbol in multi_history_data:
                history = multi_history_data[symbol]
                # 为了匹配日期轴，创建完整的数据序列（缺失日期填充为None）
                series_data = []
                date_to_value = {item["date"]: item for item in history}

                if use_growth_rate and len(history) > 0:
                    # 使用增长率计算
                    growth_rates = calculate_growth_rate(history)
                    # 将增长率映射到对应日期
                    date_to_growth = {
                        item["date"]: item["growth_rate"] for item in growth_rates
                    }
                    for date in chart_data["dates"]:
                        if date in date_to_growth:
                            series_data.append(date_to_growth[date])
                        else:
                            series_data.append(None)
                else:
                    # 使用原始价格数据
                    for date in chart_data["dates"]:
                        if date in date_to_value:
                            series_data.append(date_to_value[date]["close"])
                        else:
                            series_data.append(None)

                # 获取指数名称
                index_name = INDEX_SYMBOL_TO_NAME_MAP.get(symbol, symbol)

                chart_data["series"].append({"name": index_name, "data": series_data})

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
