# -*- coding: utf-8 -*-
"""
共享技术指标 —— 均线 / 排列 / 金叉 / 斜率 / 乖离。

由原 `analyzers/picker_rules.py`（指标层）与 `analyzers/trend_trading_analyzer.py`
（`_prepare_data` / `_calculate_trend_slope` / `_is_bullish_arrangement` / `_is_near_price`）
里的重复实现合并而来：**纯计算、无 IO、无业务语义**，两个调用方各自保留自己的规则语义。

约定：
  * 输入统一为**按 date 升序**的 DataFrame（至少含 `close`；可用列 date/open/high/low/close/volume）
  * `records_to_frame()` 负责把各种来源的 records 规整成该形状
  * 斜率有**两种口径，不可互换**：
      - `slope_pct`        首尾变化率（轻量，供选股规则）
      - `slope_regression` 线性回归（`log=True` = 对数收益斜率，供趋势分析）
"""
from __future__ import annotations

from typing import List, Optional

import numpy as np
import pandas as pd


def records_to_frame(records: List[dict]) -> pd.DataFrame:
    """把历史 K 线 records（含 date/open/high/low/close/volume 等）转成按 date 升序的 DataFrame。

    数据源返回的列可能同时存在中/英文或缺失，这里只取我们关心的列做规整：
    - date: 统一成 %Y-%m-%d 字符串
    - open/high/low/close 统一 float
    - volume 统一 float（部分源为字符串或为 0）
    """
    if not records:
        return pd.DataFrame()

    df = pd.DataFrame(records)
    # 列名别名归一
    rename = {
        "trade_date": "date",
        "日期": "date",
        "开盘": "open",
        "最高": "high",
        "最低": "low",
        "收盘": "close",
        "成交量": "volume",
        "vol": "volume",
    }
    df.rename(columns={k: v for k, v in rename.items() if k in df.columns}, inplace=True)

    keep = [c for c in ("date", "open", "high", "low", "close", "volume") if c in df.columns]
    df = df[keep]

    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"]).dt.strftime("%Y-%m-%d")

    numeric_cols = [c for c in ("open", "high", "low", "close", "volume") if c in df.columns]
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    # 去重 + 排序，取最后保留 date 非空行
    if "date" in df.columns:
        df = (df.dropna(subset=["date"])
                .drop_duplicates(subset=["date"], keep="last")
                .sort_values("date"))
    return df.reset_index(drop=True)


def add_ma(df: pd.DataFrame, windows: List[int]) -> pd.DataFrame:
    """对 close 追加 `ma{window}` 列。窗口足够时用 rolling，不足的行置 NaN。"""
    if df.empty or "close" not in df.columns:
        return df
    out = df.copy()
    for w in windows:
        out[f"ma{w}"] = out["close"].rolling(window=w, min_periods=w).mean()
    return out


def detect_ma_cross_up(
    df: pd.DataFrame, fast_label: str, slow_label: str, lookback_days: int
) -> Optional[dict]:
    """检测“快均线上穿慢均线”的金叉。

    返回最近一次 fast 由 <=slow 变为 >slow 的信息：
        {'cross_date': 'YYYY-MM-DD', 'cross_bars_ago': int}  # 距今多少根K线(0=今日金叉)
    若 lookback_days 内没有发生返回 None。
    用法：ma60 上穿 ma200 => fast_label='ma60', slow_label='ma200'。
    只保留两线均有效的行——只有两侧都有值才谈得上相对位置（避免 ma200 刚起步的假交叉）。
    """
    if df.empty or fast_label not in df.columns or slow_label not in df.columns:
        return None
    valid = df[fast_label].notna() & df[slow_label].notna()
    whole = df[valid].reset_index(drop=True)
    if len(whole) < 2:
        return None

    above = whole[fast_label] > whole[slow_label]
    last_cross_row = None
    for i in range(1, len(whole)):
        if (not above.iloc[i - 1]) and above.iloc[i]:
            last_cross_row = i  # 循环结束后保留最近一次
    if last_cross_row is None:
        return None

    bars_to_end = int(len(whole) - 1 - last_cross_row)
    if bars_to_end > lookback_days:
        return None
    return {
        "cross_date": str(whole.iloc[last_cross_row].get("date")),
        "cross_bars_ago": bars_to_end,
    }


def dist_to_ma(df: pd.DataFrame, ma_label: str) -> Optional[float]:
    """最新 close 相对 ma 的乖离率：(close - ma)/ma * 100，保留 2 位。无有效值返回 None。"""
    if df.empty or "close" not in df.columns or ma_label not in df.columns:
        return None
    last = df.iloc[-1]
    if pd.isna(last[ma_label]) or pd.isna(last.get("close")):
        return None
    ma = float(last[ma_label])
    if ma == 0:
        return None
    return round((float(last["close"]) - ma) / ma * 100, 2)


def slope_pct(df: pd.DataFrame, col: str, window: int) -> Optional[float]:
    """最近 window 根内某均线/收盘价的斜率(以百分比计)：用**首尾值变化率**，避免线性回归开销。

    用于约束“MA20 仍向上”。返回正值表示上行。
    """
    if df.empty or col not in df.columns:
        return None
    vals = pd.to_numeric(df[col], errors="coerce").dropna()
    if len(vals) < window:
        return None
    seg = vals.tail(window)
    base = float(seg.iloc[0])
    if base == 0:
        return None
    return round((float(seg.iloc[-1]) - base) / base * 100, 3)


def slope_regression(series: pd.Series, window: int, log: bool = False) -> Optional[float]:
    """最近 window 根的**线性回归**斜率（%/日）。

    `log=True`  → 对 `log(值)` 回归后 ×100（**对数收益斜率**，价格口径）
    `log=False` → 对原值回归后 ÷均值 ×100（**归一化斜率**，均线口径；均值为 0 时返回 0.0）

    数值与原 `TrendTradingAnalyzer._calculate_trend_slope` 一致（**不剔除 NaN**，保持原行为）。
    """
    vals = series.tail(window)
    if len(vals) < 2:
        return None
    x = np.arange(len(vals))
    y = np.log(vals.values.astype(float)) if log else vals.values.astype(float)
    slope, _ = np.polyfit(x, y, 1)
    if log:
        return float(slope * 100)
    avg = float(np.mean(y))
    return float(slope / avg * 100) if avg != 0 else 0.0


def is_bullish_arrangement(row, fast: str = "ma20", mid: str = "ma60",
                           slow: str = "ma120", tolerance: float = 0.0) -> bool:
    """多头排列：`fast > mid > slow`，且 `fast > slow × (1 + tolerance)`。"""
    return (row[fast] > row[mid] > row[slow]
            and row[fast] > row[slow] * (1 + tolerance))


def is_bearish_arrangement(row, fast: str = "ma20", mid: str = "ma60",
                           slow: str = "ma120", tolerance: float = 0.0) -> bool:
    """空头排列：`fast < mid < slow`，且 `fast < slow × (1 - tolerance)`。"""
    return (row[fast] < row[mid] < row[slow]
            and row[fast] < row[slow] * (1 - tolerance))


def is_near_price(price, target, tolerance: float = 0.05) -> bool:
    """价格是否落在目标价的 ±tolerance 区间内（默认 ±5%）。"""
    return target * (1 - tolerance) <= price <= target * (1 + tolerance)
