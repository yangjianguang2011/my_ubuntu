"""
因子计算专用工具 — 需要 numpy/pandas 依赖。
从原 factor_signal/utils.py 拆出，避免 data_fetchers 被迫加载 numpy。
"""
import numpy as np
import pandas as pd
from bisect import bisect_left, bisect_right, insort


def expanding_pct(s: pd.Series, min_periods: int, start_pos: int = 0) -> pd.Series:
    """历史位置：t 时刻的值在"截至 t 的历史"中的百分位(<=计)。

    min_periods 之前为 NaN。start_pos 之前的样本不计入历史分布（对齐口径用）。
    """
    out = np.full(len(s), np.nan)
    buf: list = []
    n = 0
    for i, v in enumerate(s.values):
        if i < start_pos:
            continue
        if v is None or (isinstance(v, float) and np.isnan(v)):
            continue
        insort(buf, float(v))
        n += 1
        if n >= min_periods:
            out[i] = bisect_right(buf, float(v)) / n
    return pd.Series(out, index=s.index)


def rolling_pct(s: pd.Series, window: int, min_periods: int) -> pd.Series:
    """滚动窗口历史位置：t 时刻的值在最近 window 个有效样本中的百分位(<=计)。

    与 expanding_pct 不同，窗口固定长度、随时间前移，避免"历史起点"带来的前视。
    """
    out = np.full(len(s), np.nan)
    buf: list = []           # 有序值列表（用于分位）
    fifo: list = []          # 进入顺序（用于淘汰）
    vals = s.values
    for i, v in enumerate(vals):
        if v is None or (isinstance(v, float) and np.isnan(v)):
            continue
        insort(buf, float(v))
        fifo.append(float(v))
        if len(fifo) > window:
            old = fifo.pop(0)
            j = bisect_left(buf, old)
            if j < len(buf) and buf[j] == old:
                buf.pop(j)
        if len(buf) >= min_periods:
            out[i] = bisect_right(buf, float(v)) / len(buf)
    return pd.Series(out, index=s.index)
