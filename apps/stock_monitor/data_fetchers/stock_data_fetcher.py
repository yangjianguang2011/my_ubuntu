import akshare as ak
import easyquotation
import pandas as pd

from config import setup_logger

logger = setup_logger(__name__)
from datetime import datetime, timedelta

import numpy as np

# 使用混合缓存（内存+数据库），以SQLite作为二级缓存
from ..core.cache_with_database import cache_system


def get_stock_cached_data(cache_key, cache_duration=None):
    """
    从缓存获取数据
    :param cache_key: 缓存键
    :param cache_duration: 缓存有效时间（秒），如果为None则使用环境变量配置
    :return: 缓存的数据或None
    """
    return cache_system.get_cached_data(cache_key, "stock", cache_duration)


def set_stock_cache_data(cache_key, data):
    """
    设置缓存数据
    :param cache_key: 缓存键
    :param data: 要缓存的数据
    """
    cache_system.set_cache_data(cache_key, data, "stock")
    # logger.info(f"股票数据已缓存: {cache_key}")


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
        normalized_code = original_code  # 保持6位A股代码不变
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
    stock_code = stock["code"]
    stock_name = stock["name"]

    # 使用股票名称和代码作为缓存键
    cache_key = f"stock_info_{stock_name}_{stock_code}"
    cached_data = get_stock_cached_data(cache_key)
    if cached_data is not None:
        # logger.info(f"从缓存返回股票 {stock_name}({stock_code}) 的信息")
        return cached_data

    logger.info(f"开始获取股票 {stock_name}({stock_code}) 的详细信息")

    try:
        # 使用新的市场判断函数
        normalized_code, is_hk_stock = determine_market_type(stock_code)

        if is_hk_stock is None:
            # 格式错误的情况
            result = {
                "stock_code": stock_code,
                "stock_name": stock_name,
                "price": None,
                "change_amount": None,
                "change_pct": None,
                "turnover_rate": None,
                "pe_ratio": None,
                "total_market_value": None,
                "volume": None,
            }
            # 不缓存失败的结果，以便下次重试
            return result

        if is_hk_stock:
            # 港股，使用hkquote接口
            quotation = easyquotation.use("hkquote")
            stock_data = quotation.stocks([normalized_code])
        else:
            # A股使用sina接口
            quotation = easyquotation.use("sina")
            stock_data = quotation.stocks([normalized_code])

        if not stock_data or normalized_code not in stock_data:
            logger.warning(f"无法获取股票 {normalized_code} 的数据")
            result = {
                "stock_code": normalized_code,
                "stock_name": stock_name,
                "price": None,
                "change_amount": None,
                "change_pct": None,
                "turnover_rate": None,
                "pe_ratio": None,
                "total_market_value": None,
                "volume": None,
            }
            # 不缓存失败的结果，以便下次重试
            return result

        stock_info = stock_data[normalized_code]

        # 初始化返回值 - 根据股票类型处理不同的数据格式
        if is_hk_stock:
            # 港股数据格式
            result = {
                "stock_code": normalized_code,
                "stock_name": stock_name,
                "price": (
                    float(stock_info["price"])
                    if stock_info.get("price")
                    and stock_info["price"] != ""
                    and stock_info["price"] != "0"
                    else None
                ),  # 当前价格
                "open_price": (
                    float(stock_info["openPrice"])
                    if stock_info.get("openPrice")
                    and stock_info["openPrice"] != ""
                    and stock_info["openPrice"] != "0"
                    else None
                ),  # 开盘价
                "prev_close": (
                    float(stock_info["lastPrice"])
                    if stock_info.get("lastPrice")
                    and stock_info["lastPrice"] != ""
                    and stock_info["lastPrice"] != "0"
                    else None
                ),  # 昨收
                "high_price": (
                    float(stock_info["high"])
                    if stock_info.get("high")
                    and stock_info["high"] != ""
                    and stock_info["high"] != "0"
                    else None
                ),  # 最高价
                "low_price": (
                    float(stock_info["low"])
                    if stock_info.get("low")
                    and stock_info["low"] != ""
                    and stock_info["low"] != "0"
                    else None
                ),  # 最低价
                "volume": stock_info.get("volume_2"),  # 成交量
                "turnover_value": stock_info.get("amountYuan"),  # 成交额
                "date": stock_info.get("date"),  # 日期
                "time": stock_info.get("time"),  # 时间
                "change_amount": (
                    float(stock_info["price"]) - float(stock_info["lastPrice"])
                    if stock_info.get("price") and stock_info.get("lastPrice")
                    else None
                ),  # 涨跌额
                "change_pct": (
                    float(stock_info["dtd"]) if stock_info.get("dtd") else None
                ),  # 涨跌幅
            }
        else:
            # A股数据格式
            result = {
                "stock_code": normalized_code,
                "stock_name": stock_name,
                "price": (
                    float(stock_info["now"])
                    if stock_info.get("now")
                    and stock_info["now"] != ""
                    and stock_info["now"] != "0"
                    else None
                ),  # 当前价格
                "open_price": (
                    float(stock_info["open"])
                    if stock_info.get("open")
                    and stock_info["open"] != ""
                    and stock_info["open"] != "0"
                    else None
                ),  # 开盘价
                "prev_close": (
                    float(stock_info["close"])
                    if stock_info.get("close")
                    and stock_info["close"] != ""
                    and stock_info["close"] != "0"
                    else None
                ),  # 昨收
                "high_price": (
                    float(stock_info["high"])
                    if stock_info.get("high")
                    and stock_info["high"] != ""
                    and stock_info["high"] != "0"
                    else None
                ),  # 最高价
                "low_price": (
                    float(stock_info["low"])
                    if stock_info.get("low")
                    and stock_info["low"] != ""
                    and stock_info["low"] != "0"
                    else None
                ),  # 最低价
                "volume": stock_info.get("turnover"),  # 成交量
                "turnover_value": stock_info.get("volume"),  # 成交额
                "date": stock_info.get("date"),  # 日期
                "time": stock_info.get("time"),  # 时间
            }

            # 计算涨跌额和涨跌幅
            if result.get("prev_close") is not None and result.get("price") is not None:
                result["change_amount"] = round(
                    result["price"] - result["prev_close"], 2
                )
                result["change_pct"] = round(
                    (result["change_amount"] / result["prev_close"]) * 100, 2
                )
            else:
                result["change_amount"] = None
                result["change_pct"] = None

        # 从API数据中提取更多字段
        result["turnover_rate"] = (
            stock_info.get("turnover") if stock_info.get("turnover") else None
        )  # 换手率
        result["pe_ratio"] = None  # 市盈率
        result["total_market_value"] = (
            stock_info.get("MarketCap") if stock_info.get("MarketCap") else None
        )  # 总市值

        # 缓存获取到的数据
        set_stock_cache_data(cache_key, result)
        # logger.info(f"股票 {stock_name}({stock_code}) 详细信息获取完成: {result}")
        logger.info(f"股票 {stock_name}({normalized_code}) 详细信息获取完成")
        return result
    except Exception as e:
        logger.error(f"获取股票 {stock_name}({stock_code}) 详细信息时出错: {str(e)}")
        # 不缓存失败的结果，以便下次重试
        return {
            "stock_code": stock_code,
            "stock_name": stock_name,
            "price": None,
            "change_amount": None,
            "change_pct": None,
            "turnover_rate": None,
            "pe_ratio": None,
            "total_market_value": None,
            "volume": None,
        }


def _fetch_historical_data(stock_code, days=365):
    """
    获取股票历史数据
    :param stock_code: 股票代码
    :param days: 获取天数
    :return: 历史数据列表
    """
    # 在函数内部添加缓存
    cache_key = f"stock_history_{stock_code}_{days}d"
    cached_data = get_stock_cached_data(
        cache_key, cache_duration=3600 * 24
    )  # 缓存 1 天
    if cached_data is not None:
        return cached_data

    try:
        # 根据股票代码判断市场类型
        if len(stock_code) == 5:
            # 港股
            # 计算日期范围（过去 days 天）
            end_date = datetime.now()
            start_date = end_date - timedelta(
                days=days * 2
            )  # 多获取一些，以防停牌等情况
            start_date_str = start_date.strftime("%Y%m%d")
            end_date_str = end_date.strftime("%Y%m%d")

            df = None
            # 尝试多个数据源
            # 数据源 1: 东财接口 (stock_hk_hist)
            try:
                logger.info(f"嘗試使用港股接口獲取 {stock_code} 歷史數據...")
                df = ak.stock_hk_hist(
                    symbol=stock_code,
                    period="daily",
                    start_date=start_date_str,
                    end_date=end_date_str,
                    adjust="",
                )
                if df is not None and not df.empty:
                    logger.info(f"港股接口獲取 {stock_code} 歷史數據成功")
            except Exception as e:
                error_msg = f"港股接口獲取股票 {stock_code} 歷史數據失敗：{str(e)}"
                logger.warning(error_msg)

            # 数据源 2: 港股日线数据接口 (stock_hk_daily)
            if df is None or df.empty:
                try:
                    logger.info(
                        f"嘗試使用港股日線數據接口獲取 {stock_code} 歷史數據..."
                    )
                    df = ak.stock_hk_daily(symbol=stock_code, adjust="")
                    if df is not None and not df.empty:
                        logger.info(f"港股日線數據接口獲取 {stock_code} 歷史數據成功")
                        # 只取最近 days 天的数据
                        df = df.tail(days)
                except Exception as e:
                    error_msg = (
                        f"港股日線數據接口獲取股票 {stock_code} 歷史數據失敗：{str(e)}"
                    )
                    logger.warning(error_msg)

            if df is not None and not df.empty:
                # 重命名列以匹配预期格式
                if "日期" in df.columns:
                    # 中文列名
                    df.rename(
                        columns={
                            "日期": "date",
                            "开盘": "open",
                            "收盘": "close",
                            "最高": "high",
                            "最低": "low",
                            "成交量": "volume",
                            "成交额": "amount",
                            "涨跌幅": "change_pct",
                            "涨跌额": "change_amount",
                            "换手率": "turnover_rate",
                        },
                        inplace=True,
                    )
                else:
                    # 英文列名 - 处理不同数据源的列名映射
                    standard_cols = {
                        "trade_date": "date",
                        "open": "open",
                        "close": "close",
                        "high": "high",
                        "low": "low",
                        "vol": "volume",
                        "amount": "amount",
                        "pct_chg": "change_pct",
                        "change": "change_amount",
                        "turnover_rate": "turnover_rate",
                    }
                    # 只重命名存在的列
                    cols_to_rename = {
                        k: v for k, v in standard_cols.items() if k in df.columns
                    }
                    if cols_to_rename:
                        df.rename(columns=cols_to_rename, inplace=True)

                    # 如果缺少 change_pct 列，根据 close 价格计算
                    if "change_pct" not in df.columns and len(df) > 1:
                        df["change_pct"] = df["close"].pct_change() * 100

                    # 如果缺少 change_amount 列，根据 close 价格计算
                    if "change_amount" not in df.columns and len(df) > 1:
                        df["change_amount"] = df["close"].diff()

                # 转换日期格式
                if "date" in df.columns:
                    df["date"] = pd.to_datetime(df["date"]).dt.strftime("%Y-%m-%d")

                # 缓存数据
                result = df.to_dict("records")
                set_stock_cache_data(cache_key, result)
                return result

            return []  # 港股数据获取失败或无数据
        else:
            # A 股
            symbol = stock_code.zfill(6)  # 补全为 6 位

            # 获取历史数据
            if symbol.startswith("6"):
                symbol = f"sh{symbol}"
            else:
                symbol = f"sz{symbol}"

            # 尝试使用多個數據源
            df = None
            error_messages = []  # 記錄錯誤信息

            # 數據源優先級：
            # 1. 東財接口 (最穩定)
            # 2. 日線數據接口
            # 3. 腾訊接口
            # 4. 新浪接口

            # 數據源 1: 東財接口 (优先使用)
            try:
                logger.info(f"嘗試使用東財接口獲取 {stock_code} 歷史數據...")
                # 计算日期范围（过去 days 天）
                end_date = datetime.now()
                # start_date = end_date - timedelta(days=days * 2)  # 多获取一些，以防停牌等情况
                start_date = (
                    end_date - timedelta(days=days) - timedelta(days=7)
                )  # 确保至少有 days 天的数据
                start_date_str = start_date.strftime("%Y%m%d")
                end_date_str = end_date.strftime("%Y%m%d")
                # 使用纯数字代码，不带 sh/sz 前缀，带明确的日期参数
                df = ak.stock_zh_a_hist(
                    symbol=stock_code.zfill(6),
                    period="daily",
                    adjust="",
                    start_date=start_date_str,
                    end_date=end_date_str,
                )
                if df is not None and not df.empty:
                    logger.info(f"東財接口獲取 {stock_code} 歷史數據成功")
            except Exception as e:
                error_msg = f"東財接口獲取股票 {stock_code} 歷史數據失敗：{str(e)}"
                logger.warning(error_msg)
                error_messages.append(error_msg)

            # 如果東財接口失敗，嘗試日線數據接口
            if df is None or df.empty:
                try:
                    logger.info(f"嘗試使用日線數據接口獲取 {stock_code} 歷史數據...")
                    # 根据股票代码判断市场前缀：6 开头是沪市 (sh)，其余是深市 (sz)
                    market_prefix = (
                        "sh" if stock_code.zfill(6).startswith("6") else "sz"
                    )
                    df = ak.stock_zh_a_daily(
                        symbol=f"{market_prefix}{stock_code.zfill(6)}", adjust=""
                    )
                    if df is not None and not df.empty:
                        logger.info(f"日線數據接口獲取 {stock_code} 歷史數據成功")
                except Exception as e:
                    error_msg = (
                        f"日線數據接口獲取股票 {stock_code} 歷史數據失敗：{str(e)}"
                    )
                    logger.warning(error_msg)
                    error_messages.append(error_msg)

            # 如果前面的接口都失敗，嘗試騰訊接口
            if df is None or df.empty:
                try:
                    logger.info(f"嘗試使用騰訊接口獲取 {stock_code} 歷史數據...")
                    df = ak.stock_zh_a_hist_tx(
                        symbol=stock_code.zfill(6),
                        start_date="",
                        end_date="",
                        adjust="",
                    )
                    if df is not None and not df.empty:
                        logger.info(f"騰訊接口獲取 {stock_code} 歷史數據成功")
                except Exception as e:
                    error_msg = f"騰訊接口獲取股票 {stock_code} 歷史數據失敗：{str(e)}"
                    logger.warning(error_msg)
                    error_messages.append(error_msg)

            # 注意：新浪接口 (ak.stock_zh_a_hist_sina) 在 akshare 中不存在，已移除

            # 如果前面的接口都失败，尝试 easyquotation 的 daykline 接口
            if df is None or df.empty:
                try:
                    logger.info(
                        f"嘗試使用 easyquotation daykline 接口獲取 {stock_code} 歷史數據..."
                    )
                    quotation = easyquotation.use("daykline")
                    # 获取 365 天的数据
                    data = quotation.real([stock_code.zfill(6)])
                    if (
                        data
                        and stock_code.zfill(6) in data
                        and data[stock_code.zfill(6)]
                    ):
                        # 转换为 DataFrame
                        kline_data = data[stock_code.zfill(6)]
                        df = pd.DataFrame(
                            kline_data,
                            columns=["date", "open", "close", "high", "low", "volume"],
                        )
                        logger.info(
                            f"easyquotation daykline 接口獲取 {stock_code} 歷史數據成功"
                        )
                except Exception as e:
                    error_msg = f"easyquotation daykline 接口獲取股票 {stock_code} 歷史數據失敗：{str(e)}"
                    logger.warning(error_msg)
                    error_messages.append(error_msg)

            if df is not None and not df.empty:
                # 只取最近 days 天的数据
                df = df.tail(days)
                # 重命名列以匹配预期格式
                if "日期" in df.columns:
                    # 中文列名
                    df.rename(
                        columns={
                            "日期": "date",
                            "开盘": "open",
                            "收盘": "close",
                            "最高": "high",
                            "最低": "low",
                            "成交量": "volume",
                            "成交额": "amount",
                            "涨跌幅": "change_pct",
                            "涨跌额": "change_amount",
                            "换手率": "turnover_rate",
                        },
                        inplace=True,
                    )
                else:
                    # 英文列名 - 处理不同数据源的列名映射
                    standard_cols = {
                        "trade_date": "date",
                        "open": "open",
                        "close": "close",
                        "high": "high",
                        "low": "low",
                        "vol": "volume",
                        "amount": "amount",
                        "pct_chg": "change_pct",
                        "change": "change_amount",
                        "turnover_rate": "turnover_rate",
                        # 日线数据接口 (stock_zh_a_daily) 返回的列名
                        "turnover": "change_pct",  # turnover 列实际上是换手率，但这里先映射为 change_pct
                    }
                    # 只重命名存在的列
                    cols_to_rename = {
                        k: v for k, v in standard_cols.items() if k in df.columns
                    }
                    if cols_to_rename:
                        df.rename(columns=cols_to_rename, inplace=True)

                    # 特殊处理：日线数据接口返回的 outstanding_share 和 turnover 需要额外处理
                    # turnover 在手线接口中是换手率，但如果已被重命名为 change_pct，则需要重新计算
                    if "turnover_rate" not in df.columns and "turnover" in df.columns:
                        # turnover 已被重命名为 change_pct，需要从其他列计算换手率
                        pass  # 换手率可以后续计算，这里先跳过

                    # 如果缺少 change_pct 列，根据 close 价格计算
                    if "change_pct" not in df.columns and len(df) > 1:
                        df["change_pct"] = df["close"].pct_change() * 100

                    # 如果缺少 change_amount 列，根据 close 价格计算
                    if "change_amount" not in df.columns and len(df) > 1:
                        df["change_amount"] = df["close"].diff()

                # 转换日期格式
                if "date" in df.columns:
                    df["date"] = pd.to_datetime(df["date"]).dt.strftime("%Y-%m-%d")

                # 缓存数据
                result = df.to_dict("records")
                set_stock_cache_data(cache_key, result)
                return result
            else:
                logger.warning(f"股票 {stock_code} 没有获取到历史数据")
                logger.debug(f"所有尝试的接口都失败，错误信息：{error_messages}")
                return []
    except Exception as e:
        logger.error(f"获取股票 {stock_code} 历史数据失败：{str(e)}")
        return []


def _calculate_technical_indicators(historical_data):
    """
    计算技术指标（基于5、20、60日均线）
    :param historical_data: 历史数据
    :return: 技术指标字典
    """
    if not historical_data or len(historical_data) < 5:  # 至少需要5天数据来计算5日均线
        return {}

    # 转换为DataFrame进行计算
    df = pd.DataFrame(historical_data)
    df = df.sort_values("date")

    # 确保数值列是数值类型
    numeric_columns = ["open", "close", "high", "low", "volume"]
    for col in numeric_columns:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # 计算5、20、60日移动平均线
    df["ma5"] = df["close"].rolling(window=5).mean()
    df["ma20"] = df["close"].rolling(window=20).mean()
    df["ma60"] = (
        df["close"].rolling(window=60).mean()
        if len(df) >= 60
        else df["close"].rolling(window=len(df)).mean()
    )

    # 计算其他技术指标
    # RSI
    if len(df) >= 14:
        delta = df["close"].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        df["rsi"] = 100 - (100 / (1 + rs))
    else:
        df["rsi"] = np.nan

    # MACD
    if len(df) >= 26:
        exp1 = df["close"].ewm(span=12).mean()
        exp2 = df["close"].ewm(span=26).mean()
        df["dif"] = exp1 - exp2
        df["dea"] = df["dif"].ewm(span=9).mean()
        df["macd"] = (df["dif"] - df["dea"]) * 2
    else:
        df["dif"] = np.nan
        df["dea"] = np.nan
        df["macd"] = np.nan

    # 乖离率（基于5、20、60日均线）
    df["bias_ma5"] = ((df["close"] - df["ma5"]) / df["ma5"] * 100).round(2)
    df["bias_ma20"] = ((df["close"] - df["ma20"]) / df["ma20"] * 100).round(2)
    df["bias_ma60"] = (
        ((df["close"] - df["ma60"]) / df["ma60"] * 100).round(2)
        if "ma60" in df.columns
        else np.nan
    )

    # 趋势判断（基于5、20、60日均线）
    latest = df.iloc[-1]

    def _determine_trend_status_5_20_60(latest_row):
        ma5 = latest_row["ma5"]
        ma20 = latest_row["ma20"]
        ma60 = latest_row["ma60"] if "ma60" in latest_row else np.nan

        if pd.notna(ma5) and pd.notna(ma20) and pd.notna(ma60):
            if ma5 > ma20 > ma60:
                return "多头排列（强势）"
            elif ma5 > ma20 and ma20 > ma60 * 0.98:  # 允许轻微偏差
                return "多头排列（偏强）"
            elif ma5 < ma20 < ma60:
                return "空头排列（弱势）"
            elif ma5 < ma20 and ma20 < ma60 * 1.02:  # 允许轻微偏差
                return "空头排列（偏弱）"
            else:
                return "均线缠绕（震荡）"
        else:
            return "数据不足"

    trend_status = _determine_trend_status_5_20_60(latest)

    # 获取最新的技术指标值
    indicators = {
        "ma5": round(latest["ma5"], 2) if pd.notna(latest["ma5"]) else None,
        "ma20": round(latest["ma20"], 2) if pd.notna(latest["ma20"]) else None,
        "ma60": (
            round(latest["ma60"], 2)
            if "ma60" in latest and pd.notna(latest["ma60"])
            else None
        ),
        "rsi": round(latest["rsi"], 2) if pd.notna(latest["rsi"]) else None,
        "macd": round(latest["macd"], 4) if pd.notna(latest["macd"]) else None,
        "dif": round(latest["dif"], 4) if pd.notna(latest["dif"]) else None,
        "dea": round(latest["dea"], 4) if pd.notna(latest["dea"]) else None,
        "bias_ma5": (
            round(latest["bias_ma5"], 2) if pd.notna(latest["bias_ma5"]) else None
        ),
        "bias_ma20": (
            round(latest["bias_ma20"], 2) if pd.notna(latest["bias_ma20"]) else None
        ),
        "bias_ma60": (
            round(latest["bias_ma60"], 2) if pd.notna(latest["bias_ma60"]) else None
        ),
        "trend_status": trend_status,
        "volume_ratio": latest.get("volume_ratio", 1.0),
        "turnover_rate": latest.get("turnover_rate", 0.0),
    }

    return indicators


def get_enhanced_stock_info(stock):
    """
    获取增强的股票信息，包含技术指标
    :param stock: 股票对象，包含name和code字段
    :return: 包含技术指标的股票信息字典
    """
    stock_code = stock["code"]
    stock_name = stock["name"]

    # 使用股票名称和代码作为缓存键
    cache_key = f"enhanced_stock_info_{stock_name}_{stock_code}"
    cached_data = get_stock_cached_data(cache_key, cache_duration=1800)  # 缓存30分钟
    if cached_data is not None:
        return cached_data

    logger.info(f"开始获取增强的股票 {stock_name}({stock_code}) 信息")

    try:
        # 获取基础股票信息
        basic_info = get_stock_info(stock)

        # 获取历史数据用于计算技术指标
        historical_data = _fetch_historical_data(stock_code, days=365)

        # 计算技术指标
        tech_indicators = _calculate_technical_indicators(historical_data)

        # 合并数据
        enhanced_info = {**basic_info, **tech_indicators}

        # 缓存增强的信息
        set_stock_cache_data(cache_key, enhanced_info)

        logger.info(f"tech_indicators: {tech_indicators}")
        logger.info(
            f"增强的股票 {stock_name}({stock_code}) 信息获取完成: {enhanced_info}"
        )
        logger.info(f"股票 {stock_name}({stock_code}) 增强信息获取完成")
        return enhanced_info
    except Exception as e:
        logger.error(f"获取增强股票信息 {stock_name}({stock_code}) 时出错: {str(e)}")
        # 返回基础信息，即使技术指标计算失败
        return get_stock_info(stock)


def get_stock_price_by_code(stock_code):
    """
    根据股票代码获取股票价格
    :param stock_code: 股票代码
    :return: 股票价格（浮点数）或None
    """
    # 创建一个模拟的股票对象用于调用新的get_stock_info函数
    stock = {"name": "Unknown", "code": stock_code}
    stock_info = get_stock_info(stock)
    if stock_info and "price" in stock_info:
        return stock_info["price"]
    return None


if __name__ == "__main__":
    print("测试股票数据获取功能...")

    # 从配置文件加载股票信息
    import json
    import os

    from config import get_path

    stocks_file = get_path("stocks_file", "./stocks.json")

    print(f"从配置文件 {stocks_file} 加载股票信息...")

    # 检查配置文件是否存在
    if os.path.exists(stocks_file):
        with open(stocks_file, "r", encoding="utf-8") as f:
            stocks = json.load(f)
        print(f"成功加载 {len(stocks)} 只监控股票")
    else:
        print(f"配置文件 {stocks_file} 不存在，使用默认股票进行测试")
        # 使用默认股票列表进行测试
        stocks = [
            {"name": "平安银行", "code": "000001"},
            {"name": "贵州茅台", "code": "600519"},
            {"name": "招商银行", "code": "600036"},
        ]
    stock = {"name": "金力永磁", "code": "300748"}

    enhanced_info = get_enhanced_stock_info(stock)
    print(f"获取到增强股票信息: {enhanced_info}")

    # if stocks:
    #     print("\n1. 测试获取配置文件中的股票信息:")
    #     for i, stock in enumerate(stocks[3:]):  # 只测试前3只股票
    #         print(f"\n测试第 {i+1} 只股票: {stock['name']}({stock['code']})")
    #         stock_info = get_stock_info(stock)
    #         print(f"获取到股票信息: 价格={stock_info.get('price')}, 涨跌幅={stock_info.get('change_pct')}")
    #         enhanced_info = get_enhanced_stock_info(stock)
    #         print(f"获取到增强股票信息: {enhanced_info}")

    #     print("\n2. 测试获取股票价格:")
    #     for i, stock in enumerate(stocks[:3]):  # 只测试前3只股票
    #         stock_price = get_stock_price_by_code(stock['code'])
    #         print(f"股票 {stock['code']}({stock['name']}) 的价格: {stock_price}")
    # else:
    #     print("配置文件中没有股票信息，使用默认股票进行测试")
    #     # 使用默认股票进行测试
    #     default_stock = {'name': '平安银行', 'code': '00001'}
    #     print(f"\n测试股票: {default_stock['name']}({default_stock['code']})")
    #     stock_info = get_stock_info(default_stock)
    #     print(f"获取到股票信息: 价格={stock_info.get('price')}, 涨跌幅={stock_info.get('change_pct')}")

    #     stock_price = get_stock_price_by_code(default_stock['code'])
    #     print(f"股票 {default_stock['code']} 的价格: {stock_price}")
