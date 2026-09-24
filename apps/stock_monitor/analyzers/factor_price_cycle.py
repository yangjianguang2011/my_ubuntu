"""
价格周期因子 — 均线偏离/z分数/距高点/动量/RSI/波动 6 项等权。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from ..core.utils import safe_float, fmt_num, fmt_pct
from .factor_utils import expanding_pct
from .factors_registry import Factor, register

MA_WINDOW = 250
PCT_MIN_PERIODS = 250
MOM_LOOKBACK = 250
MOM_SKIP = 21
VOL_WINDOW = 20

_ITEMS = [
    ("pc_ma_dev", "长期均线偏离(close/MA250-1)"),
    ("pc_z", "均值回复z((close-MA250)/std250)"),
    ("pc_dist_high", "距52周高点(close/max250-1)"),
    ("pc_mom", "12-1月动量"),
    ("pc_rsi", "RSI(250)"),
    ("pc_vol_lo", "低波动位置(波动率反向)"),
]


@dataclass
class PriceCycleParams:
    ma_window: int = MA_WINDOW
    pct_min_periods: int = PCT_MIN_PERIODS
    mom_lookback: int = MOM_LOOKBACK
    mom_skip: int = MOM_SKIP
    vol_window: int = VOL_WINDOW


def rsi(close: pd.Series, n: int) -> pd.Series:
    """Wilder RSI。"""
    d = close.diff()
    up = d.clip(lower=0).ewm(alpha=1.0 / n, adjust=False).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1.0 / n, adjust=False).mean()
    out = 100.0 - 100.0 / (1.0 + up / dn.replace(0, np.nan))
    out = out.where(dn != 0, 100.0)
    out = out.mask((up == 0) & (dn == 0), 50.0)
    out = out.mask(up.isna() | dn.isna(), np.nan)
    return out


def compute_price_cycle(df, params=None) -> pd.DataFrame:
    """输入升序日K(至少 date/close)，输出各分项 + 综合 price_cycle（0~1）。"""
    p = params or PriceCycleParams()
    if df is None or df.empty or "close" not in df.columns:
        return pd.DataFrame()
    out = df.copy()
    c = out["close"].astype(float)
    ma = c.rolling(p.ma_window, min_periods=int(p.ma_window * 0.8)).mean()
    sd = c.rolling(p.ma_window, min_periods=int(p.ma_window * 0.8)).std()
    hi = c.rolling(p.ma_window, min_periods=int(p.ma_window * 0.8)).max()

    out["pc_ma_dev"] = c / ma - 1.0
    out["pc_z"] = (c - ma) / sd.replace(0, np.nan)
    out["pc_dist_high"] = c / hi - 1.0
    out["pc_mom"] = c.shift(p.mom_skip) / c.shift(p.mom_lookback) - 1.0
    out["pc_rsi"] = rsi(c, p.ma_window)
    out["pc_vol_lo"] = c.pct_change().rolling(p.vol_window).std() * np.sqrt(252.0)

    pos_cols = []
    for col, _label in _ITEMS:
        s = out[col]
        if col == "pc_vol_lo":
            s = -s
        out[f"{col}_pos"] = expanding_pct(s, p.pct_min_periods)
        pos_cols.append(f"{col}_pos")
    out["price_cycle"] = out[pos_cols].mean(axis=1, skipna=True)
    return out


def latest_cycle(metrics) -> Optional[Dict]:
    """最新读数：综合位置 + 各分项。"""
    if metrics is None or metrics.empty or "price_cycle" not in metrics.columns:
        return None
    last = metrics.iloc[-1]
    items = []
    for col, label in _ITEMS:
        v = safe_float(last.get(f"{col}_pos"))
        raw = safe_float(last.get(col))
        items.append({"item": label, "pos": v, "value": raw})
    pc = safe_float(last.get("price_cycle"))
    return {"date": str(pd.Timestamp(last["date"]))[:10],
            "price_cycle": pc, "items": items}


def panel_rows(ctx: dict) -> List[Tuple[str, str, str]]:
    """价格周期面板行。"""
    pc = ctx.get("price_cycle")
    if pc is None:
        return []
    return [("价格周期位置(维度⑤)", fmt_num(pc),
             f"{fmt_pct(pc)} 位置 · 均线偏离/z/距高/动量/RSI/波动 6 项等权")]


register(Factor(
    name="price_cycle",
    title="价格周期",
    compute=compute_price_cycle,
    latest=latest_cycle,
    panel_rows=panel_rows,
    merge_cols=("price_cycle",),
))
