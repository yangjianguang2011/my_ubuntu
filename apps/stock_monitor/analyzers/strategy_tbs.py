"""
反转策略信号 —— 月线反转 6.5 + 三线红 + 卖点（**全在 RPS 底座之上**）。

公式来源与口径见开发资料 `docs/dev/`（不入库）。
本模块把通达信公式逐条翻译为 pandas，**只在项目内**、只依赖 stockdb 日K。

三个信号：
  1. `monthly_reversal`  月线反转 6.5（7 组 FYX1~FYX7 全 AND）  —— **买点/选股**
  2. `triple_red`        三线红（RPS50/120/250 同时 ≥90）        —— 买点/关注
  3. `break_ma20_exit`   有效跌破 20 日线                        —— **卖点/止损**

⚠️ 关于卖点：该体系**没有**公开过「月线反转卖点公式」（见调研结论），
   他成文的卖出准则里唯一**可自动量化且不依赖主观判断**的是
   《顺向火车轨 3.0》的"有效跌破 20 日线且没有勾头向上的迹象"。
   本模块据此实现为：**连续 `confirm_bars` 日收盘 < MA20，且 MA20 不再上升**
   （`ma20 <= ma20.shift(slope_lag)`）。这是**官方规则的忠实近似**，
   不是新造的信号。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional, Sequence

import numpy as np
import pandas as pd

from config import setup_logger

logger = setup_logger(__name__)

# ---------------------------------------------------------------- 参数
@dataclass
class TbsParams:
    """月线反转 6.5 参数（默认值 = 公式原值，不建议随意改）。"""

    # —— FYX1 相对强度 ——
    rps50_min: float = 0.87          # RPS50 > 87
    rps120_min: float = 0.90         # RPS120 > 90
    rps90: float = 0.90              # FYX130 / FYX32 用的 90 分位线
    sigma_rps50_min: float = 0.87    # 三线红：RPS50 ≥ 90 用 rps90
    # —— FYX3 / FYX13 ——
    new_high_win: int = 70           # 创 70 日最高收盘价
    nh80_win: int = 80
    nh80_lookback: int = 10          # 10 天内曾创 80 日新高
    nh50_win: int = 50
    # —— FYX4 均线 ——
    ma_fast: int = 20
    ma_long: int = 200
    ma_ratio: float = 0.90           # MA120 / MA200 > 0.9
    ma_mid: int = 120
    # —— FYX5 站上均线天数 ——
    hold_win: int = 45
    hold_min: int = 2
    # —— FYX6 阶段涨幅 ——
    range_high_win: int = 30
    range_low_win: int = 120
    range_max_l1: float = 1.50
    range_max_l2: float = 1.55
    range_max_l3: float = 1.65
    ma_slope_lag: int = 10
    ma_slope_lag2: int = 15
    # —— FYX7 距高点 ——
    near_high_win: int = 5
    near_high_ref: int = 120
    near_high_l1: float = 0.85
    near_high_l2: float = 0.80
    close_win: int = 10
    close_ratio: float = 0.90
    # —— 信号去重 ——
    dedup_days: int = 15
    # —— 卖点 ——
    exit_ma: int = 20
    exit_confirm_bars: int = 2
    exit_slope_lag: int = 1


# ---------------------------------------------------------------- 月线反转 6.5
def compute_tbs(df: pd.DataFrame,
                params: Optional[TbsParams] = None,
                rps: Optional[pd.DataFrame] = None) -> pd.DataFrame:
    """单只股票：算月线反转 6.5 + 三线红 + 卖点。

    `df`  —— 升序日K（date/open/high/low/close），**qfq**
    `rps` —— 同 index 的 RPS（列名 rps50/rps120/rps250，0~1）。
              也可直接给 `df` 带这些列（宽表转长表时用）。

    返回 `df` + 各条件中间列 + `monthly_reversal` / `triple_red` / `break_ma20_exit`。
    """
    p = params or TbsParams()
    if df is None or df.empty or "close" not in df.columns:
        return pd.DataFrame()

    out = df.copy().sort_values("date").reset_index(drop=True)
    c = out["close"].astype(float)
    h = out["high"].astype(float)
    low = out["low"].astype(float)

    # —— RPS 对齐（**按日期 merge**，不能按位置，否则两者长度不同会炸）——
    if rps is not None and len(getattr(rps, "columns", [])) > 0:
        rp = rps.copy()
        if "date" in rp.columns:
            rp["date"] = pd.to_datetime(rp["date"])
            out["date"] = pd.to_datetime(out["date"])
            out = out.merge(rp[["date", "rps50", "rps120", "rps250"]],
                            on="date", how="left")
        else:
            # 无 date 列 → 退回按位置（仅当长度一致时）
            if len(rp) == len(out):
                for col in ("rps50", "rps120", "rps250"):
                    if col in rp.columns:
                        out[col] = rp[col].values
    for col in ("rps50", "rps120", "rps250"):
        if col not in out.columns:
            out[col] = np.nan

    rps50 = out["rps50"] * 100.0      # 转 0~100，与公式一致
    rps120 = out["rps120"] * 100.0
    rps250 = out["rps250"] * 100.0

    # ===== FYX13（被多组引用）= (RPS50≥90 或 RPS120≥90) 且 创70日最高收盘价 =====
    fyx130 = (rps50 >= p.rps90 * 100) | (rps120 >= p.rps90 * 100)
    fyx131 = c >= c.rolling(p.new_high_win, min_periods=p.new_high_win).max()
    fyx13 = fyx130 & fyx131

    # ===== FYX1 股价相对强度 =====
    fyx11 = rps50 > p.rps50_min * 100
    fyx12 = rps120 > p.rps120_min * 100
    fyx1 = fyx11 | fyx12

    # ===== FYX2 结构紧凑（低点抬高）=====
    fyx21 = (low.rolling(50).min() > low.rolling(200).min()) & fyx13
    fyx22 = (low.rolling(30).min() > low.rolling(120).min()) & fyx13
    fyx23 = low.rolling(20).min() > low.rolling(50).min()
    fyx2 = fyx21 | fyx22 | fyx23

    # ===== FYX3 创N日新高 =====
    # 对齐原公式：`NH80:=IF(H<HHV(H,80),0,1)` → **创新高记 1**（H>=80日最高），
    # `FYX31:=COUNT(NH80,10)` → 10 天内**至少一天创 80 日新高**。
    # （旧实现写成 `h < rolling_max` 记 1，方向反了 → fyx31 几乎恒真）
    is_new_high = (h >= h.rolling(p.nh80_win, min_periods=p.nh80_win).max()).astype(int)
    fyx31 = is_new_high.rolling(p.nh80_lookback, min_periods=1).sum() > 0
    fyx32 = ((c >= c.rolling(p.nh50_win).max())
             | (h >= h.rolling(p.nh50_win).max())) & fyx130
    fyx3 = fyx31 | fyx32

    # ===== FYX4 站上均线 =====
    ma20 = c.rolling(p.ma_fast).mean()
    ma120 = c.rolling(p.ma_mid).mean()
    ma200 = c.rolling(p.ma_long).mean()
    ma250 = c.rolling(250).mean()
    fyx4 = (c > ma20) & (c > ma200) & (ma120 / ma200 > p.ma_ratio)

    # ===== FYX5 站上长期均线天数限制 =====
    nn200 = (c > ma200).astype(int)
    aa200 = nn200.rolling(p.hold_win, min_periods=1).sum()
    nn250 = (c > ma250).astype(int)
    aa250 = nn250.rolling(p.hold_win, min_periods=1).sum()
    fyx51 = (aa200 >= p.hold_min) & (aa200 < p.hold_win)
    lnn200 = (low < ma200).astype(int)
    fyx52 = (lnn200.rolling(p.hold_win, min_periods=1).sum() > 0) & (aa200 > p.hold_min)
    lnn250 = (low < ma250).astype(int)
    fyx53 = (lnn250.rolling(p.hold_win, min_periods=1).sum() > 0) & (aa250 > p.hold_min)
    fyx5 = fyx51 | fyx52 | fyx53

    # ===== FYX6 阶段涨幅上限 + 长均线趋势 =====
    fyx6011 = ((ma120 >= ma120.shift(p.ma_slope_lag))
               | (ma200 >= ma200.shift(p.ma_slope_lag)))
    fyx6012 = ((ma120 >= ma120.shift(p.ma_slope_lag2))
               | (ma200 >= ma200.shift(p.ma_slope_lag2)))
    fyx601 = fyx6011 | fyx6012
    fyx6021 = ((ma120 >= ma120.shift(p.ma_slope_lag))
               & (ma200 >= ma200.shift(p.ma_slope_lag)))
    fyx6022 = ((ma120 >= ma120.shift(p.ma_slope_lag2))
               & (ma200 >= ma200.shift(p.ma_slope_lag2)))
    fyx602 = fyx6021 | fyx6022
    fyx603 = (ma120 > ma200) & fyx601

    rng = (h.rolling(p.range_high_win).max()
           / low.rolling(p.range_low_win).min())
    fyx61 = (rng < p.range_max_l1) & fyx601
    fyx62 = (rng < p.range_max_l2) & fyx602
    fyx63 = (rng < p.range_max_l3) & fyx603 & fyx13
    fyx6 = fyx61 | fyx62 | fyx63

    # ===== FYX7 距高点 =====
    fyx71 = (h.rolling(p.near_high_win).max()
             / h.rolling(p.near_high_ref).max()) > p.near_high_l1
    fyx72 = ((h.rolling(p.near_high_win).max()
              / h.rolling(p.near_high_ref).max()) > p.near_high_l2) & fyx13
    fyx73 = (c / h.rolling(p.close_win).max()) > p.close_ratio
    fyx7 = (fyx71 | fyx72) & fyx73

    # ===== 合成 =====
    yxfz = fyx1 & fyx2 & fyx3 & fyx4 & fyx5 & fyx6 & fyx7
    out["monthly_reversal"] = yxfz.fillna(False).astype(bool)
    # 15 天内只报首日（公式 BARSSINCEN(YXFZ,15)=0）
    out["monthly_reversal_first"] = out["monthly_reversal"] & ~(
        out["monthly_reversal"].rolling(p.dedup_days, min_periods=1).sum().shift(1) > 0)

    # ===== 三线红 =====
    out["triple_red"] = ((rps50 >= p.rps90 * 100)
                         & (rps120 >= p.rps90 * 100)
                         & (rps250 >= p.rps90 * 100)).fillna(False).astype(bool)

    # ===== 卖点：有效跌破 20 日线 =====
    out["break_ma20_exit"] = _break_ma_exit(c, p)

    # 各组中间列（便于诊断"卡在哪一条"）
    for name, s in (("fyx1", fyx1), ("fyx2", fyx2), ("fyx3", fyx3), ("fyx4", fyx4),
                    ("fyx5", fyx5), ("fyx6", fyx6), ("fyx7", fyx7), ("fyx13", fyx13)):
        out[name] = s.fillna(False).astype(bool)
    for name, s in (("ma20", ma20), ("ma120", ma120),
                    ("ma200", ma200), ("ma250", ma250)):
        out[name] = s
    return out


def _break_ma_exit(close: pd.Series, p: TbsParams) -> pd.Series:
    """有效跌破 MA20：**连续 exit_confirm_bars 日收盘 < MA20 且 MA20 不再上升**。

    对应原文「股价很快向下**有效**跌破了 20 日线，并且**没有勾头向上**的迹象」。
    """
    ma = close.rolling(p.exit_ma).mean()
    below = close < ma
    confirmed = below.rolling(p.exit_confirm_bars, min_periods=p.exit_confirm_bars).sum() \
        >= p.exit_confirm_bars
    flat_or_down = ma <= ma.shift(p.exit_slope_lag)
    return (confirmed & flat_or_down).fillna(False).astype(bool)


# ---------------------------------------------------------------- 宽表批量
def scan_panel(close: pd.DataFrame, high: pd.DataFrame, low: pd.DataFrame,
               rps: Dict[str, pd.DataFrame],
               params: Optional[TbsParams] = None,
               codes: Optional[Sequence[str]] = None,
               progress_every: int = 500) -> Dict[str, pd.DataFrame]:
    """全市场批量扫描（宽表进、宽表出）。

    返回 {signal_name: bool 宽表}，signal_name ∈
      monthly_reversal / monthly_reversal_first / triple_red / break_ma20_exit
    另含 `fyx_hit` —— 每只股票每月线反转信号命中的条件组数（诊断用）。
    """
    p = params or TbsParams()
    codes = list(codes or close.columns)
    sig_names = ("monthly_reversal", "monthly_reversal_first",
                 "triple_red", "break_ma20_exit")
    acc: Dict[str, Dict[str, pd.Series]] = {k: {} for k in sig_names}
    fyx_acc: Dict[str, pd.Series] = {}

    for i, code in enumerate(codes, 1):
        if code not in close.columns:
            continue
        try:
            sub = pd.DataFrame({
                "date": close.index,
                "close": close[code].values,
                "high": high[code].values if code in high.columns else close[code].values,
                "low": low[code].values if code in low.columns else close[code].values,
            })
            rp = pd.DataFrame({k: v[code].values for k, v in rps.items()
                               if code in v.columns})
            rp["date"] = close.index
            m = compute_tbs(sub, p, rps=rp)
            if m.empty:
                continue
            idx = close.index
            for k in sig_names:
                acc[k][code] = pd.Series(m[k].values, index=idx)
            # 命中的条件组数（0~7）
            grp = sum(m[g].astype(int) for g in
                      ("fyx1", "fyx2", "fyx3", "fyx4", "fyx5", "fyx6", "fyx7"))
            fyx_acc[code] = pd.Series(grp.values, index=idx)
        except Exception as e:  # noqa: BLE001
            logger.warning(f"策略扫描 {code} 失败：{type(e).__name__}: {e}")
        if i % progress_every == 0:
            logger.info(f"策略扫描 {i}/{len(codes)}")

    out = {k: pd.DataFrame(v).reindex(index=close.index, columns=codes)
           for k, v in acc.items()}
    out["fyx_hit"] = pd.DataFrame(fyx_acc).reindex(index=close.index, columns=codes)
    return out
