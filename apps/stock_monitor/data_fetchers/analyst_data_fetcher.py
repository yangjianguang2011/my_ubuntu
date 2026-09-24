# -*- coding: utf-8 -*-
"""分析师数据（东方财富，经 akshare）。

口径说明（重要）
================
akshare 只有两个分析师接口：

* ``stock_analyst_rank_em(year)``   —— 列表页排行，**只有 year 参数**
  （即「年度排行」，全市场前 100 名）
* ``stock_analyst_detail_em(...)``  —— 单分析师详情（最新跟踪 / 历史跟踪成份股）

因此本模块**只支持年度排行**，口径与东方财富页面「{年}最新排行」一致。

东方财富页面另有「3/6/12 个月排行」，那是**全市场**按对应收益率排序；
akshare 无法复现。早期实现把「年度前 100 名」按 3/6/12 个月收益率**本地重排**再取前 N，
得到的分析师集合与页面完全不同（导致统计结果对不上），故**不再这样做**。
3/6/12 个月收益率只作为**展示字段**保留（数据本就在年度榜同一行里）。

数据来源：akshare 的东财接口；字段名随年份变化（如 ``2026年收益率``），故年份一律动态取。
"""
import time
from datetime import date, datetime, timedelta

import akshare as ak

from config import setup_logger

logger = setup_logger(__name__)

from ..core.cache_with_database import cache_system  # noqa: E402

# 「最近更新」判定用的日期字段（按跟踪类型取第一个非空）
_UPDATED_DATE_FIELDS = {
    "最新跟踪成分股": ("最新评级日期", "调入日期"),  # 最近一次评级变动
    "历史跟踪成分股": ("调出日期", "调入日期"),      # 最近被调出
}
DEFAULT_INDICATOR = "最新跟踪成分股"


def _year() -> int:
    """当前年度（排行榜口径；随年份动态变化）。"""
    return datetime.now().year


# ---------------------------------------------------------------- 缓存


def get_analyst_cached_data(cache_key, cache_duration=None):
    """从分析师数据缓存获取数据。"""
    cached = cache_system.get_cached_data(cache_key, "analyst", cache_duration)
    logger.debug(f"{'命中' if cached is not None else '未命中'}缓存: {cache_key}")
    return cached


def set_analyst_cache_data(cache_key, data, cache_duration=None):
    """写入分析师数据缓存（先做 JSON 安全化处理）。"""
    cache_system.set_cache_data(
        cache_key, _convert_dates_to_strings(data), "analyst", cache_duration
    )
    logger.debug(f"已缓存: {cache_key}")


def _convert_dates_to_strings(obj):
    """递归把日期/缺失值转成 JSON 可序列化的形式；其余类型原样返回。

    缓存层用 ``json.dumps``，所以 numpy 标量、pandas 缺失值都必须在这里处理掉。
    """
    if isinstance(obj, dict):
        return {k: _convert_dates_to_strings(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_convert_dates_to_strings(v) for v in obj]
    if obj is None or isinstance(obj, (str, bool, int, float)):
        return obj

    # pandas / numpy 缺失值
    try:
        import pandas as pd

        if obj is pd.NaT or pd.isna(obj):
            return None
    except (TypeError, ValueError, ImportError):
        pass

    if hasattr(obj, "isoformat"):          # datetime / date / pd.Timestamp
        return obj.isoformat()
    if hasattr(obj, "item"):               # numpy 标量（np.int64 / np.float64 / …）
        try:
            v = obj.item()
            return v.isoformat() if hasattr(v, "isoformat") else v
        except (ValueError, AttributeError):
            pass
    return str(obj)


# ---------------------------------------------------------------- 长期历史


def save_analyst_history_data(stock_code, day, analyst_count):
    """把某只股票当日的分析师关注数量写入长期存储（永不过期）。"""
    try:
        from ..core.cache_with_database import store_long_term_data

        key = f"analyst_history:{stock_code}:{day}"
        data = {"stock_code": stock_code, "date": day, "analyst_count": analyst_count}
        ok = store_long_term_data(key, data, "analyst", None)
        if ok:
            logger.debug(f"历史关注数已保存: {key} = {analyst_count}")
        else:
            logger.warning(f"历史关注数保存失败: {key}")
        return ok
    except Exception as e:  # noqa: BLE001
        logger.error(f"保存分析师历史数据失败: {e}")
        return False


# ---------------------------------------------------------------- 数据获取


def get_analyst_rank_data():
    """获取**年度**分析师排行榜（全市场前 100，保持接口原始顺序）。

    收益率字段名带年份（如 ``2026年收益率``），故动态取，不再写死年份。
    """
    year = _year()
    cache_key = f"analyst_rank_{year}"
    cached = get_analyst_cached_data(cache_key)
    if cached is not None:
        logger.info(f"从缓存返回 {year} 年度分析师排行")
        return cached

    try:
        logger.info(f"获取 {year} 年度分析师排行榜…")
        df = ak.stock_analyst_rank_em(year=str(year))
        records = df.to_dict("records")
        set_analyst_cache_data(cache_key, records, cache_duration=24 * 3600)
        logger.info(f"!akshare!获取到 {len(records)} 条分析师排行数据")
        return records
    except Exception as e:  # noqa: BLE001
        logger.error(f"获取 {year} 年度分析师排行失败: {e}")
        return []


def _fetch_analyst_stocks(analyst_id, analyst_name, indicator=DEFAULT_INDICATOR):
    """获取单个分析师的跟踪成份股（带缓存）。

    注：`成分股个数=0` 的分析师调该接口会抛 `TypeError`（akshare 内部对 None 取下标），
    调用方应先按 `成分股个数` 过滤；此处仍保留兜底。
    """
    cache_key = f"analyst_stocks_{analyst_id}_{indicator}"
    cached = get_analyst_cached_data(cache_key)
    if cached is not None:
        logger.debug(f"从缓存获取 {analyst_name}({analyst_id}) 的 {indicator}")
        return cached

    try:
        from akshare import stock_analyst_detail_em

        time.sleep(0.1)  # 轻微限速，避免请求过密
        df = stock_analyst_detail_em(analyst_id=str(analyst_id), indicator=indicator)
        stocks = df.to_dict("records")
        set_analyst_cache_data(cache_key, stocks)
        logger.info(f"!akshare!{analyst_name}({analyst_id}) 获取到 {len(stocks)} 只{indicator}")
        return stocks
    except Exception as e:  # noqa: BLE001
        logger.warning(f"获取 {analyst_name}({analyst_id}) 的{indicator}失败: {e}")
        return []


def _get_combined_analyst_data(top_analysts=50, top_stocks=50):
    """前 N 名分析师的「最新跟踪成份股」聚合 → 重点关注股票（按被关注数排序）。"""
    cache_key = f"combined_analyst_data_{top_analysts}_{top_stocks}"
    cached = get_analyst_cached_data(cache_key)
    if cached is not None:
        logger.info("从缓存返回组合分析师数据")
        return cached

    try:
        rank_data = get_analyst_rank_data()
        if not rank_data:
            logger.warning("未能获取分析师排行数据")
            return {"top_focus_stocks": [], "latest_tracking": []}

        top_analysts_data = rank_data[:top_analysts]
        logger.info(f"取前 {len(top_analysts_data)} 名分析师（共 {len(rank_data)} 名）")

        stock_counter = {}
        all_latest_tracking = []
        processed = 0

        for idx, analyst in enumerate(top_analysts_data, 1):
            name = analyst.get("分析师名称", "")
            analyst_id = analyst.get("分析师ID", "")
            tracked = int(analyst.get("成分股个数") or 0)
            if not analyst_id or tracked <= 0:
                logger.debug(f"跳过 {name}({analyst_id})：无跟踪成份股")
                continue

            stocks = _fetch_analyst_stocks(analyst_id, name, DEFAULT_INDICATOR)
            processed += 1

            for stock in stocks:
                code = str(stock.get("股票代码", "")).strip().upper()
                stock_name = str(stock.get("股票名称", "")).strip()
                if not (code and stock_name):
                    continue

                info = stock_counter.get(code)
                if info is None:
                    info = {
                        "stock_code": code,
                        "stock_name": stock_name,
                        "analyst_count": 0,
                        "trade_prices": [],
                        "latest_price": None,
                    }
                    stock_counter[code] = info
                info["analyst_count"] += 1

                trade = _to_float(stock.get("成交价格(前复权)"))
                if trade is not None:
                    info["trade_prices"].append(trade)
                if info["latest_price"] is None:
                    info["latest_price"] = _to_float(stock.get("最新价格"))

                all_latest_tracking.append(
                    {**stock, "analyst_name": name, "analyst_rank": idx}
                )

        # 价格统计
        for info in stock_counter.values():
            prices = info.pop("trade_prices")
            if prices:
                info["avg_price"] = round(sum(prices) / len(prices), 2)
                info["max_price"] = max(prices)
                info["min_price"] = min(prices)
            else:
                info["avg_price"] = info["max_price"] = info["min_price"] = 0

        focus = sorted(stock_counter.values(),
                       key=lambda x: x["analyst_count"], reverse=True)[:top_stocks]
        unique = len(stock_counter)
        multi = sum(1 for s in stock_counter.values() if s["analyst_count"] > 1)
        logger.info(f"处理 {processed} 位分析师 → {unique} 只唯一股票（其中 {multi} 只被多人关注）")

        # 历史关注数：仅默认参数下记录（避免多组参数写重复点）
        if top_analysts == 50 and top_stocks == 50:
            today = date.today().strftime("%Y-%m-%d")
            for s in focus:
                save_analyst_history_data(s["stock_code"], today, s["analyst_count"])

        result = {
            "top_focus_stocks": focus,
            "latest_tracking": all_latest_tracking,
            "total_analysts_processed": processed,
            "latest_focus_stocks": multi,
            "latest_unique_stocks": unique,
        }
        set_analyst_cache_data(cache_key, result)
        logger.info(f"组合数据完成：{len(focus)} 只重点股票，{len(all_latest_tracking)} 条最新跟踪")
        return result

    except Exception as e:  # noqa: BLE001
        logger.error(f"获取组合分析师数据失败: {e}", exc_info=True)
        return {"top_focus_stocks": [], "latest_tracking": []}


def _to_float(value):
    """把 akshare 的价格/涨跌值转 float；空值/占位符/非数字 → None。"""
    if value is None or value == "" or value == "--":
        return None
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    return None if f != f else f  # NaN → None


# ---------------------------------------------------------------- 对外接口


def get_analyst_focus_stocks(top_analysts=50, top_stocks=50):
    """分析师重点关注股票（按被多少位分析师跟踪排序）。"""
    cache_key = f"analyst_focus_stocks_{top_analysts}_{top_stocks}"
    cached = get_analyst_cached_data(cache_key)
    if cached is not None:
        logger.info("从缓存返回分析师重点关注股票")
        return cached

    combined = _get_combined_analyst_data(top_analysts, top_stocks)
    result = {
        "top_focus_stocks": combined.get("top_focus_stocks", []),
        "total_analysts_processed": combined.get("total_analysts_processed", 0),
        "latest_unique_stocks": combined.get("latest_unique_stocks", 0),
        "latest_focus_stocks": combined.get("latest_focus_stocks", 0),
    }
    set_analyst_cache_data(cache_key, result)
    return result


def get_analyst_latest_tracking(top_analysts=50, top_stocks=50):
    """最新跟踪成份股明细（前 N 名分析师的原始记录）。"""
    cache_key = f"latest_analyst_tracking_{top_analysts}_{top_stocks}"
    cached = get_analyst_cached_data(cache_key)
    if cached is not None:
        logger.info("从缓存返回最新跟踪成份股")
        return cached

    combined = _get_combined_analyst_data(top_analysts, top_stocks)
    latest = combined.get("latest_tracking", [])
    set_analyst_cache_data(cache_key, latest)
    logger.info(f"最新跟踪成份股：{len(latest)} 条")
    return latest


def get_analyst_updated_stocks(days=30, indicator=DEFAULT_INDICATOR):
    """最近 N 天内「有更新」的跟踪成份股。

    「更新」的判定字段按跟踪类型取（见 `_UPDATED_DATE_FIELDS`）：
    最新跟踪看「最新评级日期」，历史跟踪看「调出日期」，缺失时退回「调入日期」。
    """
    if indicator not in _UPDATED_DATE_FIELDS:
        raise ValueError(f"未知跟踪类型：{indicator}（可选：{list(_UPDATED_DATE_FIELDS)}）")

    threshold = (datetime.now() - timedelta(days=days)).date()
    cache_key = f"recently_updated_stocks_{days}_{indicator}"
    cached = get_analyst_cached_data(cache_key)
    if cached is not None:
        logger.info(f"从缓存返回最近更新股票（{days} 天 / {indicator}）")
        return cached

    try:
        logger.info(f"获取最近更新股票：{days} 天 / {indicator}")
        rank_data = get_analyst_rank_data()
        date_fields = _UPDATED_DATE_FIELDS[indicator]

        recent = []
        for analyst in rank_data:
            updated = _parse_date(analyst.get("更新日期"))
            if updated is None or updated < threshold:
                continue
            name = analyst.get("分析师名称", "")
            analyst_id = analyst.get("分析师ID", "")
            if not analyst_id or int(analyst.get("成分股个数") or 0) <= 0:
                continue

            for stock in _fetch_analyst_stocks(analyst_id, name, indicator):
                day = next((_parse_date(stock.get(f)) for f in date_fields
                            if _parse_date(stock.get(f))), None)
                if day is None or day < threshold:
                    continue
                stock = dict(stock)
                stock["analyst_name"] = name
                stock["analyst_period_3m_return"] = analyst.get("3个月收益率", "")
                stock["analyst_period_6m_return"] = analyst.get("6个月收益率", "")
                stock["analyst_period_12m_return"] = analyst.get("12个月收益率", "")
                recent.append(stock)

        logger.info(f"最近 {days} 天内更新的{indicator}：{len(recent)} 条")
        set_analyst_cache_data(cache_key, recent)
        return recent
    except Exception as e:  # noqa: BLE001
        logger.error(f"获取最近更新股票失败: {e}", exc_info=True)
        return []


def _parse_date(value):
    """把 akshare 的日期（date / datetime / 'YYYY-MM-DD' / 'YYYY-MM-DD HH:MM:SS'）转成 date。"""
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value).strip()
    for fmt in ("%Y-%m-%d", "%Y-%m-%d %H:%M:%S", "%Y/%m/%d"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def get_analyst_history_tracking(stock_code, days=360):
    """某只股票的「分析师关注数量」历史序列（来自长期存储）。"""
    try:
        from ..core.cache_with_database import get_module_long_term_data

        end = datetime.now().date()
        start = end - timedelta(days=days)

        rows = []
        for item in get_module_long_term_data("analyst"):
            data = item.get("data") or {}
            day = _parse_date(data.get("date"))
            if data.get("stock_code") == stock_code and day and start <= day <= end:
                rows.append(data)

        rows.sort(key=lambda x: x["date"])
        logger.info(f"获取到 {len(rows)} 条 {stock_code} 的历史关注数")
        return {"dates": [r["date"] for r in rows],
                "analyst_counts": [r["analyst_count"] for r in rows]}
    except Exception as e:  # noqa: BLE001
        logger.error(f"获取股票 {stock_code} 历史关注数失败: {e}")
        return None
