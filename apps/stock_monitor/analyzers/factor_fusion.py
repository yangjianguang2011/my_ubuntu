# -*- coding: utf-8 -*-
"""多因子融合因子 —— 把估值维度读数融合成一个 0~1 的"融合读数"。

口径（见 plan/估值报告-多因子融合层-设计.md §7）：
  特征：pb_adj_b_pct / pr_pct / pe_ttm_pct（均为 expanding 历史位置 0~1）
  朝向：先转"便宜"方向 f' = 1 − f（读数低=便宜→f' 高）
  权重：**全池共享**（M1/M2 实测：个股偏移有害，见 §7.7），非负、Σ=1
  融合读数：s = Σ f'_i · w_i   （s 高 = 好买点）
  术语统一：面板显示 r = 1 − s（低 = 买），与其它估值读数方向一致。

权重来源（hs300 全池、H=250、target=ts 的约束回归，2026-09-20）：
  pb_adj_b_pct 0.41 / pr_pct 0.00 / pe_ttm_pct 0.59
  → pr_pct 权重为 0（被 pe/pb 覆盖）；不纳入非估值因子（price_cycle 朝向相反）。

注意：融合信号是**相对自身历史**的时序读数（信号在时序不在横截面，§7.5）。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd

from ..core.utils import fmt_num, fmt_pct, safe_float
from .factors_registry import Factor, register

# 全池共享权重（hs300 / H=250，见模块 docstring）
FUSION_WEIGHTS: Dict[str, float] = {
    "pb_adj_b_pct": 0.41,
    "pr_pct": 0.00,
    "pe_ttm_pct": 0.59,
}

# 买卖阈值（与其它读数一致的 10/90；融合读数 r 低=买）
PCT_BUY = 0.10
PCT_SELL = 0.90


@dataclass
class FusionParams:
    weights: Dict[str, float] = None

    def __post_init__(self):
        if self.weights is None:
            self.weights = dict(FUSION_WEIGHTS)


def compute_fusion(df, params=None) -> pd.DataFrame:
    """输入日K（需含各特征列或可由估值因子产出），输出 fusion / fusion_pct。"""
    p = params or FusionParams()
    if df is None or df.empty:
        return pd.DataFrame()
    out = df.copy()
    feats = [(k, v) for k, v in p.weights.items() if v > 0 and k in out.columns]
    if not feats:
        return pd.DataFrame()
    cols = [k for k, _ in feats]
    ws = np.array([v for _, v in feats], dtype=float)
    ws = ws / ws.sum()
    # 便宜朝向 f' = 1 − f（缺失按各列中位数位置 0.5 处理前先算 mask）
    F = 1.0 - out[cols].astype(float)
    valid = F.notna().all(axis=1)
    out["fusion"] = np.nan
    if valid.any():
        out.loc[valid, "fusion"] = (F.loc[valid].to_numpy() @ ws)
    # 融合读数 r = 1 − s（低=买，与其它面板读数方向一致）
    out["fusion_pct"] = 1.0 - out["fusion"]
    # 仅供参考：融合 s 自身的历史位置（s 高=好买点）
    return out


def latest_fusion(metrics) -> Dict:
    if metrics is None or metrics.empty or "fusion" not in metrics.columns:
        return {}
    last = metrics.iloc[-1]
    return {
        "fusion": {"label": "多因子融合读数", "value": safe_float(last.get("fusion")),
                   "pct": safe_float(last.get("fusion_pct"))},
        "fusion_s": {"label": "多因子融合(便宜度)", "value": safe_float(last.get("fusion")),
                     "pct": None},
    }


def panel_rows(ctx: dict) -> List[Tuple[str, str, str]]:
    """融合面板行。"""
    reads = ctx.get("readings", {})
    d = reads.get("fusion")
    if not d:
        return []
    r = d.get("pct")
    s = d.get("value")
    wtxt = " / ".join(f"{k.replace('_pct','').replace('pb_adj_b','PBadjB').replace('pb_adj','PBadj')}="
                      f"{fmt_num(v)}" for k, v in FUSION_WEIGHTS.items() if v > 0)
    return [("多因子融合读数", fmt_num(r),
             f"{fmt_pct(r)} 位置（低=买）· 便宜度 s={fmt_num(s)} · 权重 {wtxt}（全池共享）")]


register(Factor(
    name="fusion",
    title="多因子融合（估值维度）",
    compute=compute_fusion,
    latest=latest_fusion,
    panel_rows=panel_rows,
    merge_cols=("fusion", "fusion_pct"),
))
